"""Integration coverage for author_skills/author_answer outputs contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient


def _wait_job_status(
    client: TestClient, job_id: str, expected: str, max_attempts: int = 12
) -> dict[str, Any]:
    """Poll until the job reaches the expected status."""
    payload: dict[str, Any] = {}
    for _ in range(max_attempts):
        response = client.get(f"/api/jobs/{job_id}")
        payload = response.json()["data"]
        if payload.get("status") == expected:
            return payload
    return payload


def _create_author_and_document(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> tuple[str, str]:
    """Create author + valid document and wait for reload success."""
    author_response = client.post(
        "/api/authors",
        json={
            "authorName": "Keynes",
            "school": "Cambridge",
            "avatarUrl": "https://example.com/keynes.png",
        },
    )
    author_id = author_response.json()["data"]["authorId"]
    pdf_uri = create_test_pdf("general-theory.pdf")
    document_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "General Theory", "pdfUri": pdf_uri},
    )
    document_id = document_response.json()["data"]["documentId"]
    reload_job_id = document_response.json()["data"]["reloadJobId"]
    _wait_job_status(client=client, job_id=reload_job_id, expected="success")
    return author_id, document_id


def test_author_skills_job_creates_snapshot_and_outputs(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """author_skills should complete and expose all required outputs."""
    author_id, _document_id = _create_author_and_document(client, create_test_pdf)
    skills_job_response = client.post(f"/api/authors/{author_id}/jobs/skills")
    payload = skills_job_response.json()
    assert skills_job_response.status_code == 200

    job_id = payload["data"]["jobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"
    assert final_payload["currentStage"] == "render"
    assert final_payload["progress"] == 100
    assert final_payload["outputsReady"] is True

    outputs_response = client.get(f"/api/jobs/{job_id}/outputs")
    outputs_payload = outputs_response.json()["data"]
    output_types = {item["type"] for item in outputs_payload}
    assert {
        "method_analysis_json",
        "main_skill_json",
        "sub_skill_json",
        "main_skill_md",
        "sub_skills_md_zip",
    }.issubset(output_types)

    method_output_response = client.get(f"/api/jobs/{job_id}/outputs/method_analysis_json")
    method_output = method_output_response.json()["data"]["content"]
    assert method_output_response.status_code == 200
    assert isinstance(method_output, dict)
    assert "chunks" in method_output
    assert "errors" in method_output


def test_author_answer_job_generates_answer_json(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """author_answer should read latest snapshot and write answer_json."""
    author_id, _document_id = _create_author_and_document(client, create_test_pdf)
    skills_job_id = client.post(f"/api/authors/{author_id}/jobs/skills").json()["data"]["jobId"]
    _wait_job_status(client=client, job_id=skills_job_id, expected="success")

    answer_job_response = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={"query": "analyze policy mechanism and outcomes"},
    )
    payload = answer_job_response.json()
    assert answer_job_response.status_code == 200

    job_id = payload["data"]["jobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="success")
    assert final_payload["status"] == "success"
    assert final_payload["currentStage"] == "answer"
    assert final_payload["outputsReady"] is True

    answer_output_response = client.get(f"/api/jobs/{job_id}/outputs/answer_json")
    answer_output = answer_output_response.json()["data"]["content"]
    assert answer_output_response.status_code == 200
    assert answer_output["query"] == "analyze policy mechanism and outcomes"
    assert answer_output["selected_main_skill_id"] is not None
    assert "answer" in answer_output


def test_outputs_type_validation_and_not_found(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    """Invalid output type should 422; missing output should 404."""
    author_id, _document_id = _create_author_and_document(client, create_test_pdf)
    skills_job = client.post(f"/api/authors/{author_id}/jobs/skills").json()["data"]
    job_id = skills_job["jobId"]
    _wait_job_status(client=client, job_id=job_id, expected="success")

    invalid_type_response = client.get(f"/api/jobs/{job_id}/outputs/not_real_type")
    invalid_payload: dict[str, Any] = invalid_type_response.json()
    assert invalid_type_response.status_code == 422
    assert invalid_payload["error"]["code"] == "INVALID_ARGUMENT"

    missing_output_response = client.get(f"/api/jobs/{job_id}/outputs/answer_json")
    missing_payload: dict[str, Any] = missing_output_response.json()
    assert missing_output_response.status_code == 404
    assert missing_payload["error"]["code"] == "NOT_FOUND"
