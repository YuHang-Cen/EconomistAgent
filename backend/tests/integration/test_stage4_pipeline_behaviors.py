"""Stage 4 integration behaviors: soft delete, retry/cancel, answer edge cases."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.domain.enums import OutputType
from app.domain.models import Author, AuthorSkillSnapshot
from app.infra import storage
from app.infra.db import session_scope
from app.services import answer_with_skills, job_service, pipeline_service
from fastapi.testclient import TestClient


def _now_iso() -> str:
    """Return current UTC ISO-8601 timestamp."""
    return datetime.now(tz=UTC).isoformat()


def _wait_job_status(
    client: TestClient, job_id: str, expected: str, max_attempts: int = 12
) -> dict[str, Any]:
    """Poll until job reaches expected status."""
    payload: dict[str, Any] = {}
    for _ in range(max_attempts):
        response = client.get(f"/api/jobs/{job_id}")
        payload = response.json()["data"]
        if payload.get("status") == expected:
            return payload
    return payload


def _create_author(client: TestClient, author_name: str) -> str:
    """Create author and return author_id."""
    response = client.post(
        "/api/authors",
        json={"authorName": author_name, "school": "test", "avatarUrl": ""},
    )
    return response.json()["data"]["authorId"]


def _insert_author(author_name: str) -> str:
    """Insert an author directly for service-level integration tests."""
    author_id = str(uuid.uuid4())
    now = _now_iso()
    with session_scope() as session:
        session.add(
            Author(
                author_id=author_id,
                author_name=author_name,
                school="test",
                language="english",
                avatar_url="",
                created_at=now,
                updated_at=now,
            )
        )
    return author_id


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


def _insert_answerable_snapshot(author_id: str) -> None:
    """Insert a latest snapshot with minimal answerable markdown artifacts."""
    snapshot_id = str(uuid.uuid4())
    root = storage.snapshot_root(author_id=author_id, snapshot_id=snapshot_id)
    main_skill_json = {
        "main_skills": [
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "pattern_summary": {
                    "name": "Robot subsidy mechanism",
                    "description": "Explain how policy interacts with constraints.",
                    "applicability": "Policy analysis",
                    "core_steps": ["identify distortion", "trace firm response"],
                },
            }
        ]
    }
    sub_skill_json = {
        "sub_skills": [
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "name": "Constraint heterogeneity",
                "description": "Distinguish large and small firm responses.",
            }
        ]
    }
    main_md_json = [
        {
            "main_skill_id": "main_skill_001",
            "section_id": "section-1",
            "name": "Robot subsidy mechanism",
            "file_name": "main_skill_001.md",
            "markdown": "Focus on mechanism, distortion, and revision logic.",
        }
    ]
    sub_md_json = [
        {
            "main_skill_id": "main_skill_001",
            "section_id": "section-1",
            "name": "Constraint heterogeneity",
            "file_name": "sub_skill_001.md",
            "markdown": "Separate framing, identification, mechanism, and evidence asks.",
        }
    ]
    outputs = {
        OutputType.MAIN_SKILL_JSON.value: storage.write_json(
            root / "main_skill.json", main_skill_json
        ),
        OutputType.SUB_SKILL_JSON.value: storage.write_json(
            root / "sub_skill.json", sub_skill_json
        ),
        OutputType.MAIN_SKILLS_MD_JSON.value: storage.write_json(
            root / "main_skills_md.json", main_md_json
        ),
        OutputType.SUB_SKILLS_MD_JSON.value: storage.write_json(
            root / "sub_skills_md.json", sub_md_json
        ),
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


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses

    def invoke(self, prompt: str) -> _FakeResponse:
        if not self._responses:
            raise RuntimeError("no more fake llm responses")
        return _FakeResponse(self._responses.pop(0))


class _ExplodingLLM:
    def invoke(self, prompt: str) -> _FakeResponse:
        raise RuntimeError("llm unavailable")


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


def test_author_answer_paper_text_returns_structured_points(monkeypatch: object) -> None:
    """Long paper input should be classified as paper_text and return numbered points."""
    fake_llm = _FakeLLM(
        [
            (
                '{"title":"Referee Note","topic":"industrial policy",'
                '"summary":"The paper is interesting but needs sharper identification '
                'and framing.",'
                '"markdown":"# Referee Note\\n\\n'
                "1. Clarify the paper\\u2019s general contribution beyond the China setting.\\n"
                "2. Tighten identification around subsidy adoption.\\n"
                "3. Show more direct evidence for the financial-frictions channel."
                '"}'
            )
        ]
    )
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: fake_llm)
    monkeypatch.setattr(
        pipeline_service,
        "_run_select_skills_with_language",
        lambda **kwargs: {
            "selected_skill_indices": [1],
            "selected_section_ids": ["section-1"],
            "selection_mode": "fallback_rule",
            "selection_warning": None,
        },
    )
    monkeypatch.setattr(
        pipeline_service,
        "_run_direct_api_article_with_language",
        lambda **kwargs: {"title": "direct", "summary": "direct", "markdown": "# direct"},
    )

    author_id = _insert_author("Stage4 Paper Answer")
    _insert_answerable_snapshot(author_id)
    query = """
Abstract

This paper studies robot subsidies, financial frictions, and misallocation in China.

Keywords: industrial policy, robots
JEL codes: O25

1 Introduction

China provides an ideal setting because robot adoption is large and capital misallocation is severe.
"""

    job_id = job_service.create_author_answer_job(author_id=author_id, query=query)["jobId"]
    final_payload = job_service.get_job(job_id)
    assert final_payload["status"] == "success"

    answer_output = job_service.get_output(job_id, "answer_json")["content"]
    assert answer_output["query_kind"] == "paper_text"
    assert answer_output["answer_source"] == "llm"
    assert answer_output["answer"]["markdown"].count("\n1.") == 1
    assert "Keywords:" not in answer_output["answer"]["markdown"]


def test_author_answer_fallback_exposes_warning_without_raw_dump(monkeypatch: object) -> None:
    """Fallback path should expose metadata and avoid echoing the raw manuscript."""
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: _ExplodingLLM())
    monkeypatch.setattr(
        pipeline_service,
        "_run_select_skills_with_language",
        lambda **kwargs: {
            "selected_skill_indices": [1],
            "selected_section_ids": ["section-1"],
            "selection_mode": "fallback_rule",
            "selection_warning": None,
        },
    )
    monkeypatch.setattr(
        pipeline_service,
        "_run_direct_api_article_with_language",
        lambda **kwargs: {"title": "direct", "summary": "direct", "markdown": "# direct"},
    )

    author_id = _insert_author("Stage4 Fallback Answer")
    _insert_answerable_snapshot(author_id)
    query = """
Abstract

This paper studies robot subsidies in China.

Keywords: robots
JEL codes: O25

1 Introduction

China provides an ideal setting for studying industrial policy under distortion.
"""

    job_id = job_service.create_author_answer_job(author_id=author_id, query=query)["jobId"]
    final_payload = job_service.get_job(job_id)
    assert final_payload["status"] == "success"

    answer_output = job_service.get_output(job_id, "answer_json")["content"]
    assert answer_output["query_kind"] == "paper_text"
    assert answer_output["answer_source"] == "fallback"
    assert answer_output["answer_warning"]
    assert answer_output["answer_fallback_reason"] == "llm_invoke_failed"
    markdown = answer_output["answer"]["markdown"]
    assert "Keywords:" not in markdown
    assert "JEL codes" not in markdown
    assert "1 Introduction" not in markdown
