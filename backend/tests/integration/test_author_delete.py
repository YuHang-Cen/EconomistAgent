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


def _seed_latest_snapshot_for_documents(
    author_id: str,
    *,
    document_a: tuple[str, str, str],
    document_b: tuple[str, str, str],
) -> dict[str, str]:
    snapshot_id = str(uuid4())
    root = storage.snapshot_root(author_id=author_id, snapshot_id=snapshot_id)
    doc_a_id, section_a_id, title_a = document_a
    doc_b_id, section_b_id, title_b = document_b

    method_analysis = {
        "chunks": [
            {
                "chunk_id": 1,
                "section_id": section_a_id,
                "section_title": title_a,
                "document_id": doc_a_id,
            },
            {
                "chunk_id": 2,
                "section_id": section_b_id,
                "section_title": title_b,
                "document_id": doc_b_id,
            },
        ],
        "errors": [],
    }
    main_skill_json = {
        "main_skills": [
            {
                "section_id": section_a_id,
                "main_skill_id": "main_skill_001",
                "section_title": title_a,
                "document_id": doc_a_id,
                "book_title": "Delete Book A",
                "chapter_title": title_a,
                "source_context": {
                    "document_id": doc_a_id,
                    "book_title": "Delete Book A",
                    "chapter_title": title_a,
                },
                "pattern_summary": {"name": "Skill A"},
                "confidence": 0.5,
            },
            {
                "section_id": section_b_id,
                "main_skill_id": "main_skill_002",
                "section_title": title_b,
                "document_id": doc_b_id,
                "book_title": "Delete Book B",
                "chapter_title": title_b,
                "source_context": {
                    "document_id": doc_b_id,
                    "book_title": "Delete Book B",
                    "chapter_title": title_b,
                },
                "pattern_summary": {"name": "Skill B"},
                "confidence": 0.6,
            },
        ]
    }
    sub_skill_json = {
        "sub_skills": [
            {
                "section_id": section_a_id,
                "main_skill_id": "main_skill_001",
                "document_id": doc_a_id,
                "source_context": {
                    "document_id": doc_a_id,
                    "book_title": "Delete Book A",
                    "chapter_title": title_a,
                },
                "name": "Sub A",
                "normalized_pattern": "pattern-a",
            },
            {
                "section_id": section_b_id,
                "main_skill_id": "main_skill_002",
                "document_id": doc_b_id,
                "source_context": {
                    "document_id": doc_b_id,
                    "book_title": "Delete Book B",
                    "chapter_title": title_b,
                },
                "name": "Sub B",
                "normalized_pattern": "pattern-b",
            },
        ]
    }
    main_skills_md_json = [
        {
            "main_skill_id": "main_skill_001",
            "section_id": section_a_id,
            "section_title": title_a,
            "document_id": doc_a_id,
            "source_context": {
                "document_id": doc_a_id,
                "book_title": "Delete Book A",
                "chapter_title": title_a,
            },
            "name": "Skill A",
            "file_name": "main_skill_001.md",
            "markdown": "MAIN A",
        },
        {
            "main_skill_id": "main_skill_002",
            "section_id": section_b_id,
            "section_title": title_b,
            "document_id": doc_b_id,
            "source_context": {
                "document_id": doc_b_id,
                "book_title": "Delete Book B",
                "chapter_title": title_b,
            },
            "name": "Skill B",
            "file_name": "main_skill_002.md",
            "markdown": "MAIN B",
        },
    ]
    sub_skills_md_json = [
        {
            "main_skill_id": "main_skill_001",
            "section_id": section_a_id,
            "document_id": doc_a_id,
            "source_context": {
                "document_id": doc_a_id,
                "book_title": "Delete Book A",
                "chapter_title": title_a,
            },
            "name": "Sub A",
            "normalized_pattern": "pattern-a",
            "file_name": "sub_a.md",
            "markdown": "SUB A",
        },
        {
            "main_skill_id": "main_skill_002",
            "section_id": section_b_id,
            "document_id": doc_b_id,
            "source_context": {
                "document_id": doc_b_id,
                "book_title": "Delete Book B",
                "chapter_title": title_b,
            },
            "name": "Sub B",
            "normalized_pattern": "pattern-b",
            "file_name": "sub_b.md",
            "markdown": "SUB B",
        },
    ]

    outputs = {
        "method_analysis_json": storage.write_json(root / "method_analysis.json", method_analysis),
        "main_skill_json": storage.write_json(root / "main_skill.json", main_skill_json),
        "sub_skill_json": storage.write_json(root / "sub_skill.json", sub_skill_json),
        "main_skills_md_json": storage.write_json(root / "main_skills_md.json", main_skills_md_json),
        "sub_skills_md_json": storage.write_json(root / "sub_skills_md.json", sub_skills_md_json),
        "sub_skills_md_zip": storage.write_zip_from_files(
            root / "sub_skills_md.zip",
            [("sub_a.md", "SUB A"), ("sub_b.md", "SUB B")],
        ),
    }

    with session_scope() as session:
        session.add(
            AuthorSkillSnapshot(
                snapshot_id=snapshot_id,
                author_id=author_id,
                is_latest=True,
                outputs_json=json.dumps(outputs),
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
    return outputs


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


def test_delete_document_cleans_related_rows_storage_and_latest_snapshot(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    author_id = _create_author(client, name="Delete One Document")

    upload_a = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Delete Book A", "pdfUri": create_test_pdf("delete-doc-a.pdf")},
    ).json()["data"]
    upload_b = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Delete Book B", "pdfUri": create_test_pdf("delete-doc-b.pdf")},
    ).json()["data"]
    document_a_id = upload_a["documentId"]
    document_b_id = upload_b["documentId"]
    _wait_job_status(client, upload_a["reloadJobId"], "success")
    _wait_job_status(client, upload_b["reloadJobId"], "success")

    with session_scope() as session:
        chapter_rows = session.execute(
            select(DocumentChapter.document_id, DocumentChapter.chapter_id)
            .where(DocumentChapter.document_id.in_([document_a_id, document_b_id]))
            .order_by(DocumentChapter.document_id.asc(), DocumentChapter.order_index.asc())
        ).all()
    chapter_map = {
        row.document_id: row.chapter_id
        for row in chapter_rows
    }

    outputs = _seed_latest_snapshot_for_documents(
        author_id,
        document_a=(document_a_id, chapter_map[document_a_id], "Delete Book A"),
        document_b=(document_b_id, chapter_map[document_b_id], "Delete Book B"),
    )

    delete_response = client.delete(f"/api/authors/{author_id}/documents/{document_a_id}")
    payload = delete_response.json()
    assert delete_response.status_code == 200
    assert payload["data"]["deleted"] is True
    assert payload["data"]["documentId"] == document_a_id
    assert not (storage.author_root(author_id) / "documents" / document_a_id).exists()

    documents_after = client.get(f"/api/authors/{author_id}/documents").json()["data"]
    assert {item["documentId"] for item in documents_after} == {document_b_id}

    with session_scope() as session:
        deleted_document_count = session.execute(
            select(func.count()).select_from(AuthorDocument).where(AuthorDocument.document_id == document_a_id)
        ).scalar_one()
        kept_document_count = session.execute(
            select(func.count()).select_from(AuthorDocument).where(AuthorDocument.document_id == document_b_id)
        ).scalar_one()
        deleted_chapter_count = session.execute(
            select(func.count()).select_from(DocumentChapter).where(DocumentChapter.document_id == document_a_id)
        ).scalar_one()
        kept_chapter_count = session.execute(
            select(func.count()).select_from(DocumentChapter).where(DocumentChapter.document_id == document_b_id)
        ).scalar_one()
        deleted_segment_count = session.execute(
            select(func.count()).select_from(DocumentSegment).where(DocumentSegment.document_id == document_a_id)
        ).scalar_one()
        kept_segment_count = session.execute(
            select(func.count()).select_from(DocumentSegment).where(DocumentSegment.document_id == document_b_id)
        ).scalar_one()

    assert deleted_document_count == 0
    assert kept_document_count == 1
    assert deleted_chapter_count == 0
    assert kept_chapter_count > 0
    assert deleted_segment_count == 0
    assert kept_segment_count > 0

    main_skill_payload = json.loads(
        storage.resolve_storage_uri(outputs["main_skill_json"]).read_text(encoding="utf-8")
    )
    assert {item["document_id"] for item in main_skill_payload["main_skills"]} == {document_b_id}

    sub_skill_payload = json.loads(
        storage.resolve_storage_uri(outputs["sub_skill_json"]).read_text(encoding="utf-8")
    )
    assert {item["document_id"] for item in sub_skill_payload["sub_skills"]} == {document_b_id}

    main_md_payload = json.loads(
        storage.resolve_storage_uri(outputs["main_skills_md_json"]).read_text(encoding="utf-8")
    )
    assert {item["document_id"] for item in main_md_payload} == {document_b_id}

    sub_md_payload = json.loads(
        storage.resolve_storage_uri(outputs["sub_skills_md_json"]).read_text(encoding="utf-8")
    )
    assert {item["document_id"] for item in sub_md_payload} == {document_b_id}

    method_analysis_payload = json.loads(
        storage.resolve_storage_uri(outputs["method_analysis_json"]).read_text(encoding="utf-8")
    )
    assert {item["document_id"] for item in method_analysis_payload["chunks"]} == {document_b_id}


def test_delete_document_returns_404_for_missing_or_wrong_author(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    author_a_id = _create_author(client, name="Delete Doc Owner A")
    author_b_id = _create_author(client, name="Delete Doc Owner B")
    upload = client.post(
        f"/api/authors/{author_a_id}/documents",
        json={"bookTitle": "Owner A Book", "pdfUri": create_test_pdf("owner-a-book.pdf")},
    ).json()["data"]

    wrong_author_response = client.delete(
        f"/api/authors/{author_b_id}/documents/{upload['documentId']}"
    )
    assert wrong_author_response.status_code == 404
    assert wrong_author_response.json()["error"]["code"] == "NOT_FOUND"

    missing_document_response = client.delete(
        f"/api/authors/{author_a_id}/documents/not-found-document"
    )
    assert missing_document_response.status_code == 404
    assert missing_document_response.json()["error"]["code"] == "NOT_FOUND"


def test_delete_document_cancels_non_terminal_reload_jobs_and_keeps_records(client: TestClient) -> None:
    author_id = _create_author(client, name="Delete Doc Jobs")

    with session_scope() as session:
        now = "2026-01-01T00:00:00+00:00"
        document = AuthorDocument(
            document_id=str(uuid4()),
            author_id=author_id,
            book_title="Processing Book",
            pdf_uri="memory://processing.pdf",
            status="processing",
            created_at=now,
            updated_at=now,
        )
        session.add(document)
        session.flush()
        document_id = document.document_id

    queued_job_id = job_service.create_document_reload_job(
        author_id=author_id,
        document_id=document_id,
        auto_run=False,
    )["jobId"]
    running_job_id = job_service.create_document_reload_job(
        author_id=author_id,
        document_id=document_id,
        auto_run=False,
    )["jobId"]

    with session_scope() as session:
        running_job = session.get(PipelineJob, running_job_id)
        assert running_job is not None
        running_job.status = "running"

    delete_response = client.delete(f"/api/authors/{author_id}/documents/{document_id}")
    assert delete_response.status_code == 200

    queued_payload = client.get(f"/api/jobs/{queued_job_id}").json()["data"]
    running_payload = client.get(f"/api/jobs/{running_job_id}").json()["data"]
    assert queued_payload["status"] == "canceled"
    assert queued_payload["errorMessage"] == "document deleted"
    assert running_payload["status"] == "canceled"
    assert running_payload["errorMessage"] == "document deleted"

    with session_scope() as session:
        job_count = session.execute(
            select(func.count())
            .select_from(PipelineJob)
            .where(PipelineJob.job_id.in_([queued_job_id, running_job_id]))
        ).scalar_one()
    assert job_count == 2


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
