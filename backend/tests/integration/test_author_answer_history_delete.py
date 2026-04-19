"""Integration tests for deleting author_answer history."""

from __future__ import annotations

from uuid import uuid4

from app.domain.models import PipelineJob
from app.infra import storage
from app.infra.db import session_scope
from app.services import job_service
from fastapi.testclient import TestClient


def _create_author(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/authors",
        json={"authorName": name, "school": "Test", "avatarUrl": ""},
    )
    assert response.status_code == 200
    return response.json()["data"]["authorId"]


def test_delete_author_answer_history_success(client: TestClient) -> None:
    author_id = _create_author(client, "Answer Delete Success")
    job_id = job_service.create_author_answer_job(
        author_id=author_id,
        query="test query",
        auto_run=False,
    )["jobId"]

    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        assert job is not None
        job.status = "success"
        job.current_stage = "answer"
        job.finished_at = "2026-04-19T00:00:00+00:00"
        job.updated_at = "2026-04-19T00:00:00+00:00"

    answer_dir = storage.answer_root(author_id=author_id, job_id=job_id)
    (answer_dir / "answer.json").write_text('{"ok": true}', encoding="utf-8")
    assert answer_dir.exists()

    delete_response = client.delete(f"/api/authors/{author_id}/jobs/answer/{job_id}")
    delete_payload = delete_response.json()
    assert delete_response.status_code == 200
    assert delete_payload["data"]["deleted"] is True
    assert delete_payload["data"]["authorId"] == author_id
    assert delete_payload["data"]["jobId"] == job_id

    list_response = client.get(
        f"/api/authors/{author_id}/jobs",
        params={"jobType": "author_answer"},
    )
    assert list_response.status_code == 200
    listed_ids = {item["jobId"] for item in list_response.json()["data"]["items"]}
    assert job_id not in listed_ids

    get_response = client.get(f"/api/jobs/{job_id}")
    assert get_response.status_code == 404
    assert not answer_dir.exists()


def test_delete_author_answer_history_rejects_queued_or_running(client: TestClient) -> None:
    author_id = _create_author(client, "Answer Delete Conflict")
    queued_job_id = job_service.create_author_answer_job(
        author_id=author_id,
        query="queued query",
        auto_run=False,
    )["jobId"]

    queued_delete = client.delete(f"/api/authors/{author_id}/jobs/answer/{queued_job_id}")
    assert queued_delete.status_code == 409
    assert queued_delete.json()["error"]["code"] == "TASK_CONFLICT"
    assert client.get(f"/api/jobs/{queued_job_id}").status_code == 200

    running_job_id = job_service.create_author_answer_job(
        author_id=author_id,
        query="running query",
        auto_run=False,
    )["jobId"]
    with session_scope() as session:
        job = session.get(PipelineJob, running_job_id)
        assert job is not None
        job.status = "running"
        job.updated_at = "2026-04-19T00:00:00+00:00"

    running_delete = client.delete(f"/api/authors/{author_id}/jobs/answer/{running_job_id}")
    assert running_delete.status_code == 409
    assert running_delete.json()["error"]["code"] == "TASK_CONFLICT"
    assert client.get(f"/api/jobs/{running_job_id}").status_code == 200


def test_delete_author_answer_history_returns_404_for_invalid_target(client: TestClient) -> None:
    author_a = _create_author(client, "Author A")
    author_b = _create_author(client, "Author B")

    answer_job_id = job_service.create_author_answer_job(
        author_id=author_a,
        query="answer query",
        auto_run=False,
    )["jobId"]
    with session_scope() as session:
        answer_job = session.get(PipelineJob, answer_job_id)
        assert answer_job is not None
        answer_job.status = "success"
        answer_job.updated_at = "2026-04-19T00:00:00+00:00"
        answer_job.finished_at = "2026-04-19T00:00:00+00:00"

    wrong_author_delete = client.delete(f"/api/authors/{author_b}/jobs/answer/{answer_job_id}")
    assert wrong_author_delete.status_code == 404
    assert wrong_author_delete.json()["error"]["code"] == "NOT_FOUND"

    skills_job_id = job_service.create_author_skills_job(
        author_id=author_a,
        auto_run=False,
    )["jobId"]
    with session_scope() as session:
        skills_job = session.get(PipelineJob, skills_job_id)
        assert skills_job is not None
        skills_job.status = "success"
        skills_job.updated_at = "2026-04-19T00:00:00+00:00"
        skills_job.finished_at = "2026-04-19T00:00:00+00:00"

    wrong_type_delete = client.delete(f"/api/authors/{author_a}/jobs/answer/{skills_job_id}")
    assert wrong_type_delete.status_code == 404
    assert wrong_type_delete.json()["error"]["code"] == "NOT_FOUND"

    missing_job_delete = client.delete(f"/api/authors/{author_a}/jobs/answer/{uuid4()}")
    assert missing_job_delete.status_code == 404
    assert missing_job_delete.json()["error"]["code"] == "NOT_FOUND"
