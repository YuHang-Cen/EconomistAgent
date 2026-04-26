"""Integration tests for author job list API and modelConfig passthrough."""

from __future__ import annotations

import json
from typing import Any

from app.domain.models import PipelineJob
from app.infra.db import session_scope
from app.infra.settings import get_settings
from app.services import job_service
from fastapi.testclient import TestClient


def _create_author(client: TestClient, name: str, *, language: str = "english") -> str:
    response = client.post(
        "/api/authors",
        json={
            "authorName": name,
            "school": "Cambridge",
            "language": language,
            "avatarUrl": "https://example.com/avatar.png",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["authorId"]


def _set_job_status(job_id: str, status: str) -> None:
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        assert job is not None
        job.status = status
        job.updated_at = "2026-04-18T00:00:00+00:00"
        if status in {"failed", "success", "canceled"}:
            job.finished_at = "2026-04-18T00:00:01+00:00"
        if status == "failed":
            job.error_message = "forced-failure"


def test_list_author_jobs_supports_filter_and_cursor(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    """GET /api/authors/{author_id}/jobs should support filters + cursor pagination."""
    monkeypatch.setattr(job_service, "_dispatch_job", lambda *args, **kwargs: None)

    author_a = _create_author(client, "Author A")
    author_b = _create_author(client, "Author B")

    job_a1 = client.post(f"/api/authors/{author_a}/jobs/skills").json()["data"]["jobId"]
    job_a2 = client.post(
        f"/api/authors/{author_a}/jobs/answer",
        json={"query": "question one"},
    ).json()["data"]["jobId"]
    job_a3 = client.post(
        f"/api/authors/{author_a}/jobs/answer",
        json={"query": "question two"},
    ).json()["data"]["jobId"]
    _job_b = client.post(f"/api/authors/{author_b}/jobs/skills").json()["data"]["jobId"]

    _set_job_status(job_a1, "running")
    _set_job_status(job_a2, "failed")
    _set_job_status(job_a3, "queued")

    page1_response = client.get(f"/api/authors/{author_a}/jobs", params={"limit": 2})
    assert page1_response.status_code == 200
    page1_data = page1_response.json()["data"]
    assert len(page1_data["items"]) == 2
    assert page1_data["nextCursor"]

    page1_ids = [item["jobId"] for item in page1_data["items"]]
    assert set(page1_ids).issubset({job_a1, job_a2, job_a3})
    assert all(item["authorId"] == author_a for item in page1_data["items"])

    page2_response = client.get(
        f"/api/authors/{author_a}/jobs",
        params={"limit": 2, "cursor": page1_data["nextCursor"]},
    )
    assert page2_response.status_code == 200
    page2_data = page2_response.json()["data"]
    assert len(page2_data["items"]) == 1
    assert page2_data["items"][0]["jobId"] in {job_a1, job_a2, job_a3}

    answer_only_response = client.get(
        f"/api/authors/{author_a}/jobs",
        params={"jobType": "author_answer"},
    )
    assert answer_only_response.status_code == 200
    answer_items = answer_only_response.json()["data"]["items"]
    assert {item["jobType"] for item in answer_items} == {"author_answer"}
    assert {item["jobId"] for item in answer_items} == {job_a2, job_a3}

    failed_only_response = client.get(
        f"/api/authors/{author_a}/jobs",
        params={"status": "failed"},
    )
    assert failed_only_response.status_code == 200
    failed_items = failed_only_response.json()["data"]["items"]
    assert len(failed_items) == 1
    assert failed_items[0]["jobId"] == job_a2
    assert failed_items[0]["errorMessage"] == "forced-failure"


def test_job_create_model_config_passthrough_and_default(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    """skills/answer create APIs should persist modelConfig or fallback to empty dict."""
    monkeypatch.setattr(job_service, "_dispatch_job", lambda *args, **kwargs: None)
    author_id = _create_author(client, "Author Model Config")

    skills_job = client.post(
        f"/api/authors/{author_id}/jobs/skills",
        json={
            "modelConfig": {
                "provider": "deepseek",
                "modelName": "deepseek-chat",
                "apiBase": "https://api.deepseek.com",
                "apiKey": "sk-test-skills",
            }
        },
    ).json()["data"]["jobId"]
    answer_job = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={
            "query": "what is inflation",
            "modelConfig": {
                "provider": "openai",
                "modelName": "gpt-4.1-mini",
                "apiBase": "https://api.openai.com",
                "apiKey": "sk-test-answer",
            },
        },
    ).json()["data"]["jobId"]
    default_job = client.post(f"/api/authors/{author_id}/jobs/skills").json()["data"]["jobId"]

    with session_scope() as session:
        skills = session.get(PipelineJob, skills_job)
        answer = session.get(PipelineJob, answer_job)
        default = session.get(PipelineJob, default_job)
        assert skills is not None and answer is not None and default is not None

        skills_cfg = json.loads(skills.model_config_json)
        answer_cfg = json.loads(answer.model_config_json)
        default_cfg = json.loads(default.model_config_json)

    assert skills_cfg.get("provider") == "deepseek"
    assert skills_cfg.get("model_name") == "deepseek-chat"
    assert skills_cfg.get("api_base") == "https://api.deepseek.com"
    assert skills_cfg.get("api_key") == "sk-test-skills"

    assert answer_cfg.get("provider") == "openai"
    assert answer_cfg.get("model_name") == "gpt-4.1-mini"
    assert answer_cfg.get("api_base") == "https://api.openai.com"
    assert answer_cfg.get("api_key") == "sk-test-answer"

    assert default_cfg == {}


def test_job_create_requires_api_key_when_missing(client: TestClient, monkeypatch: Any) -> None:
    """skills/answer create APIs should return 422 when no model API key is configured."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "false")
    get_settings.cache_clear()
    author_id = _create_author(client, "Author Missing Key")

    skills_response = client.post(f"/api/authors/{author_id}/jobs/skills")
    assert skills_response.status_code == 422
    assert "missing model api key" in skills_response.json()["error"]["message"]

    answer_response = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={"query": "test missing key"},
    )
    assert answer_response.status_code == 422
    assert "missing model api key" in answer_response.json()["error"]["message"]

    get_settings.cache_clear()


def test_job_create_requires_api_key_message_is_localized_for_chinese_author(
    client: TestClient, monkeypatch: Any
) -> None:
    """Missing-key errors should be readable in Chinese when author language is chinese."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "false")
    get_settings.cache_clear()
    author_id = _create_author(client, "Chinese Author Missing Key", language="chinese")

    skills_response = client.post(f"/api/authors/{author_id}/jobs/skills")
    assert skills_response.status_code == 422
    assert "缺少模型 API Key" in skills_response.json()["error"]["message"]

    answer_response = client.post(
        f"/api/authors/{author_id}/jobs/answer",
        json={"query": "测试缺少 key"},
    )
    assert answer_response.status_code == 422
    assert "缺少模型 API Key" in answer_response.json()["error"]["message"]

    get_settings.cache_clear()
