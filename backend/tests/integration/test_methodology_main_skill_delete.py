"""Integration tests for deleting one methodology main-skill section."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

from app.domain.enums import OutputType
from app.domain.models import AuthorSkillSnapshot
from app.infra import storage
from app.infra.db import session_scope
from app.services import job_service, pipeline_service
from fastapi.testclient import TestClient


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _create_author(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/authors",
        json={"authorName": name, "school": "Test", "avatarUrl": ""},
    )
    assert response.status_code == 200
    return response.json()["data"]["authorId"]


def _seed_latest_snapshot(author_id: str) -> dict[str, str]:
    snapshot_id = str(uuid4())
    root = storage.snapshot_root(author_id=author_id, snapshot_id=snapshot_id)

    method_analysis = {
        "chunks": [
            {"chunk_id": 1, "section_id": "section-a", "section_title": "Section A"},
            {"chunk_id": 2, "section_id": "section-b", "section_title": "Section B"},
        ],
        "errors": [],
    }
    main_skill_json = {
        "main_skills": [
            {
                "section_id": "section-a",
                "main_skill_id": "main_skill_001",
                "section_title": "Section A",
                "pattern_summary": {"name": "Skill A"},
                "confidence": 0.5,
            },
            {
                "section_id": "section-b",
                "main_skill_id": "main_skill_002",
                "section_title": "Section B",
                "pattern_summary": {"name": "Skill B"},
                "confidence": 0.6,
            },
        ]
    }
    sub_skill_json = {
        "sub_skills": [
            {
                "section_id": "section-a",
                "main_skill_id": "main_skill_001",
                "name": "Sub A",
                "normalized_pattern": "pattern-a",
            },
            {
                "section_id": "section-b",
                "main_skill_id": "main_skill_002",
                "name": "Sub B",
                "normalized_pattern": "pattern-b",
            },
        ]
    }
    main_skills_md_json = [
        {
            "main_skill_id": "main_skill_001",
            "section_id": "section-a",
            "section_title": "Section A",
            "name": "Skill A",
            "file_name": "main_skill_001.md",
            "markdown": "MAIN A",
        },
        {
            "main_skill_id": "main_skill_002",
            "section_id": "section-b",
            "section_title": "Section B",
            "name": "Skill B",
            "file_name": "main_skill_002.md",
            "markdown": "MAIN B",
        },
    ]
    sub_skills_md_json = [
        {
            "main_skill_id": "main_skill_001",
            "section_id": "section-a",
            "name": "Sub A",
            "normalized_pattern": "pattern-a",
            "file_name": "sub_a.md",
            "markdown": "SUB A",
        },
        {
            "main_skill_id": "main_skill_002",
            "section_id": "section-b",
            "name": "Sub B",
            "normalized_pattern": "pattern-b",
            "file_name": "sub_b.md",
            "markdown": "SUB B",
        },
    ]

    outputs = {
        OutputType.METHOD_ANALYSIS_JSON.value: storage.write_json(root / "method_analysis.json", method_analysis),
        OutputType.MAIN_SKILL_JSON.value: storage.write_json(root / "main_skill.json", main_skill_json),
        OutputType.SUB_SKILL_JSON.value: storage.write_json(root / "sub_skill.json", sub_skill_json),
        OutputType.MAIN_SKILLS_MD_JSON.value: storage.write_json(root / "main_skills_md.json", main_skills_md_json),
        OutputType.SUB_SKILLS_MD_JSON.value: storage.write_json(root / "sub_skills_md.json", sub_skills_md_json),
        OutputType.SUB_SKILLS_MD_ZIP.value: storage.write_zip_from_files(
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
                created_at=_now_iso(),
            )
        )
    return outputs


def _read_json_uri(uri: str) -> dict[str, object] | list[dict[str, object]]:
    path = storage.resolve_storage_uri(uri)
    return json.loads(path.read_text(encoding="utf-8"))


def test_delete_main_skill_section_updates_latest_snapshot_artifacts(client: TestClient) -> None:
    author_id = _create_author(client, "Method Delete Success")
    outputs = _seed_latest_snapshot(author_id=author_id)

    response = client.delete(f"/api/authors/{author_id}/skills/sections/section-a")
    payload = response.json()
    assert response.status_code == 200
    assert payload["data"]["deleted"] is True

    main_skill_json = _read_json_uri(outputs[OutputType.MAIN_SKILL_JSON.value])
    main_sections = {item.get("section_id") for item in main_skill_json["main_skills"]}  # type: ignore[index]
    assert main_sections == {"section-b"}

    main_skills_md_json = _read_json_uri(outputs[OutputType.MAIN_SKILLS_MD_JSON.value])
    main_md_sections = {item.get("section_id") for item in main_skills_md_json}  # type: ignore[union-attr]
    assert main_md_sections == {"section-b"}

    sub_skill_json = _read_json_uri(outputs[OutputType.SUB_SKILL_JSON.value])
    sub_sections = {item.get("section_id") for item in sub_skill_json["sub_skills"]}  # type: ignore[index]
    assert sub_sections == {"section-b"}

    sub_skills_md_json = _read_json_uri(outputs[OutputType.SUB_SKILLS_MD_JSON.value])
    sub_md_sections = {item.get("section_id") for item in sub_skills_md_json}  # type: ignore[union-attr]
    assert sub_md_sections == {"section-b"}

    method_analysis_json = _read_json_uri(outputs[OutputType.METHOD_ANALYSIS_JSON.value])
    analysis_sections = {item.get("section_id") for item in method_analysis_json["chunks"]}  # type: ignore[index]
    assert analysis_sections == {"section-b"}

    zip_path = storage.resolve_storage_uri(outputs[OutputType.SUB_SKILLS_MD_ZIP.value])
    with ZipFile(zip_path, mode="r") as zip_file:
        assert sorted(zip_file.namelist()) == ["sub_b.md"]


def test_deleted_section_can_be_regenerated_in_next_skills_job(
    client: TestClient,
    monkeypatch: object,
) -> None:
    author_id = _create_author(client, "Method Delete Regen")
    _seed_latest_snapshot(author_id=author_id)

    delete_response = client.delete(f"/api/authors/{author_id}/skills/sections/section-a")
    assert delete_response.status_code == 200

    monkeypatch.setattr(
        pipeline_service,
        "get_settings",
        lambda: SimpleNamespace(skills_batch_size=2, skills_max_main_skills=6),
    )

    def fake_load_segments(*, session: object, author_id: str) -> list[dict[str, object]]:
        _ = (session, author_id)
        return [
            {
                "document_id": "doc-1",
                "chapter_id": "section-a",
                "chapter_title": "Section A",
                "chunk_id": "a-1",
                "content": "A content",
                "order_index": 0,
            },
            {
                "document_id": "doc-1",
                "chapter_id": "section-b",
                "chapter_title": "Section B",
                "chunk_id": "b-1",
                "content": "B content",
                "order_index": 1,
            },
        ]

    def fake_analyze(segments: list[dict[str, object]]) -> dict[str, object]:
        chunks: list[dict[str, object]] = []
        seen: set[str] = set()
        for row in segments:
            section_id = str(row.get("chapter_id", "")).strip()
            if not section_id or section_id in seen:
                continue
            seen.add(section_id)
            chunks.append(
                {
                    "chunk_id": len(chunks) + 1,
                    "section_id": section_id,
                    "section_title": str(row.get("chapter_title", "")).strip(),
                    "analysis": {"methodPatterns": {}, "methodSignals": {}},
                }
            )
        return {"chunks": chunks, "errors": []}

    def fake_main_skill(
        method_analysis: dict[str, object], *, drop_low_confidence: bool = True
    ) -> dict[str, object]:
        _ = drop_low_confidence
        chunks = method_analysis.get("chunks", [])
        if not isinstance(chunks, list):
            return {"main_skills": []}
        main_skills: list[dict[str, object]] = []
        for index, item in enumerate(chunks, start=1):
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id", "")).strip()
            main_skills.append(
                {
                    "section_id": section_id,
                    "section_title": str(item.get("section_title", section_id)),
                    "main_skill_id": f"main_skill_{index:03d}",
                    "pattern_summary": {"name": f"Skill {section_id}"},
                    "confidence": 0.9,
                }
            )
        return {"main_skills": main_skills}

    def fake_sub_skill(
        main_skill_json: dict[str, object], method_analysis: dict[str, object]
    ) -> dict[str, object]:
        _ = method_analysis
        main_skills = main_skill_json.get("main_skills", [])
        if not isinstance(main_skills, list):
            return {"sub_skills": []}
        sub_skills: list[dict[str, object]] = []
        for item in main_skills:
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id", "")).strip()
            main_skill_id = str(item.get("main_skill_id", "")).strip()
            sub_skills.append(
                {
                    "section_id": section_id,
                    "main_skill_id": main_skill_id,
                    "name": f"Sub {section_id}",
                    "normalized_pattern": f"pattern-{section_id}",
                }
            )
        return {"sub_skills": sub_skills}

    def fake_render(
        main_skill_json: dict[str, object], sub_skill_json: dict[str, object]
    ) -> dict[str, object]:
        main_skills = main_skill_json.get("main_skills", [])
        sub_skills = sub_skill_json.get("sub_skills", [])
        if not isinstance(main_skills, list):
            main_skills = []
        if not isinstance(sub_skills, list):
            sub_skills = []

        main_skill_files: list[dict[str, str]] = []
        for item in main_skills:
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id", "")).strip()
            main_skill_id = str(item.get("main_skill_id", "")).strip()
            main_skill_files.append(
                {
                    "main_skill_id": main_skill_id,
                    "section_id": section_id,
                    "section_title": str(item.get("section_title", "")).strip(),
                    "name": str(item.get("pattern_summary", {}).get("name", "")).strip(),
                    "file_name": f"{main_skill_id}.md",
                    "markdown": f"MAIN::{section_id}",
                }
            )

        sub_skill_files: list[dict[str, str]] = []
        for item in sub_skills:
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id", "")).strip()
            main_skill_id = str(item.get("main_skill_id", "")).strip()
            skill_name = str(item.get("name", "")).strip() or "sub"
            file_name = f"{main_skill_id}_{skill_name}.md"
            markdown = f"SUB::{section_id}::{skill_name}"
            sub_skill_files.append(
                {
                    "name": file_name,
                    "content": markdown,
                    "file_name": file_name,
                    "skill_name": skill_name,
                    "main_skill_id": main_skill_id,
                    "section_id": section_id,
                    "normalized_pattern": str(item.get("normalized_pattern", "")).strip(),
                    "markdown": markdown,
                }
            )

        return {
            "main_skill_md": "\n".join(item["markdown"] for item in main_skill_files),
            "main_skill_files": main_skill_files,
            "sub_skill_files": sub_skill_files,
        }

    monkeypatch.setattr(pipeline_service, "_load_author_segments", fake_load_segments)
    monkeypatch.setattr(pipeline_service, "run_analyze_method_chunks", fake_analyze)
    monkeypatch.setattr(pipeline_service, "run_main_skill", fake_main_skill)
    monkeypatch.setattr(pipeline_service, "run_sub_skill", fake_sub_skill)
    monkeypatch.setattr(pipeline_service, "run_render", fake_render)

    job = job_service.create_author_skills_job(author_id=author_id, auto_run=False)
    job_service.execute_author_skills_job(job["jobId"])

    with session_scope() as session:
        latest_snapshot = (
            session.query(AuthorSkillSnapshot)
            .filter(
                AuthorSkillSnapshot.author_id == author_id,
                AuthorSkillSnapshot.is_latest.is_(True),
            )
            .order_by(AuthorSkillSnapshot.created_at.desc())
            .first()
        )
        assert latest_snapshot is not None
        outputs = json.loads(latest_snapshot.outputs_json)

    main_skill_payload = _read_json_uri(outputs[OutputType.MAIN_SKILL_JSON.value])
    section_ids = {
        str(item.get("section_id", ""))
        for item in main_skill_payload["main_skills"]  # type: ignore[index]
        if isinstance(item, dict)
    }
    assert "section-a" in section_ids
    assert "section-b" in section_ids
