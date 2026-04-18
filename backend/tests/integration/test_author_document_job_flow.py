"""Integration tests for author/document creation and document_reload lifecycle."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient


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


def _find_document_status(client: TestClient, author_id: str, document_id: str) -> str:
    """Read document status from author's document list."""
    documents = client.get(f"/api/authors/{author_id}/documents").json()["data"]
    matched = next(item for item in documents if item["documentId"] == document_id)
    return str(matched["status"])


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
    assert payload["data"]["manuscriptsCount"] == 0


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

    job_id = payload["data"]["reloadJobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"
    assert final_payload["progress"] == 100


def test_multipart_upload_rejects_non_pdf(client: TestClient) -> None:
    """Multipart upload should reject non-pdf file extension."""
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
    assert "must end with .pdf" in payload["error"]["message"]


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


def test_document_reload_fails_when_path_not_pdf(client: TestClient) -> None:
    """Non-PDF file extension should fail reload job."""
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
    assert "must end with .pdf" in str(final_payload["errorMessage"])
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
