"""Integration tests for author/document creation and document_reload lifecycle."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.models import AuthorDocument, DocumentChapter, DocumentSegment
from app.infra.db import session_scope
from fastapi.testclient import TestClient


def _build_multi_section_pdf_bytes() -> bytes:
    import fitz

    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_textbox(
        fitz.Rect(72, 72, 540, 780),
        "Chapter 1 Foundations\n\nFirst chapter paragraph about institutional baselines.",
        fontsize=11,
    )
    second_page = document.new_page()
    second_page.insert_textbox(
        fitz.Rect(72, 72, 540, 780),
        "Chapter 2 Dynamics\n\nSecond chapter paragraph about policy propagation.",
        fontsize=11,
    )
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def _create_multi_section_pdf_path() -> str:
    input_root = Path("storage") / "test_tmp" / "test_inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    path = input_root / f"{uuid4()}-multi-section.pdf"
    path.write_bytes(_build_multi_section_pdf_bytes())
    return str(path)


def _wait_job_status(
    client: TestClient, job_id: str, expected: str, max_attempts: int = 200
) -> dict[str, Any]:
    """Poll job until it reaches expected terminal status."""
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


def _find_document_status(client: TestClient, author_id: str, document_id: str) -> str:
    """Read document status from author's document list."""
    documents = client.get(f"/api/authors/{author_id}/documents").json()["data"]
    matched = next(item for item in documents if item["documentId"] == document_id)
    return str(matched["status"])


def _list_document_chapters(
    client: TestClient, author_id: str, document_id: str
) -> list[dict[str, Any]]:
    response = client.get(f"/api/authors/{author_id}/documents/{document_id}/chapters")
    return list(response.json()["data"])


def _list_chapter_segments(
    client: TestClient, author_id: str, document_id: str, chapter_id: str
) -> list[dict[str, Any]]:
    response = client.get(
        f"/api/authors/{author_id}/documents/{document_id}/chapters/{chapter_id}/segments"
    )
    return list(response.json()["data"])


def test_create_author(client: TestClient) -> None:
    """Author create endpoint should return camelCase payload."""
    response = client.post(
        "/api/authors",
        json={
            "authorName": "Friedrich Hayek",
            "school": "Austrian School",
            "avatarUrl": "https://example.com/hayek.png",
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["authorName"] == "Friedrich Hayek"
    assert payload["data"]["language"] == "english"
    assert payload["data"]["manuscriptsCount"] == 0


def test_create_author_with_chinese_language(client: TestClient) -> None:
    """Author create endpoint should persist explicit chinese language choice."""
    response = client.post(
        "/api/authors",
        json={
            "authorName": "约翰·梅纳德·凯恩斯",
            "language": "chinese",
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["language"] == "chinese"


def test_upload_document_creates_reload_job(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """Uploading a valid local PDF should create and complete document_reload job."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "John Hicks", "school": "Neoclassical", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    pdf_uri = create_test_pdf("value-and-capital.pdf")

    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Value and Capital", "pdfUri": pdf_uri},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["documentId"]
    assert payload["data"]["reloadJobId"]
    assert payload["data"]["documentKind"] == "book"

    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"
    assert final_payload["currentStage"] == "segment_sync"
    assert final_payload["progress"] == 100


def test_multipart_upload_document_creates_reload_job(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """Uploading a PDF file via multipart should create and complete reload job."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Multipart Author", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    pdf_uri = create_test_pdf("multipart-upload.pdf")
    pdf_path = Path(pdf_uri)
    pdf_bytes = pdf_path.read_bytes()

    upload_response = client.post(
        f"/api/authors/{author_id}/documents/upload",
        data={"bookTitle": "Multipart Book"},
        files={"file": ("multipart-upload.pdf", pdf_bytes, "application/pdf")},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["documentId"]
    assert payload["data"]["reloadJobId"]
    assert payload["data"]["documentKind"] == "book"

    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"
    assert final_payload["progress"] == 100


def test_upload_epub_document_creates_reload_job(
    client: TestClient,
    create_test_epub: Callable[[str], str],
) -> None:
    """Uploading a valid local EPUB should create and complete document_reload job."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "EPUB Author", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    epub_uri = create_test_epub("big-country-big-city.epub")

    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Big Country Big City", "pdfUri": epub_uri},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["documentId"]
    assert payload["data"]["reloadJobId"]
    assert payload["data"]["documentKind"] == "book"

    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"
    assert final_payload["currentStage"] == "segment_sync"
    assert final_payload["progress"] == 100


def test_multipart_upload_epub_document_creates_reload_job(
    client: TestClient,
    create_test_epub: Callable[[str], str],
) -> None:
    """Uploading an EPUB file via multipart should create and complete reload job."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Multipart EPUB Author", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    epub_uri = create_test_epub("multipart-upload.epub")
    epub_path = Path(epub_uri)
    epub_bytes = epub_path.read_bytes()

    upload_response = client.post(
        f"/api/authors/{author_id}/documents/upload",
        data={"bookTitle": "Multipart EPUB Book"},
        files={"file": ("multipart-upload.epub", epub_bytes, "application/epub+zip")},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["documentId"]
    assert payload["data"]["reloadJobId"]
    assert payload["data"]["documentKind"] == "book"

    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"
    assert final_payload["progress"] == 100


def test_multipart_upload_markdown_document_creates_reload_job(
    client: TestClient,
    create_test_markdown: Callable[[str, str | None], str],
) -> None:
    """Uploading a Markdown file via multipart should create segments in one chapter."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Multipart Markdown Author", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    markdown_uri = create_test_markdown("multipart-upload.md")
    markdown_path = Path(markdown_uri)
    markdown_bytes = markdown_path.read_bytes()

    upload_response = client.post(
        f"/api/authors/{author_id}/documents/upload",
        data={"bookTitle": "Multipart Markdown Book"},
        files={"file": ("multipart-upload.md", markdown_bytes, "text/markdown")},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["documentId"]
    assert payload["data"]["reloadJobId"]
    assert payload["data"]["documentKind"] == "book"

    document_id = payload["data"]["documentId"]
    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"
    assert final_payload["progress"] == 100
    assert _find_document_status(client, author_id, document_id) == "active"

    chapters = _list_document_chapters(client, author_id, document_id)
    assert len(chapters) == 1
    assert chapters[0]["chapterTitle"] == "Markdown Import Title"

    segments = _list_chapter_segments(client, author_id, document_id, chapters[0]["chapterId"])
    assert segments
    assert any("Section Context" in str(item["content"]) for item in segments)


def test_multipart_upload_paper_pdf_creates_single_chapter(
    client: TestClient,
) -> None:
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Multipart Paper PDF Author", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]

    upload_response = client.post(
        f"/api/authors/{author_id}/documents/upload",
        data={"bookTitle": "Paper PDF Title", "documentKind": "paper"},
        files={"file": ("paper-upload.pdf", _build_multi_section_pdf_bytes(), "application/pdf")},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["documentKind"] == "paper"

    document_id = payload["data"]["documentId"]
    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"

    chapters = _list_document_chapters(client, author_id, document_id)
    assert len(chapters) == 1
    assert chapters[0]["chapterTitle"] == "Paper PDF Title"

    segments = _list_chapter_segments(client, author_id, document_id, chapters[0]["chapterId"])
    merged_content = "\n".join(str(item["content"]) for item in segments)
    assert "First chapter paragraph" in merged_content
    assert "Second chapter paragraph" in merged_content


def test_multipart_upload_paper_markdown_creates_single_chapter(
    client: TestClient,
    create_test_markdown: Callable[[str, str | None], str],
) -> None:
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Multipart Paper Markdown Author", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    markdown_uri = create_test_markdown("multipart-paper-upload.md")
    markdown_bytes = Path(markdown_uri).read_bytes()

    upload_response = client.post(
        f"/api/authors/{author_id}/documents/upload",
        data={"bookTitle": "Paper Markdown Title", "documentKind": "paper"},
        files={"file": ("multipart-paper-upload.md", markdown_bytes, "text/markdown")},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["data"]["documentKind"] == "paper"

    document_id = payload["data"]["documentId"]
    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"

    chapters = _list_document_chapters(client, author_id, document_id)
    assert len(chapters) == 1
    assert chapters[0]["chapterTitle"] == "Paper Markdown Title"


def test_multipart_upload_paper_epub_creates_single_chapter(
    client: TestClient,
    create_test_epub: Callable[[str], str],
) -> None:
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Multipart Paper EPUB Author", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    epub_uri = create_test_epub("multipart-paper-upload.epub")
    epub_bytes = Path(epub_uri).read_bytes()

    upload_response = client.post(
        f"/api/authors/{author_id}/documents/upload",
        data={"bookTitle": "Paper EPUB Title", "documentKind": "paper"},
        files={"file": ("multipart-paper-upload.epub", epub_bytes, "application/epub+zip")},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["data"]["documentKind"] == "paper"

    document_id = payload["data"]["documentId"]
    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"

    chapters = _list_document_chapters(client, author_id, document_id)
    assert len(chapters) == 1
    assert chapters[0]["chapterTitle"] == "Paper EPUB Title"


def test_multipart_upload_rejects_unsupported_document(client: TestClient) -> None:
    """Multipart upload should reject unsupported document extensions."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Multipart Bad Suffix", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]

    upload_response = client.post(
        f"/api/authors/{author_id}/documents/upload",
        data={"bookTitle": "Bad Upload"},
        files={"file": ("not_pdf.txt", b"plain-text", "text/plain")},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 422
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert "must end with .pdf, .epub, or .md" in payload["error"]["message"]


def test_multipart_upload_returns_404_when_author_missing(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """Multipart upload should return 404 for missing author."""
    pdf_uri = create_test_pdf("missing-author-upload.pdf")
    pdf_bytes = Path(pdf_uri).read_bytes()

    upload_response = client.post(
        "/api/authors/not-found-author/documents/upload",
        data={"bookTitle": "Missing Author Book"},
        files={"file": ("missing-author-upload.pdf", pdf_bytes, "application/pdf")},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 404
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["message"] == "author not found"


def test_poll_job_status_contract(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """Job polling response should keep required contract fields."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Milton Friedman", "school": "Chicago School", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    pdf_uri = create_test_pdf("capitalism-and-freedom.pdf")

    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Capitalism and Freedom", "pdfUri": pdf_uri},
    )
    job_id = upload_response.json()["data"]["reloadJobId"]

    response = client.get(f"/api/jobs/{job_id}")
    payload = response.json()["data"]
    assert response.status_code == 200
    assert "status" in payload
    assert "currentStage" in payload
    assert "progress" in payload
    assert "errorMessage" in payload
    assert "retryable" in payload
    assert "outputsReady" in payload


def test_document_reload_fails_when_pdf_path_missing(client: TestClient) -> None:
    """Missing file path should fail reload job with actionable error."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Missing Path", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    missing_path = str((Path("storage") / "test_inputs" / f"{uuid4()}-missing.pdf").resolve())

    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Broken Path", "pdfUri": missing_path},
    )
    payload = upload_response.json()["data"]

    final_payload = _wait_job_status(client, payload["reloadJobId"], "failed")
    assert final_payload["status"] == "failed"
    assert "pdf path does not exist" in str(final_payload["errorMessage"])
    assert final_payload["outputsReady"] is False
    assert _find_document_status(client, author_id, payload["documentId"]) == "failed"


def test_list_documents_recovers_stale_processing_document_with_segments(
    client: TestClient,
) -> None:
    """Document list should recover zombie processing rows with no live reload job."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Zombie Processing", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    document_id = str(uuid4())

    with session_scope() as session:
        session.add(
            AuthorDocument(
                document_id=document_id,
                author_id=author_id,
                book_title="Recovered Book",
                pdf_uri="memory://recovered.md",
                status="processing",
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        )
        session.add(
            DocumentChapter(
                chapter_id="recovered-chapter-01",
                document_id=document_id,
                chapter_title="Recovered Chapter",
                order_index=0,
                is_deleted=False,
                deleted_at=None,
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        )
        session.add(
            DocumentSegment(
                segment_id=str(uuid4()),
                document_id=document_id,
                chapter_id="recovered-chapter-01",
                chunk_id="recovered-chunk-01",
                content="Recovered content",
                order_index=0,
                is_deleted=False,
                deleted_at=None,
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        )

    documents = client.get(f"/api/authors/{author_id}/documents").json()["data"]
    recovered = next(item for item in documents if item["documentId"] == document_id)
    assert recovered["status"] == "active"

    with session_scope() as session:
        document = session.get(AuthorDocument, document_id)
        assert document is not None
        assert document.status == "active"


def test_document_reload_fails_when_path_not_supported_document(client: TestClient) -> None:
    """Unsupported file extension should fail reload job."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Bad Suffix", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]

    input_root = Path("storage") / "test_inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    text_path = (input_root / f"{uuid4()}-not-a-pdf.txt").resolve()
    text_path.write_text("plain text", encoding="utf-8")

    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Wrong Type", "pdfUri": str(text_path)},
    )
    payload = upload_response.json()["data"]

    final_payload = _wait_job_status(client, payload["reloadJobId"], "failed")
    assert final_payload["status"] == "failed"
    assert "must end with .pdf, .epub, or .md" in str(final_payload["errorMessage"])
    assert final_payload["outputsReady"] is False
    assert _find_document_status(client, author_id, payload["documentId"]) == "failed"


def test_document_reload_fails_when_pdf_has_no_extractable_segments(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """Empty/invalid extraction should fail reload job instead of writing fallback segments."""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Empty PDF", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    empty_pdf_uri = create_test_pdf("empty.pdf", blocks=[])

    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "No Segments", "pdfUri": empty_pdf_uri},
    )
    payload = upload_response.json()["data"]

    final_payload = _wait_job_status(client, payload["reloadJobId"], "failed")
    assert final_payload["status"] == "failed"
    assert "no extractable segments" in str(final_payload["errorMessage"])
    assert final_payload["outputsReady"] is False
    assert _find_document_status(client, author_id, payload["documentId"]) == "failed"


def test_reload_document_defaults_to_book_when_document_kind_missing(
    client: TestClient,
) -> None:
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Legacy Kind Author", "school": "Test", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    pdf_uri = _create_multi_section_pdf_path()
    document_id = str(uuid4())

    with session_scope() as session:
        session.add(
            AuthorDocument(
                document_id=document_id,
                author_id=author_id,
                book_title="Legacy Kind Book",
                pdf_uri=pdf_uri,
                document_kind="",
                status="processing",
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:00:00+00:00",
            )
        )

    reload_response = client.post(f"/api/authors/{author_id}/documents/{document_id}/reload")
    assert reload_response.status_code == 200
    job_id = reload_response.json()["data"]["reloadJobId"]
    final_payload = _wait_job_status(client, job_id, "success")
    assert final_payload["status"] == "success"

    chapters = _list_document_chapters(client, author_id, document_id)
    assert len(chapters) >= 2
