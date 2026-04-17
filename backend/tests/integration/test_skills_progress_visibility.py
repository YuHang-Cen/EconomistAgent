"""Integration test for live progress visibility in author_skills jobs."""

from __future__ import annotations

import time
from threading import Thread
from typing import Any

from app.services import job_service
from app.services import pipeline_service
from fastapi.testclient import TestClient


def _create_author(client: TestClient, author_name: str = "Progress Visible") -> str:
    response = client.post(
        "/api/authors",
        json={"authorName": author_name, "school": "test", "avatarUrl": ""},
    )
    return response.json()["data"]["authorId"]


def test_author_skills_progress_is_visible_while_running(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    """Polling job status should observe running progress before final success."""
    author_id = _create_author(client)
    job_id = job_service.create_author_skills_job(author_id=author_id, auto_run=False)["jobId"]

    def fake_load_segments(*, session: Any, author_id: str) -> list[dict[str, Any]]:
        return [
            {
                "document_id": "doc-1",
                "chapter_id": "chapter-1",
                "chapter_title": "Chapter One",
                "chunk_id": "chunk-1",
                "content": "policy changes alter incentives and outcomes",
                "order_index": 0,
            }
        ]

    def fake_analyze_method_chunks(segments: list[dict[str, Any]]) -> dict[str, Any]:
        time.sleep(0.25)
        return {"chunks": [{"chunk_id": 1, "analysis": {}}], "errors": []}

    def fake_main_skill(method_analysis: dict[str, Any]) -> dict[str, Any]:
        time.sleep(0.25)
        return {"main_skills": [{"id": "m1", "name": "Main Skill"}]}

    def fake_sub_skill(
        main_skill_json: dict[str, Any],
        method_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        time.sleep(0.25)
        return {"sub_skills": [{"id": "s1", "main_skill_id": "m1", "name": "Sub Skill"}]}

    def fake_render(main_skill_json: dict[str, Any], sub_skill_json: dict[str, Any]) -> dict[str, Any]:
        time.sleep(0.25)
        return {
            "main_skill_md": "# Main Skill",
            "sub_skill_files": [{"name": "s1.md", "content": "sub skill details"}],
        }

    monkeypatch.setattr(pipeline_service, "_load_author_segments", fake_load_segments)
    monkeypatch.setattr(pipeline_service, "run_analyze_method_chunks", fake_analyze_method_chunks)
    monkeypatch.setattr(pipeline_service, "run_main_skill", fake_main_skill)
    monkeypatch.setattr(pipeline_service, "run_sub_skill", fake_sub_skill)
    monkeypatch.setattr(pipeline_service, "run_render", fake_render)

    worker_error: list[BaseException] = []

    def run_worker() -> None:
        try:
            job_service.execute_author_skills_job(job_id)
        except BaseException as exc:  # pragma: no cover
            worker_error.append(exc)

    worker = Thread(target=run_worker, daemon=True)
    worker.start()

    saw_running_progress = False
    deadline = time.time() + 6
    while time.time() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()["data"]
        if payload["status"] == "running" and int(payload["progress"]) >= 35:
            saw_running_progress = True
            break
        if payload["status"] in {"failed", "success", "canceled"}:
            break
        time.sleep(0.05)

    worker.join(timeout=8)

    assert not worker.is_alive()
    assert worker_error == []
    assert saw_running_progress is True

    final_payload = client.get(f"/api/jobs/{job_id}").json()["data"]
    assert final_payload["status"] == "success"
    assert final_payload["currentStage"] == "render"
    assert final_payload["progress"] == 100
    assert final_payload["outputsReady"] is True
