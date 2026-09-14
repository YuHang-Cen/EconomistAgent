"""Stage 4 integration behaviors: soft delete, retry/cancel, answer edge cases."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import OutputType
from app.domain.models import AuthorSkillSnapshot
from app.infra import storage
from app.infra.db import session_scope
from app.services import job_service
from fastapi.testclient import TestClient


def _now_iso() -> str:
    """Return current UTC ISO-8601 timestamp."""
    return datetime.now(tz=UTC).isoformat()


def _wait_job_status(
    client: TestClient, job_id: str, expected: str, max_attempts: int = 200
) -> dict[str, Any]:
    """Poll until job reaches expected status."""
    payload: dict[str, Any] = {}
    for _ in range(max_attempts):
        response = client.get(f"/api/jobs/{job_id}")
        payload = response.json()["data"]
        if payload.get("status") == expected or payload.get("status") in {
            "success",
            "failed",
            "canceled",
        }:
            return payload
        time.sleep(0.05)
    return payload


def _create_author(client: TestClient, author_name: str) -> str:
    """Create author and return author_id."""
    response = client.post(
        "/api/authors",
        json={"authorName": author_name, "school": "test", "avatarUrl": ""},
    )
    return response.json()["data"]["authorId"]


def _create_document(
    client: TestClient,
    author_id: str,
    title: str,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> tuple[str, str]:
    """Upload a valid local PDF and return (document_id, reload_job_id)."""
    safe_name = f"{title.lower().replace(' ', '-')}.pdf"
    pdf_uri = create_test_pdf(safe_name)
    response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": title, "pdfUri": pdf_uri},
    )
    payload = response.json()["data"]
    return payload["documentId"], payload["reloadJobId"]


def _insert_empty_snapshot(author_id: str) -> None:
    """Insert a latest snapshot with empty skill artifacts."""
    snapshot_id = str(uuid.uuid4())
    root = storage.snapshot_root(author_id=author_id, snapshot_id=snapshot_id)
    main_uri = storage.write_json(root / "main_skill.json", {"main_skills": []})
    sub_uri = storage.write_json(root / "sub_skill.json", {"sub_skills": []})
    outputs = {
        OutputType.MAIN_SKILL_JSON.value: main_uri,
        OutputType.SUB_SKILL_JSON.value: sub_uri,
    }

    with session_scope() as session:
        session.add(
            AuthorSkillSnapshot(
                snapshot_id=snapshot_id,
                author_id=author_id,
                is_latest=True,
                outputs_json=json.dumps(outputs),
                created_at=_now_iso(),
            )
        )


def test_soft_delete_consistency_after_reload(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """Soft-deleted chapter/segment should not be resurrected by reload."""
    author_id = _create_author(client, "Stage4 Delete")
    document_id, reload_job_id = _create_document(
        client, author_id, "Delete Consistency Book", create_test_pdf
    )
    _wait_job_status(client, reload_job_id, "success")

    chapters = client.get(f"/api/authors/{author_id}/documents/{document_id}/chapters").json()[
        "data"
    ]
    assert chapters, "expected chapters after reload"

    chapter_id = chapters[0]["chapterId"]
    segments_before = client.get(
        f"/api/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}/segments"
    ).json()["data"]
    assert segments_before, "expected segments after reload"
    deleted_segment_id = segments_before[0]["segmentId"]
    client.delete(f"/api/authors/{author_id}/documents/{document_id}/segments/{deleted_segment_id}")

    reload_response = client.post(
        f"/api/authors/{author_id}/documents/{document_id}/reload"
    ).json()["data"]
    _wait_job_status(client, reload_response["reloadJobId"], "success")

    segments_after = client.get(
        f"/api/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}/segments"
    ).json()["data"]
    segment_ids_after = {item["segmentId"] for item in segments_after}
    assert deleted_segment_id not in segment_ids_after

    deleted_chapter_id = chapter_id
    client.delete(f"/api/authors/{author_id}/documents/{document_id}/chapters/{deleted_chapter_id}")

    reload_response2 = client.post(
        f"/api/authors/{author_id}/documents/{document_id}/reload"
    ).json()["data"]
    _wait_job_status(client, reload_response2["reloadJobId"], "success")

    chapters_after = client.get(
        f"/api/authors/{author_id}/documents/{document_id}/chapters"
    ).json()["data"]
    chapter_ids_after = {item["chapterId"] for item in chapters_after}
    assert deleted_chapter_id not in chapter_ids_after


def test_retry_and_cancel_semantics(client: TestClient) -> None:
    """Cover retry after failure and cancel short-circuit behavior."""
    author_id = _create_author(client, "Stage4 Retry")

    skills_job_id = client.post(f"/api/authors/{author_id}/jobs/skills").json()["data"]["jobId"]
    failed_payload = _wait_job_status(client, skills_job_id, "failed")
    assert failed_payload["status"] == "failed"

    retry_payload = client.post(f"/api/jobs/{skills_job_id}/retry").json()["data"]
    assert retry_payload["status"] in {"queued", "failed"}
    failed_payload_retry = _wait_job_status(client, skills_job_id, "failed")
    assert failed_payload_retry["status"] == "failed"

    queued_job = job_service.create_author_skills_job(author_id=author_id, auto_run=False)
    queued_job_id = queued_job["jobId"]
    canceled_payload = client.post(f"/api/jobs/{queued_job_id}/cancel").json()["data"]
    assert canceled_payload["status"] == "canceled"

    job_service.execute_author_skills_job(queued_job_id)
    canceled_after_execute = client.get(f"/api/jobs/{queued_job_id}").json()["data"]
    assert canceled_after_execute["status"] == "canceled"

    second_cancel = client.post(f"/api/jobs/{queued_job_id}/cancel")
    second_cancel_payload = second_cancel.json()
    assert second_cancel.status_code == 409
    assert second_cancel_payload["error"]["code"] == "TASK_CONFLICT"


def test_author_answer_edge_cases(client: TestClient) -> None:
    """Cover no snapshot, empty query, and empty-skill snapshot behavior."""
    author_without_snapshot = _create_author(client, "Stage4 No Snapshot")
    no_snapshot_job_id = client.post(
        f"/api/authors/{author_without_snapshot}/jobs/answer",
        json={"query": "what is the mechanism"},
    ).json()["data"]["jobId"]
    failed_no_snapshot = _wait_job_status(client, no_snapshot_job_id, "failed")
    assert failed_no_snapshot["status"] == "failed"

    empty_query_response = client.post(
        f"/api/authors/{author_without_snapshot}/jobs/answer",
        json={"query": ""},
    )
    empty_query_payload = empty_query_response.json()
    assert empty_query_response.status_code == 422
    assert empty_query_payload["error"]["code"] == "INVALID_ARGUMENT"

    author_empty_skills = _create_author(client, "Stage4 Empty Skills")
    _insert_empty_snapshot(author_empty_skills)
    empty_skill_job_id = client.post(
        f"/api/authors/{author_empty_skills}/jobs/answer",
        json={"query": "explain"},
    ).json()["data"]["jobId"]
    failed_empty_skill = _wait_job_status(client, empty_skill_job_id, "failed")
    assert failed_empty_skill["status"] == "failed"
