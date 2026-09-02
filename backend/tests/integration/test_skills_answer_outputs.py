"""Integration coverage for author_skills/author_answer outputs contract."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.services import pipeline_service
from app.services.answer_with_skills import AnswerGenerationError
from app.services.llm_utils import get_effective_model_config
from fastapi.testclient import TestClient


def _wait_job_status(
    client: TestClient, job_id: str, expected: str, max_attempts: int = 200
) -> dict[str, Any]:
    """Poll until the job reaches the expected status."""
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
    pdf_uri = create_test_pdf("general-theory.pdf", None)
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
    expected_model_config = get_effective_model_config()
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
        "main_skills_md_json",
        "sub_skills_md_zip",
        "sub_skills_md_json",
    }.issubset(output_types)
    assert "main_skill_md" not in output_types

    removed_main_md_response = client.get(f"/api/jobs/{job_id}/outputs/main_skill_md")
    removed_main_md_payload: dict[str, Any] = removed_main_md_response.json()
    assert removed_main_md_response.status_code == 404
    assert removed_main_md_payload["error"]["code"] == "NOT_FOUND"

    method_output_response = client.get(f"/api/jobs/{job_id}/outputs/method_analysis_json")
    method_output = method_output_response.json()["data"]["content"]
    assert method_output_response.status_code == 200
    assert isinstance(method_output, dict)
    assert "chunks" in method_output
    assert "errors" in method_output
    assert method_output.get("model_name") == expected_model_config["model_name"]
    assert method_output.get("api_base") == expected_model_config["api_base"]

    main_skill_output_response = client.get(f"/api/jobs/{job_id}/outputs/main_skill_json")
    main_skill_output = main_skill_output_response.json()["data"]["content"]
    assert main_skill_output_response.status_code == 200
    assert isinstance(main_skill_output, dict)
    assert main_skill_output.get("model_name") == expected_model_config["model_name"]
    assert main_skill_output.get("api_base") == expected_model_config["api_base"]

    sub_skill_output_response = client.get(f"/api/jobs/{job_id}/outputs/sub_skill_json")
    sub_skill_output = sub_skill_output_response.json()["data"]["content"]
    assert sub_skill_output_response.status_code == 200
    assert isinstance(sub_skill_output, dict)
    assert sub_skill_output.get("model_name") == expected_model_config["model_name"]
    assert sub_skill_output.get("api_base") == expected_model_config["api_base"]

    main_md_output_response = client.get(f"/api/jobs/{job_id}/outputs/main_skills_md_json")
    main_md_output = main_md_output_response.json()["data"]["content"]
    assert main_md_output_response.status_code == 200
    assert isinstance(main_md_output, list)
    if main_md_output:
        first_main = main_md_output[0]
        assert "main_skill_id" in first_main
        assert "section_id" in first_main
        assert "file_name" in first_main
        assert "markdown" in first_main
        assert first_main.get("model_name") == expected_model_config["model_name"]
        assert first_main.get("api_base") == expected_model_config["api_base"]

    sub_md_output_response = client.get(f"/api/jobs/{job_id}/outputs/sub_skills_md_json")
    sub_md_output = sub_md_output_response.json()["data"]["content"]
    assert sub_md_output_response.status_code == 200
    assert isinstance(sub_md_output, list)
    if sub_md_output:
        first_sub = sub_md_output[0]
        assert "main_skill_id" in first_sub
        assert "section_id" in first_sub
        assert "name" in first_sub
        assert "file_name" in first_sub
        assert "markdown" in first_sub
        assert first_sub.get("model_name") == expected_model_config["model_name"]
        assert first_sub.get("api_base") == expected_model_config["api_base"]


def test_author_answer_job_generates_answer_json(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
    monkeypatch: Any,
) -> None:
    """author_answer should read latest snapshot and write answer_json."""
    monkeypatch.setattr(
        pipeline_service,
        "_run_answer_with_skills_with_language",
        lambda **kwargs: {
            "query": kwargs["query"],
            "selected_skill_indices": [1],
            "selected_section_ids": ["section-1"],
            "selected_skill_index": 1,
            "selected_section_id": "section-1",
            "selected_main_skill_names": ["Test main skill"],
            "selected_main_skill_name": "Test main skill",
            "selected_sub_skill_names": [],
            "selection_mode": "fallback_rule",
            "selection_warning": None,
            "answer": {
                "title": "Generated title",
                "topic": "Generated topic",
                "summary": "Generated summary",
                "markdown": "Generated markdown",
            },
        },
    )
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
    expected_model_config = get_effective_model_config()
    assert final_payload["status"] == "success"
    assert final_payload["currentStage"] == "answer"
    assert final_payload["outputsReady"] is True

    answer_output_response = client.get(f"/api/jobs/{job_id}/outputs/answer_json")
    answer_output = answer_output_response.json()["data"]["content"]
    assert answer_output_response.status_code == 200
    assert answer_output["query"] == "analyze policy mechanism and outcomes"
    assert isinstance(answer_output.get("selected_skill_indices"), list)
    assert answer_output.get("selected_skill_indices")
    assert isinstance(answer_output.get("selected_section_ids"), list)
    assert answer_output.get("selected_section_ids")
    assert isinstance(answer_output.get("selected_skill_index"), int)
    assert answer_output.get("selected_section_id")
    assert isinstance(answer_output.get("selected_main_skill_names"), list)
    assert "selected_main_skill_name" in answer_output
    assert isinstance(answer_output.get("selected_sub_skill_names"), list)
    assert answer_output.get("selection_mode") in {"llm", "fallback_rule"}
    assert "answer" in answer_output
    generated_at = answer_output.get("generated_at")
    assert isinstance(generated_at, str)
    assert generated_at.strip()
    datetime.fromisoformat(generated_at)
    assert answer_output.get("model_name") == expected_model_config["model_name"]
    assert answer_output.get("api_base") == expected_model_config["api_base"]


def test_author_answer_failure_does_not_publish_fallback_output(
    client: TestClient,
    create_test_pdf: Callable[[str, list[str] | None], str],
    monkeypatch: Any,
) -> None:
    """A generation failure must fail the job instead of publishing a fake answer."""

    def fail_answer(**kwargs: Any) -> dict[str, Any]:
        raise AnswerGenerationError("invalid_model_json")

    monkeypatch.setattr(
        pipeline_service,
        "_run_answer_with_skills_with_language",
        fail_answer,
    )
    author_id, _document_id = _create_author_and_document(client, create_test_pdf)
    skills_job_id = client.post(f"/api/authors/{author_id}/jobs/skills").json()["data"]["jobId"]
    _wait_job_status(client=client, job_id=skills_job_id, expected="success")

    answer_job_response = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={"query": "analyze policy mechanism and outcomes"},
    )
    job_id = answer_job_response.json()["data"]["jobId"]
    final_payload = _wait_job_status(client=client, job_id=job_id, expected="failed")

    assert final_payload["status"] == "failed"
    assert final_payload["outputsReady"] is False
    assert final_payload["errorMessage"] == ("answer_generation_failed:invalid_model_json")
    missing_output_response = client.get(f"/api/jobs/{job_id}/outputs/answer_json")
    assert missing_output_response.status_code == 404


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
