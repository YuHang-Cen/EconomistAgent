"""验证作者创建、文档上传触发任务与任务轮询最小闭环。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_author(client: TestClient) -> None:
    """应能够创建作者并返回 camelCase 响应字段。"""
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


def test_upload_document_creates_reload_job(client: TestClient) -> None:
    """上传文档后应自动创建并执行 document_reload 任务。"""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "John Hicks", "school": "Neoclassical", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]

    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Value and Capital", "pdfUri": "memory://value-and-capital.pdf"},
    )
    payload = upload_response.json()
    assert upload_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["documentId"]
    assert payload["data"]["reloadJobId"]

    job_id = payload["data"]["reloadJobId"]
    job_response = client.get(f"/api/jobs/{job_id}")
    job_payload = job_response.json()
    assert job_response.status_code == 200
    assert job_payload["data"]["status"] == "success"
    assert job_payload["data"]["currentStage"] == "segment_sync"
    assert job_payload["data"]["progress"] == 100


def test_poll_job_status_contract(client: TestClient) -> None:
    """任务轮询返回必须包含约定字段。"""
    create_author_response = client.post(
        "/api/authors",
        json={"authorName": "Milton Friedman", "school": "Chicago School", "avatarUrl": ""},
    )
    author_id = create_author_response.json()["data"]["authorId"]
    upload_response = client.post(
        f"/api/authors/{author_id}/documents",
        json={"bookTitle": "Capitalism and Freedom", "pdfUri": "memory://caf.pdf"},
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
