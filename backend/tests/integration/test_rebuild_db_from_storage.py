"""Integration test: rebuild DB from storage after data loss."""

from __future__ import annotations

import base64
import json
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.infra import storage
from app.infra.db import Base, engine
from app.infra.db_recovery import bootstrap_database_on_startup
from app.scripts.rebuild_db_from_storage import rebuild_from_storage
from fastapi.testclient import TestClient

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+kvxkAAAAASUVORK5CYII="
)


def _wait_job_status(
    client: TestClient, job_id: str, expected: str, max_attempts: int = 200
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for _ in range(max_attempts):
        response = client.get(f"/api/jobs/{job_id}")
        payload = response.json()["data"]
        if payload.get("status") == expected:
            return payload
        if payload.get("status") in {"success", "failed", "canceled"}:
            raise AssertionError(f"job reached unexpected terminal state: {payload}")
        time.sleep(0.05)
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
    recovered_answer_job_id = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={"query": "answer should be recoverable"},
    ).json()["data"]["jobId"]
    _wait_job_status(client=client, job_id=recovered_answer_job_id, expected="success")

    # Manifests should exist in storage.
    author_meta_path = storage.author_root(author_id=author_id) / "author_meta.json"
    assert author_meta_path.exists()
    document_meta_path = (
        storage.document_root(author_id=author_id, document_id=document_id) / "document_meta.json"
    )
    assert document_meta_path.exists()
    document_meta = json.loads(document_meta_path.read_text(encoding="utf-8"))
    document_meta.pop("document_kind", None)
    document_meta_path.write_text(json.dumps(document_meta), encoding="utf-8")
    extracted_path = (
        storage.document_root(author_id=author_id, document_id=document_id)
        / "extracted_segments.json"
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
    recovered_document = next(item for item in documents if item["documentId"] == document_id)
    assert recovered_document["documentKind"] == "book"

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

    # Methodology relies on latest successful author_skills job.
    recovered_jobs_resp = client.get(
        f"/api/authors/{author_id}/jobs",
        params={"jobType": "author_skills", "status": "success", "limit": 1},
    )
    assert recovered_jobs_resp.status_code == 200
    recovered_jobs = recovered_jobs_resp.json()["data"]["items"]
    assert recovered_jobs
    recovered_job = recovered_jobs[0]
    assert recovered_job["outputsReady"] is True

    recovered_main_skill_output = client.get(
        f"/api/jobs/{recovered_job['jobId']}/outputs/main_skill_json"
    )
    assert recovered_main_skill_output.status_code == 200
    assert isinstance(recovered_main_skill_output.json()["data"]["content"], dict)

    recovered_answer_jobs_resp = client.get(
        f"/api/authors/{author_id}/jobs",
        params={"jobType": "author_answer", "status": "success", "limit": 50},
    )
    assert recovered_answer_jobs_resp.status_code == 200
    recovered_answer_jobs = recovered_answer_jobs_resp.json()["data"]["items"]
    assert any(item["jobId"] == recovered_answer_job_id for item in recovered_answer_jobs)

    recovered_answer_output = client.get(
        f"/api/jobs/{recovered_answer_job_id}/outputs/answer_json"
    )
    assert recovered_answer_output.status_code == 200
    recovered_answer_content = recovered_answer_output.json()["data"]["content"]
    assert recovered_answer_content.get("query") == "answer should be recoverable"

    # Answer should succeed using rebuilt latest snapshot.
    answer_job_id = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={"query": "test rebuild answer"},
    ).json()["data"]["jobId"]
    final_payload = _wait_job_status(client=client, job_id=answer_job_id, expected="success")
    assert final_payload["status"] == "success"


def test_bootstrap_database_on_startup_auto_recovers_when_db_empty(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    author_response = client.post(
        "/api/authors",
        json={
            "authorName": "Auto Recover Author",
            "school": "Test School",
            "avatarUrl": "https://example.com/avatar.png",
        },
    )
    author_id = author_response.json()["data"]["authorId"]

    pdf_uri = create_test_pdf("auto-recover.pdf")
    document_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Auto Recover Book", "pdfUri": pdf_uri},
    )
    payload = document_response.json()["data"]
    reload_job_id = payload["reloadJobId"]
    _wait_job_status(client=client, job_id=reload_job_id, expected="success")

    # Simulate DB loss: wipe all tables, keep storage artifacts untouched.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    bootstrap_database_on_startup(migration_runner=lambda: 0)

    authors = client.get("/api/authors").json()["data"]
    assert any(item["authorId"] == author_id for item in authors)


def test_bootstrap_auto_recovery_is_cwd_independent(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    author_response = client.post(
        "/api/authors",
        json={
            "authorName": "CWD Recover Author",
            "school": "Test School",
            "avatarUrl": "https://example.com/avatar.png",
        },
    )
    author_id = author_response.json()["data"]["authorId"]

    pdf_uri = create_test_pdf("cwd-recover.pdf")
    document_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "CWD Recover Book", "pdfUri": pdf_uri},
    )
    payload = document_response.json()["data"]
    reload_job_id = payload["reloadJobId"]
    _wait_job_status(client=client, job_id=reload_job_id, expected="success")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    current_cwd = Path.cwd()
    repo_root = Path(__file__).resolve().parents[3]
    try:
        os.chdir(repo_root)
        bootstrap_database_on_startup(migration_runner=lambda: 0)
    finally:
        os.chdir(current_cwd)

    authors = client.get("/api/authors").json()["data"]
    assert any(item["authorId"] == author_id for item in authors)


def test_rebuild_db_from_storage_recovers_local_avatar_url(client: TestClient) -> None:
    author_response = client.post(
        "/api/authors",
        json={
            "authorName": "Avatar Rebuild Author",
            "school": "Test School",
            "avatarUrl": "",
        },
    )
    author_id = author_response.json()["data"]["authorId"]

    upload_response = client.post(
        f"/api/authors/{author_id}/avatar/upload",
        files={"file": ("avatar.png", PNG_BYTES, "image/png")},
    )
    assert upload_response.status_code == 200
    avatar_url = upload_response.json()["data"]["avatarUrl"]

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    summary = rebuild_from_storage(storage_root=storage.ensure_storage_root())
    assert summary.authors >= 1

    authors = client.get("/api/authors").json()["data"]
    recovered = next(item for item in authors if item["authorId"] == author_id)
    assert recovered["avatarUrl"] == avatar_url

    public_response = client.get(avatar_url)
    assert public_response.status_code == 200
    assert public_response.headers["content-type"].startswith("image/png")


def test_rebuild_db_from_storage_warns_when_authors_path_is_not_directory() -> None:
    storage_root = Path("storage") / "test_tmp" / f"rebuild-not-dir-{uuid4()}"
    storage_root.mkdir(parents=True, exist_ok=True)
    try:
        (storage_root / "authors").write_text("not a directory", encoding="utf-8")

        summary = rebuild_from_storage(storage_root=storage_root)

        assert summary.authors == 0
        assert summary.documents == 0
        assert summary.chapters == 0
        assert summary.segments == 0
        assert summary.snapshots == 0
        assert any("not directory" in warning for warning in summary.warnings)
    finally:
        shutil.rmtree(storage_root, ignore_errors=True)
