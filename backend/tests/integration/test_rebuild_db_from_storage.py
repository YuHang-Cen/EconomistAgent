"""Integration test: rebuild DB from storage after data loss."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.infra import storage
from app.infra.db import Base, engine
from app.scripts.rebuild_db_from_storage import rebuild_from_storage
from fastapi.testclient import TestClient


def _wait_job_status(
    client: TestClient, job_id: str, expected: str, max_attempts: int = 12
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for _ in range(max_attempts):
        response = client.get(f"/api/jobs/{job_id}")
        payload = response.json()["data"]
        if payload.get("status") == expected:
            return payload
    return payload


def test_rebuild_db_from_storage_recovers_author_document_segments_and_skills(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    author_response = client.post(
        "/api/authors",
        json={
            "authorName": "Rebuild Author",
            "school": "Test School",
            "avatarUrl": "https://example.com/avatar.png",
        },
    )
    author_id = author_response.json()["data"]["authorId"]

    pdf_uri = create_test_pdf("rebuild-source.pdf")
    document_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Rebuild Book", "pdfUri": pdf_uri},
    )
    document_payload = document_response.json()["data"]
    document_id = document_payload["documentId"]
    reload_job_id = document_payload["reloadJobId"]
    _wait_job_status(client=client, job_id=reload_job_id, expected="success")

    skills_job_id = client.post(f"/api/authors/{author_id}/jobs/skills").json()["data"]["jobId"]
    _wait_job_status(client=client, job_id=skills_job_id, expected="success")

    # Manifests should exist in storage.
    author_meta_path = storage.author_root(author_id=author_id) / "author_meta.json"
    assert author_meta_path.exists()
    document_meta_path = storage.document_root(author_id=author_id, document_id=document_id) / "document_meta.json"
    assert document_meta_path.exists()
    extracted_path = (
        storage.document_root(author_id=author_id, document_id=document_id) / "extracted_segments.json"
    )
    assert extracted_path.exists()

    # Snapshot meta should exist for the latest snapshot directory.
    snapshots_dir = storage.author_root(author_id=author_id) / "snapshots"
    snapshot_dirs = sorted([p for p in snapshots_dir.iterdir() if p.is_dir()])
    assert snapshot_dirs
    assert (snapshot_dirs[-1] / "snapshot_meta.json").exists()

    # Simulate DB loss: wipe all tables but keep storage artifacts.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    summary = rebuild_from_storage(storage_root=storage.ensure_storage_root())
    assert summary.authors >= 1
    assert summary.documents >= 1
    assert summary.segments >= 1
    assert summary.snapshots >= 1

    # API should work again using rebuilt DB.
    authors = client.get("/api/authors").json()["data"]
    assert any(item["authorId"] == author_id for item in authors)

    documents = client.get(f"/api/authors/{author_id}/documents").json()["data"]
    assert any(item["documentId"] == document_id for item in documents)

    chapters = client.get(
        f"/api/authors/{author_id}/documents/{document_id}/chapters"
    ).json()["data"]
    assert isinstance(chapters, list)
    assert chapters

    chapter_id = chapters[0]["chapterId"]
    segments = client.get(
        f"/api/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}/segments"
    ).json()["data"]
    assert isinstance(segments, list)
    assert segments

    # Answer should succeed using rebuilt latest snapshot.
    answer_job_id = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={"query": "test rebuild answer"},
    ).json()["data"]["jobId"]
    final_payload = _wait_job_status(client=client, job_id=answer_job_id, expected="success")
    assert final_payload["status"] == "success"

