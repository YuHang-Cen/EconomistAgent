"""Integration tests for DELETE /api/authors/{author_id}."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from app.domain.models import (
    Author,
    AuthorDocument,
    AuthorSkillSnapshot,
    DocumentChapter,
    DocumentSegment,
    PipelineJob,
)
from app.infra import storage
from app.infra.db import session_scope
from app.services import job_service
from fastapi.testclient import TestClient
from sqlalchemy import func, select


def _wait_job_status(
    client: TestClient, job_id: str, expected: str, max_attempts: int = 15
) -> dict[str, Any]:
    """Poll job until it reaches expected terminal status."""
    payload: dict[str, Any] = {}
    for _ in range(max_attempts):
        response = client.get(f"/api/jobs/{job_id}")
        payload = response.json()["data"]
        if payload.get("status") == expected:
            return payload
    return payload


def _create_author(client: TestClient, name: str = "Delete Author") -> str:
    """Create author and return author_id."""
    response = client.post(
        "/api/authors",
        json={"authorName": name, "school": "test", "avatarUrl": ""},
    )
    return response.json()["data"]["authorId"]


def test_delete_author_without_documents(client: TestClient) -> None:
    """Deleting an author without documents should succeed and be idempotent-safe via 404."""
    author_id = _create_author(client, name="Delete Empty")

    delete_response = client.delete(f"/api/authors/{author_id}")
    payload = delete_response.json()
    assert delete_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["deleted"] is True

    authors_after = client.get("/api/authors").json()["data"]
    author_ids = {item["authorId"] for item in authors_after}
    assert author_id not in author_ids

    missing_response = client.delete(f"/api/authors/{author_id}")
    missing_payload = missing_response.json()
    assert missing_response.status_code == 404
    assert missing_payload["error"]["code"] == "NOT_FOUND"


def test_delete_author_with_documents_cleans_related_data_and_storage(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """Deleting an author should hard-delete related rows and storage directory."""
    author_id = _create_author(client, name="Delete With Docs")

    pdf_uri = create_test_pdf("delete-author.pdf")
    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Delete Book", "pdfUri": pdf_uri},
    )
    upload_payload = upload_response.json()["data"]
    document_id = upload_payload["documentId"]
    reload_job_id = upload_payload["reloadJobId"]
    _wait_job_status(client, reload_job_id, "success")

    snapshot_id = str(uuid4())
    snapshot_dir = storage.snapshot_root(author_id=author_id, snapshot_id=snapshot_id)
    method_uri = storage.write_json(snapshot_dir / "method_analysis.json", {"chunks": [], "errors": []})
    with session_scope() as session:
        session.add(
            AuthorSkillSnapshot(
                snapshot_id=snapshot_id,
                author_id=author_id,
                is_latest=True,
                outputs_json=json.dumps({"method_analysis_json": method_uri}),
                created_at="2026-01-01T00:00:00+00:00",
            )
        )

    assert storage.author_root(author_id).exists()

    delete_response = client.delete(f"/api/authors/{author_id}")
    payload = delete_response.json()
    assert delete_response.status_code == 200
    assert payload["data"]["deleted"] is True
    assert not storage.author_root(author_id).exists()

    with session_scope() as session:
        author_count = session.execute(
            select(func.count()).select_from(Author).where(Author.author_id == author_id)
        ).scalar_one()
        document_count = session.execute(
            select(func.count()).select_from(AuthorDocument).where(AuthorDocument.author_id == author_id)
        ).scalar_one()
        chapter_count = session.execute(
            select(func.count()).select_from(DocumentChapter).where(DocumentChapter.document_id == document_id)
        ).scalar_one()
        segment_count = session.execute(
            select(func.count()).select_from(DocumentSegment).where(DocumentSegment.document_id == document_id)
        ).scalar_one()
        snapshot_count = session.execute(
            select(func.count())
            .select_from(AuthorSkillSnapshot)
            .where(AuthorSkillSnapshot.author_id == author_id)
        ).scalar_one()

    assert author_count == 0
    assert document_count == 0
    assert chapter_count == 0
    assert segment_count == 0
    assert snapshot_count == 0


def test_delete_author_cancels_non_terminal_jobs_and_keeps_job_records(
    client: TestClient,
) -> None:
    """Deleting author should cancel queued/running jobs and keep them queryable."""
    author_id = _create_author(client, name="Delete Jobs")

    queued_job_id = job_service.create_author_skills_job(author_id=author_id, auto_run=False)["jobId"]
    running_job_id = job_service.create_author_answer_job(
        author_id=author_id,
        query="explain",
        auto_run=False,
    )["jobId"]

    with session_scope() as session:
        running_job = session.get(PipelineJob, running_job_id)
        assert running_job is not None
        running_job.status = "running"

    delete_response = client.delete(f"/api/authors/{author_id}")
    assert delete_response.status_code == 200

    queued_payload = client.get(f"/api/jobs/{queued_job_id}").json()["data"]
    running_payload = client.get(f"/api/jobs/{running_job_id}").json()["data"]

    assert queued_payload["status"] == "canceled"
    assert queued_payload["finishedAt"] is not None
    assert queued_payload["errorMessage"] == "author deleted"

    assert running_payload["status"] == "canceled"
    assert running_payload["finishedAt"] is not None
    assert running_payload["errorMessage"] == "author deleted"

    with session_scope() as session:
        job_count = session.execute(
            select(func.count())
            .select_from(PipelineJob)
            .where(PipelineJob.job_id.in_([queued_job_id, running_job_id]))
        ).scalar_one()
    assert job_count == 2
