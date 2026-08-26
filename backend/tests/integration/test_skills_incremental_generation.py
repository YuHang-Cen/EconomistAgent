"""Integration tests for incremental author_skills generation with section batching."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

from app.domain.models import (
    Author,
    AuthorDocument,
    AuthorSkillSnapshot,
    DocumentChapter,
    DocumentSegment,
    PipelineJob,
)
from app.infra import storage
from app.infra.db import session_scope
from app.services import job_service, pipeline_service


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _seed_author_with_sections(author_id: str, section_count: int) -> None:
    now = _now_iso()
    document_id = str(uuid4())

    with session_scope() as session:
        session.add(
            Author(
                author_id=author_id,
                author_name=f"Author-{author_id[:8]}",
                school=None,
                avatar_url=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            AuthorDocument(
                document_id=document_id,
                author_id=author_id,
                book_title="Incremental Book",
                pdf_uri="memory://incremental.pdf",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )

        for index in range(1, section_count + 1):
            section_id = f"section-{index:02d}"
            chapter_id = section_id
            session.add(
                DocumentChapter(
                    chapter_id=chapter_id,
                    document_id=document_id,
                    chapter_title=f"Chapter {index}",
                    order_index=index - 1,
                    is_deleted=False,
                    deleted_at=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            for segment_index in range(1, 3):
                session.add(
                    DocumentSegment(
                        segment_id=str(uuid4()),
                        document_id=document_id,
                        chapter_id=chapter_id,
                        chunk_id=f"{section_id}-chunk-{segment_index}",
                        content=f"Section {index} segment {segment_index}",
                        order_index=segment_index - 1,
                        is_deleted=False,
                        deleted_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )


def _seed_author_with_book_layout(author_id: str, books: list[tuple[str, int]]) -> None:
    now = _now_iso()

    with session_scope() as session:
        session.add(
            Author(
                author_id=author_id,
                author_name=f"Author-{author_id[:8]}",
                school=None,
                avatar_url=None,
                created_at=now,
                updated_at=now,
            )
        )

        section_number = 1
        for document_index, (book_title, chapter_count) in enumerate(books, start=1):
            document_id = f"document-{document_index:02d}"
            session.add(
                AuthorDocument(
                    document_id=document_id,
                    author_id=author_id,
                    book_title=book_title,
                    pdf_uri=f"memory://{document_id}.pdf",
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )

            for chapter_offset in range(chapter_count):
                section_id = f"section-{section_number:02d}"
                section_number += 1
                session.add(
                    DocumentChapter(
                        chapter_id=section_id,
                        document_id=document_id,
                        chapter_title=f"{book_title} Chapter {chapter_offset + 1}",
                        order_index=chapter_offset,
                        is_deleted=False,
                        deleted_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
                session.add(
                    DocumentSegment(
                        segment_id=str(uuid4()),
                        document_id=document_id,
                        chapter_id=section_id,
                        chunk_id=f"{section_id}-chunk-1",
                        content=f"{book_title} content {chapter_offset + 1}",
                        order_index=0,
                        is_deleted=False,
                        deleted_at=None,
                        created_at=now,
                        updated_at=now,
                    )
                )


def _extract_section_number(section_id: str) -> int:
    try:
        return int(section_id.split("-")[-1])
    except Exception:
        return 0


def _install_incremental_fakes(
    monkeypatch: object, batch_size: int, max_main_skills: int
) -> dict[str, int]:
    counters = {"analyze": 0, "main": 0, "sub": 0, "render": 0}

    monkeypatch.setattr(
        pipeline_service,
        "get_settings",
        lambda: SimpleNamespace(
            skills_batch_size=batch_size, skills_max_main_skills=max_main_skills
        ),
    )
    monkeypatch.setattr(pipeline_service.random, "sample", lambda seq, n: list(seq)[:n])

    def fake_analyze(segments: list[dict[str, object]]) -> dict[str, object]:
        counters["analyze"] += 1
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
                    "analysis": {
                        "methodPatterns": {},
                        "methodSignals": {},
                    },
                }
            )
        return {"chunks": chunks, "errors": []}

    def fake_main_skill(
        method_analysis: dict[str, object], *, drop_low_confidence: bool = True
    ) -> dict[str, object]:
        _ = drop_low_confidence
        counters["main"] += 1
        chunks = method_analysis.get("chunks", [])
        if not isinstance(chunks, list):
            return {"main_skills": []}

        main_skills: list[dict[str, object]] = []
        for index, chunk in enumerate(chunks, start=1):
            if not isinstance(chunk, dict):
                continue
            section_id = str(chunk.get("section_id", "")).strip()
            section_title = str(chunk.get("section_title", "")).strip() or section_id
            section_number = _extract_section_number(section_id)
            confidence = float(section_number) / 10.0
            main_skills.append(
                {
                    "section_id": section_id,
                    "main_skill_id": f"main_skill_{index:03d}",
                    "section_title": section_title,
                    "pattern_summary": {
                        "name": f"Skill {section_id}",
                        "description": f"Desc {section_id}",
                        "applicability": f"Apply {section_id}",
                        "core_steps": ["step-1"],
                        "pattern_flow": ["flow-1"],
                        "chapter_method_summary": f"Method {section_id}",
                    },
                    "signal_summary": {
                        "perspective": {"value": "p", "notes": ""},
                        "nature": {"value": "n", "notes": ""},
                        "time_orientation": {"value": "t", "notes": ""},
                        "system_scope": {"value": "s", "notes": ""},
                        "equilibrium_view": {"value": "e", "notes": ""},
                        "logic": {"value": ["l"], "notes": ""},
                    },
                    "confidence": confidence,
                }
            )
        return {"main_skills": main_skills}

    def fake_sub_skill(
        main_skill_json: dict[str, object], method_analysis: dict[str, object]
    ) -> dict[str, object]:
        _ = method_analysis
        counters["sub"] += 1
        main_skills = main_skill_json.get("main_skills", [])
        if not isinstance(main_skills, list):
            return {"sub_skills": []}

        sub_skills: list[dict[str, object]] = []
        for main_item in main_skills:
            if not isinstance(main_item, dict):
                continue
            section_id = str(main_item.get("section_id", "")).strip()
            main_skill_id = str(main_item.get("main_skill_id", "")).strip()
            sub_skills.append(
                {
                    "section_id": section_id,
                    "main_skill_id": main_skill_id,
                    "name": f"Sub {section_id}",
                    "description": f"Sub Desc {section_id}",
                    "normalized_pattern": f"pattern-{section_id}",
                    "method_program_summary": "summary",
                    "method_program_example": "example",
                    "abstract_action_chain": ["a"],
                    "source_chunk_ids": [1],
                }
            )
        return {"sub_skills": sub_skills}

    def fake_render(
        main_skill_json: dict[str, object], sub_skill_json: dict[str, object]
    ) -> dict[str, object]:
        counters["render"] += 1
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
            markdown = f"MAIN::{section_id}::{main_skill_id}"
            main_skill_files.append(
                {
                    "main_skill_id": main_skill_id,
                    "section_id": section_id,
                    "section_title": str(item.get("section_title", "")).strip(),
                    "name": str(item.get("pattern_summary", {}).get("name", "")).strip(),
                    "file_name": f"{main_skill_id}.md",
                    "markdown": markdown,
                }
            )

        sub_skill_files: list[dict[str, str]] = []
        for item in sub_skills:
            if not isinstance(item, dict):
                continue
            section_id = str(item.get("section_id", "")).strip()
            main_skill_id = str(item.get("main_skill_id", "")).strip()
            skill_name = str(item.get("name", "")).strip() or "sub"
            markdown = f"SUB::{section_id}::{main_skill_id}::{skill_name}"
            filename = f"{main_skill_id}_{skill_name}.md"
            sub_skill_files.append(
                {
                    "name": filename,
                    "content": markdown,
                    "file_name": filename,
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

    monkeypatch.setattr(pipeline_service, "run_analyze_method_chunks", fake_analyze)
    monkeypatch.setattr(pipeline_service, "run_main_skill", fake_main_skill)
    monkeypatch.setattr(pipeline_service, "run_sub_skill", fake_sub_skill)
    monkeypatch.setattr(pipeline_service, "run_render", fake_render)
    return counters


def _latest_snapshot(author_id: str) -> AuthorSkillSnapshot | None:
    with session_scope() as session:
        return (
            session.query(AuthorSkillSnapshot)
            .filter(
                AuthorSkillSnapshot.author_id == author_id,
                AuthorSkillSnapshot.is_latest.is_(True),
            )
            .order_by(AuthorSkillSnapshot.created_at.desc())
            .first()
        )


def _snapshot_count(author_id: str) -> int:
    with session_scope() as session:
        return (
            session.query(AuthorSkillSnapshot)
            .filter(AuthorSkillSnapshot.author_id == author_id)
            .count()
        )


def _read_main_skills(snapshot: AuthorSkillSnapshot) -> list[dict[str, object]]:
    outputs = json.loads(snapshot.outputs_json)
    uri = outputs["main_skill_json"]
    payload = json.loads(storage.resolve_storage_uri(uri).read_text(encoding="utf-8"))
    main_skills = payload.get("main_skills", [])
    return main_skills if isinstance(main_skills, list) else []


def _read_sub_skills(snapshot: AuthorSkillSnapshot) -> list[dict[str, object]]:
    outputs = json.loads(snapshot.outputs_json)
    uri = outputs["sub_skill_json"]
    payload = json.loads(storage.resolve_storage_uri(uri).read_text(encoding="utf-8"))
    sub_skills = payload.get("sub_skills", [])
    return sub_skills if isinstance(sub_skills, list) else []


def _read_main_skills_md(snapshot: AuthorSkillSnapshot) -> list[dict[str, object]]:
    outputs = json.loads(snapshot.outputs_json)
    uri = outputs["main_skills_md_json"]
    payload = json.loads(storage.resolve_storage_uri(uri).read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def _read_sub_skills_md(snapshot: AuthorSkillSnapshot) -> list[dict[str, object]]:
    outputs = json.loads(snapshot.outputs_json)
    uri = outputs["sub_skills_md_json"]
    payload = json.loads(storage.resolve_storage_uri(uri).read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def _read_method_analysis(snapshot: AuthorSkillSnapshot) -> dict[str, object]:
    outputs = json.loads(snapshot.outputs_json)
    uri = outputs["method_analysis_json"]
    payload = json.loads(storage.resolve_storage_uri(uri).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_snapshot_json(
    snapshot: AuthorSkillSnapshot, output_key: str, payload: object
) -> None:
    outputs = json.loads(snapshot.outputs_json)
    storage.resolve_storage_uri(outputs[output_key]).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _execute_skills_once(author_id: str) -> str:
    job = job_service.create_author_skills_job(author_id=author_id, auto_run=False)
    job_id = job["jobId"]
    job_service.execute_author_skills_job(job_id)
    return job_id


def test_incremental_skills_generation_and_no_remaining_reuses_latest_snapshot(
    monkeypatch: object,
) -> None:
    author_id = str(uuid4())
    _seed_author_with_sections(author_id=author_id, section_count=5)
    counters = _install_incremental_fakes(monkeypatch, batch_size=2, max_main_skills=0)

    _execute_skills_once(author_id)
    snapshot1 = _latest_snapshot(author_id)
    assert snapshot1 is not None
    main1 = _read_main_skills(snapshot1)
    sections1 = {str(item.get("section_id", "")) for item in main1 if isinstance(item, dict)}
    assert sections1 == {"section-01", "section-02"}
    assert _snapshot_count(author_id) == 1

    _execute_skills_once(author_id)
    snapshot2 = _latest_snapshot(author_id)
    assert snapshot2 is not None
    assert snapshot2.snapshot_id != snapshot1.snapshot_id
    main2 = _read_main_skills(snapshot2)
    sections2 = {str(item.get("section_id", "")) for item in main2 if isinstance(item, dict)}
    assert sections2 == {"section-01", "section-02", "section-03", "section-04"}
    assert _snapshot_count(author_id) == 2

    _execute_skills_once(author_id)
    snapshot3 = _latest_snapshot(author_id)
    assert snapshot3 is not None
    main3 = _read_main_skills(snapshot3)
    sections3 = {str(item.get("section_id", "")) for item in main3 if isinstance(item, dict)}
    assert sections3 == {"section-01", "section-02", "section-03", "section-04", "section-05"}
    assert _snapshot_count(author_id) == 3
    assert counters == {"analyze": 3, "main": 3, "sub": 3, "render": 3}

    job_id = _execute_skills_once(author_id)
    snapshot4 = _latest_snapshot(author_id)
    assert snapshot4 is not None
    assert snapshot4.snapshot_id == snapshot3.snapshot_id
    assert _snapshot_count(author_id) == 3
    assert counters == {"analyze": 3, "main": 3, "sub": 3, "render": 3}

    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        assert job is not None
        assert job.status == "success"
        assert job.snapshot_id == snapshot3.snapshot_id


def test_trim_by_max_confidence_and_latest_snapshot_scope(monkeypatch: object) -> None:
    author_id = str(uuid4())
    _seed_author_with_sections(author_id=author_id, section_count=4)
    counters = _install_incremental_fakes(monkeypatch, batch_size=2, max_main_skills=2)

    _execute_skills_once(author_id)
    snapshot1 = _latest_snapshot(author_id)
    assert snapshot1 is not None
    main1 = _read_main_skills(snapshot1)
    sections1 = {str(item.get("section_id", "")) for item in main1 if isinstance(item, dict)}
    assert sections1 == {"section-01", "section-02"}
    assert len(main1) == 2

    _execute_skills_once(author_id)
    snapshot2 = _latest_snapshot(author_id)
    assert snapshot2 is not None
    assert snapshot2.snapshot_id != snapshot1.snapshot_id
    main2 = _read_main_skills(snapshot2)
    sections2 = [str(item.get("section_id", "")) for item in main2 if isinstance(item, dict)]
    assert len(main2) == 2
    assert set(sections2) == {"section-03", "section-04"}

    sub2 = _read_sub_skills(snapshot2)
    sub_main_ids = {str(item.get("main_skill_id", "")) for item in sub2 if isinstance(item, dict)}
    kept_main_ids = {str(item.get("main_skill_id", "")) for item in main2 if isinstance(item, dict)}
    assert sub_main_ids.issubset(kept_main_ids)

    previous_snapshot_id = snapshot2.snapshot_id
    _execute_skills_once(author_id)
    snapshot3 = _latest_snapshot(author_id)
    assert snapshot3 is not None
    assert snapshot3.snapshot_id != previous_snapshot_id
    assert _snapshot_count(author_id) == 3
    main3 = _read_main_skills(snapshot3)
    sections3 = {str(item.get("section_id", "")) for item in main3 if isinstance(item, dict)}
    assert sections3 == {"section-03", "section-04"}
    assert counters == {"analyze": 3, "main": 3, "sub": 3, "render": 3}


def test_generation_prioritizes_book_coverage_before_same_book_extra_sections(
    monkeypatch: object,
) -> None:
    author_id = str(uuid4())
    _seed_author_with_book_layout(
        author_id=author_id,
        books=[
            ("Book A", 2),
            ("Book B", 1),
        ],
    )
    _install_incremental_fakes(monkeypatch, batch_size=2, max_main_skills=6)

    _execute_skills_once(author_id)
    snapshot = _latest_snapshot(author_id)
    assert snapshot is not None

    main_skills = _read_main_skills(snapshot)
    sections = {str(item.get("section_id", "")) for item in main_skills if isinstance(item, dict)}
    assert sections == {"section-01", "section-03"}

    main_contexts = {
        str(item.get("section_id", "")): item.get("source_context")
        for item in main_skills
        if isinstance(item, dict)
    }
    assert main_contexts["section-01"] == {
        "document_id": "document-01",
        "book_title": "Book A",
        "chapter_title": "Book A Chapter 1",
    }
    assert main_contexts["section-03"] == {
        "document_id": "document-02",
        "book_title": "Book B",
        "chapter_title": "Book B Chapter 1",
    }

    sub_skills = _read_sub_skills(snapshot)
    assert {
        str(item.get("section_id", "")): item.get("source_context")
        for item in sub_skills
        if isinstance(item, dict)
    } == main_contexts

    main_md_items = _read_main_skills_md(snapshot)
    assert {
        str(item.get("section_id", "")): item.get("source_context")
        for item in main_md_items
        if isinstance(item, dict)
    } == main_contexts

    sub_md_items = _read_sub_skills_md(snapshot)
    assert {
        str(item.get("section_id", "")): item.get("source_context")
        for item in sub_md_items
        if isinstance(item, dict)
    } == main_contexts


def test_author_skills_reconciles_stale_processing_document_before_generation(
    monkeypatch: object,
) -> None:
    author_id = str(uuid4())
    now = _now_iso()

    with session_scope() as session:
        session.add(
            Author(
                author_id=author_id,
                author_name=f"Author-{author_id[:8]}",
                school=None,
                avatar_url=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            AuthorDocument(
                document_id="stale-document-01",
                author_id=author_id,
                book_title="Stale Book",
                pdf_uri="memory://stale.md",
                status="processing",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            DocumentChapter(
                chapter_id="stale-section-01",
                document_id="stale-document-01",
                chapter_title="Recovered Chapter",
                order_index=0,
                is_deleted=False,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            DocumentSegment(
                segment_id=str(uuid4()),
                document_id="stale-document-01",
                chapter_id="stale-section-01",
                chunk_id="stale-section-01-chunk-1",
                content="Recovered segment content",
                order_index=0,
                is_deleted=False,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
        )

    counters = _install_incremental_fakes(monkeypatch, batch_size=5, max_main_skills=0)
    _execute_skills_once(author_id)

    snapshot = _latest_snapshot(author_id)
    assert snapshot is not None
    main_skills = _read_main_skills(snapshot)
    assert {str(item.get("section_id", "")) for item in main_skills if isinstance(item, dict)} == {
        "stale-section-01"
    }
    assert counters == {"analyze": 1, "main": 1, "sub": 1, "render": 1}

    with session_scope() as session:
        document = session.get(AuthorDocument, "stale-document-01")
        assert document is not None
        assert document.status == "active"


def test_upgrade_snapshot_source_contexts_backfills_legacy_section_titles() -> None:
    author_id = str(uuid4())
    _seed_author_with_book_layout(
        author_id=author_id,
        books=[("Book A", 1)],
    )

    snapshot_id = str(uuid4())
    snapshot_root = storage.snapshot_root(author_id=author_id, snapshot_id=snapshot_id)
    outputs = {
        "main_skill_json": storage.write_json(
            snapshot_root / "main_skill.json",
            {
                "main_skills": [
                    {
                        "section_id": "legacy-section-01",
                        "main_skill_id": "main_skill_001",
                        "section_title": "Book A Chapter 1",
                        "pattern_summary": {"name": "Legacy Skill"},
                    }
                ]
            },
        ),
        "sub_skill_json": storage.write_json(
            snapshot_root / "sub_skill.json",
            {
                "sub_skills": [
                    {
                        "section_id": "legacy-section-01",
                        "main_skill_id": "main_skill_001",
                        "name": "Legacy Sub Skill",
                        "normalized_pattern": "legacy-pattern",
                    }
                ]
            },
        ),
        "main_skills_md_json": storage.write_json(
            snapshot_root / "main_skills_md.json",
            [
                {
                    "main_skill_id": "main_skill_001",
                    "section_id": "legacy-section-01",
                    "section_title": "Book A Chapter 1",
                    "name": "Legacy Skill",
                    "file_name": "legacy_main.md",
                    "markdown": "MAIN",
                }
            ],
        ),
        "sub_skills_md_json": storage.write_json(
            snapshot_root / "sub_skills_md.json",
            [
                {
                    "main_skill_id": "main_skill_001",
                    "section_id": "legacy-section-01",
                    "name": "Legacy Sub Skill",
                    "normalized_pattern": "legacy-pattern",
                    "file_name": "legacy_sub.md",
                    "markdown": "SUB",
                }
            ],
        ),
    }

    with session_scope() as session:
        changed = pipeline_service.upgrade_snapshot_source_contexts(
            session=session,
            author_id=author_id,
            outputs=outputs,
        )

    assert changed is True

    main_skill_payload = json.loads(
        storage.resolve_storage_uri(outputs["main_skill_json"]).read_text(encoding="utf-8")
    )
    main_skill = main_skill_payload["main_skills"][0]
    assert main_skill["document_id"] == "document-01"
    assert main_skill["book_title"] == "Book A"
    assert main_skill["chapter_title"] == "Book A Chapter 1"
    assert main_skill["source_context"] == {
        "document_id": "document-01",
        "book_title": "Book A",
        "chapter_title": "Book A Chapter 1",
    }

    sub_skill_payload = json.loads(
        storage.resolve_storage_uri(outputs["sub_skill_json"]).read_text(encoding="utf-8")
    )
    sub_skill = sub_skill_payload["sub_skills"][0]
    assert sub_skill["source_context"] == main_skill["source_context"]

    main_md_payload = json.loads(
        storage.resolve_storage_uri(outputs["main_skills_md_json"]).read_text(encoding="utf-8")
    )
    assert main_md_payload[0]["source_context"] == main_skill["source_context"]

    sub_md_payload = json.loads(
        storage.resolve_storage_uri(outputs["sub_skills_md_json"]).read_text(encoding="utf-8")
    )
    assert sub_md_payload[0]["source_context"] == main_skill["source_context"]


def test_generation_reconciles_legacy_duplicates_without_llm_and_is_idempotent(
    monkeypatch: object,
) -> None:
    author_id = str(uuid4())
    _seed_author_with_sections(author_id=author_id, section_count=2)
    counters = _install_incremental_fakes(monkeypatch, batch_size=2, max_main_skills=0)
    _execute_skills_once(author_id)

    dirty_snapshot = _latest_snapshot(author_id)
    assert dirty_snapshot is not None
    main_skills = _read_main_skills(dirty_snapshot)
    sub_skills = _read_sub_skills(dirty_snapshot)
    current_main = next(item for item in main_skills if item["section_id"] == "section-01")
    current_sub = next(item for item in sub_skills if item["section_id"] == "section-01")

    legacy_main = dict(current_main)
    legacy_main.update(
        {
            "section_id": "legacy-section-01",
            "main_skill_id": "main_skill_999",
            "confidence": 0.99,
        }
    )
    legacy_sub = dict(current_sub)
    legacy_sub.update(
        {"section_id": "legacy-section-01", "main_skill_id": "main_skill_999"}
    )
    unmatched_main = dict(current_main)
    unmatched_main.update(
        {
            "section_id": "unmatched-section",
            "section_title": "Missing Chapter",
            "chapter_title": "Missing Chapter",
            "main_skill_id": "main_skill_998",
            "source_context": {"chapter_title": "Missing Chapter"},
            "document_id": "",
            "book_title": "",
        }
    )
    unmatched_sub = dict(current_sub)
    unmatched_sub.update(
        {"section_id": "unmatched-section", "main_skill_id": "main_skill_998"}
    )
    _write_snapshot_json(
        dirty_snapshot,
        "main_skill_json",
        {"main_skills": [*main_skills, legacy_main, unmatched_main]},
    )
    _write_snapshot_json(
        dirty_snapshot,
        "sub_skill_json",
        {"sub_skills": [*sub_skills, legacy_sub, unmatched_sub]},
    )
    method_analysis = _read_method_analysis(dirty_snapshot)
    chunks = method_analysis.get("chunks", [])
    assert isinstance(chunks, list)
    method_analysis["chunks"] = [
        *chunks,
        {"section_id": "legacy-section-01", "section_title": "Chapter 1"},
        {"section_id": "unmatched-section", "section_title": "Missing Chapter"},
    ]
    _write_snapshot_json(dirty_snapshot, "method_analysis_json", method_analysis)

    _execute_skills_once(author_id)
    clean_snapshot = _latest_snapshot(author_id)
    assert clean_snapshot is not None
    assert clean_snapshot.snapshot_id != dirty_snapshot.snapshot_id
    assert counters == {"analyze": 1, "main": 1, "sub": 1, "render": 2}

    clean_main = _read_main_skills(clean_snapshot)
    clean_sub = _read_sub_skills(clean_snapshot)
    assert {item["section_id"] for item in clean_main} == {"section-01", "section-02"}
    assert {item["main_skill_id"] for item in clean_main} == {
        "main_skill_001",
        "main_skill_002",
    }
    assert {item["main_skill_id"] for item in clean_sub} == {
        "main_skill_001",
        "main_skill_002",
    }
    assert all(item["section_id"] != "legacy-section-01" for item in clean_sub)

    main_md = _read_main_skills_md(clean_snapshot)
    sub_md = _read_sub_skills_md(clean_snapshot)
    assert {item["section_id"] for item in main_md} == {"section-01", "section-02"}
    assert {item["section_id"] for item in sub_md} == {"section-01", "section-02"}
    clean_analysis = _read_method_analysis(clean_snapshot)
    clean_chunks = clean_analysis.get("chunks", [])
    assert isinstance(clean_chunks, list)
    assert {
        item["section_id"] for item in clean_chunks if isinstance(item, dict)
    } == {"section-01", "section-02"}

    outputs = json.loads(clean_snapshot.outputs_json)
    zip_path = storage.resolve_storage_uri(outputs["sub_skills_md_zip"])
    with ZipFile(zip_path) as archive:
        assert set(archive.namelist()) == {str(item["file_name"]) for item in sub_md}

    _execute_skills_once(author_id)
    stable_snapshot = _latest_snapshot(author_id)
    assert stable_snapshot is not None
    assert stable_snapshot.snapshot_id == clean_snapshot.snapshot_id
    assert counters == {"analyze": 1, "main": 1, "sub": 1, "render": 2}


def test_reconciliation_does_not_guess_ambiguous_cross_book_titles() -> None:
    section_contexts = {
        "current-a": {
            "document_id": "doc-a",
            "book_title": "Book A",
            "chapter_title": "Introduction",
        },
        "current-b": {
            "document_id": "doc-b",
            "book_title": "Book B",
            "chapter_title": "Introduction",
        },
    }
    ambiguous = {
        "section_id": "legacy-ambiguous",
        "main_skill_id": "main_skill_001",
        "section_title": "Introduction",
    }
    scoped = {
        "section_id": "legacy-scoped",
        "main_skill_id": "main_skill_002",
        "section_title": "Introduction",
        "source_context": {
            "book_title": "Book B",
            "chapter_title": "Introduction",
        },
    }

    main, _sub, stats, _mapping = pipeline_service._reconcile_existing_skills(
        [ambiguous, scoped], [], section_contexts=section_contexts
    )

    assert [item["section_id"] for item in main] == ["current-b"]
    assert stats == {
        "input": 2,
        "retained": 1,
        "mapped": 1,
        "deduplicated": 0,
        "deleted": 1,
        "sub_skills_deleted": 0,
    }


def test_failed_reconciliation_render_keeps_previous_latest_snapshot(
    monkeypatch: object,
) -> None:
    author_id = str(uuid4())
    _seed_author_with_sections(author_id=author_id, section_count=1)
    _install_incremental_fakes(monkeypatch, batch_size=1, max_main_skills=0)
    _execute_skills_once(author_id)
    previous = _latest_snapshot(author_id)
    assert previous is not None
    main_skills = _read_main_skills(previous)
    dirty = dict(main_skills[0])
    dirty.update(
        {
            "section_id": "unmatched",
            "main_skill_id": "main_skill_999",
            "section_title": "Missing",
            "chapter_title": "Missing",
            "source_context": {"chapter_title": "Missing"},
            "document_id": "",
            "book_title": "",
        }
    )
    _write_snapshot_json(
        previous, "main_skill_json", {"main_skills": [*main_skills, dirty]}
    )

    def fail_render(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("render failed")

    monkeypatch.setattr(pipeline_service, "run_render", fail_render)
    job_id = _execute_skills_once(author_id)

    latest = _latest_snapshot(author_id)
    assert latest is not None
    assert latest.snapshot_id == previous.snapshot_id
    with session_scope() as session:
        job = session.get(PipelineJob, job_id)
        assert job is not None
        assert job.status == "failed"
