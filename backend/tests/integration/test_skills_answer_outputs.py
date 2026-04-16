"""验证 author_skills、author_answer 与 jobs outputs 的第三阶段闭环行为。"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def _create_author_and_document(client: TestClient) -> tuple[str, str]:
    """创建作者并上传文档，返回 author_id 与 document_id。"""
    author_response = client.post(
        "/api/authors",
        json={
            "authorName": "Keynes",
            "school": "Cambridge",
            "avatarUrl": "https://example.com/keynes.png",
        },
    )
    author_id = author_response.json()["data"]["authorId"]
    document_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "General Theory", "pdfUri": "memory://general-theory.pdf"},
    )
    document_id = document_response.json()["data"]["documentId"]
    return author_id, document_id


def test_author_skills_job_creates_snapshot_and_outputs(client: TestClient) -> None:
    """author_skills 任务应成功并可读取技能产物。"""
    author_id, _document_id = _create_author_and_document(client)
    skills_job_response = client.post(f"/api/authors/{author_id}/jobs/skills")
    payload = skills_job_response.json()
    assert skills_job_response.status_code == 200
    assert payload["data"]["status"] == "success"
    assert payload["data"]["currentStage"] == "render"
    assert payload["data"]["progress"] == 100
    assert payload["data"]["outputsReady"] is True

    job_id = payload["data"]["jobId"]
    outputs_response = client.get(f"/api/jobs/{job_id}/outputs")
    outputs_payload = outputs_response.json()["data"]
    output_types = {item["type"] for item in outputs_payload}
    assert {
        "main_skill_json",
        "sub_skill_json",
        "main_skill_md",
        "sub_skills_md_zip",
    }.issubset(output_types)


def test_author_answer_job_generates_answer_json(client: TestClient) -> None:
    """author_answer 应读取最新快照并生成 answer_json。"""
    author_id, _document_id = _create_author_and_document(client)
    client.post(f"/api/authors/{author_id}/jobs/skills")

    answer_job_response = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={"query": "analyze policy mechanism and outcomes"},
    )
    payload = answer_job_response.json()
    assert answer_job_response.status_code == 200
    assert payload["data"]["status"] == "success"
    assert payload["data"]["currentStage"] == "answer"
    assert payload["data"]["outputsReady"] is True

    job_id = payload["data"]["jobId"]
    answer_output_response = client.get(f"/api/jobs/{job_id}/outputs/answer_json")
    answer_output = answer_output_response.json()["data"]["content"]
    assert answer_output_response.status_code == 200
    assert answer_output["query"] == "analyze policy mechanism and outcomes"
    assert answer_output["selected_main_skill_id"] is not None
    assert "answer" in answer_output


def test_outputs_type_validation_and_not_found(client: TestClient) -> None:
    """非法产物类型应返回 INVALID_ARGUMENT，缺失产物应返回 NOT_FOUND。"""
    author_id, _document_id = _create_author_and_document(client)
    skills_job = client.post(f"/api/authors/{author_id}/jobs/skills").json()["data"]
    job_id = skills_job["jobId"]

    invalid_type_response = client.get(f"/api/jobs/{job_id}/outputs/not_real_type")
    invalid_payload: dict[str, Any] = invalid_type_response.json()
    assert invalid_type_response.status_code == 422
    assert invalid_payload["error"]["code"] == "INVALID_ARGUMENT"

    missing_output_response = client.get(f"/api/jobs/{job_id}/outputs/answer_json")
    missing_payload: dict[str, Any] = missing_output_response.json()
    assert missing_output_response.status_code == 404
    assert missing_payload["error"]["code"] == "NOT_FOUND"
