"""Unit coverage for structured markdown outputs from render stage."""

from __future__ import annotations

from app.services import render


def test_run_render_produces_split_main_and_structured_sub_outputs(monkeypatch: object) -> None:
    """run_render should keep legacy outputs and add structured markdown records."""

    def fake_render_main_skill_md(main_skill: dict[str, object]) -> str:
        return f"MAIN::{main_skill.get('main_skill_id', '')}"

    def fake_render_sub_skill_md(sub_skill: dict[str, object], index: int) -> str:
        return f"SUB::{sub_skill.get('name', '')}::{index}"

    def fake_validate_and_normalize_sub_skill(
        raw_skill: dict[str, object],
        index: int,
    ) -> render.SubSkillData:
        return render.SubSkillData(
            section_id=str(raw_skill.get("section_id", "")),
            main_skill_id=str(raw_skill.get("main_skill_id", "")),
            normalized_pattern=str(raw_skill.get("normalized_pattern", "")),
            name=str(raw_skill.get("name", "sub")),
            description="desc",
            method_program_summary="summary",
            method_program_example="example",
            abstract_action_chain=[],
            source_chunk_ids=[index],
        )

    monkeypatch.setattr(render, "_render_main_skill_md", fake_render_main_skill_md)
    monkeypatch.setattr(render, "_render_sub_skill_md", fake_render_sub_skill_md)
    monkeypatch.setattr(render, "_validate_and_normalize_sub_skill", fake_validate_and_normalize_sub_skill)

    main_skill_json = {
        "main_skills": [
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "section_title": "Chapter One",
                "pattern_summary": {"name": "Main A"},
            },
            {
                "main_skill_id": "main_skill_002",
                "section_id": "section-2",
                "section_title": "Chapter Two",
                "pattern_summary": {"name": "Main B"},
            },
        ]
    }
    sub_skill_json = {
        "sub_skills": [
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "name": "Sub A",
                "normalized_pattern": "np-a",
            }
        ]
    }

    rendered = render.run_render(main_skill_json=main_skill_json, sub_skill_json=sub_skill_json)

    assert "main_skill_md" in rendered
    assert "MAIN::main_skill_001" in rendered["main_skill_md"]
    assert "MAIN::main_skill_002" in rendered["main_skill_md"]

    assert "main_skill_files" in rendered
    assert isinstance(rendered["main_skill_files"], list)
    assert len(rendered["main_skill_files"]) == 2
    first_main = rendered["main_skill_files"][0]
    assert first_main["main_skill_id"] == "main_skill_001"
    assert first_main["section_id"] == "section-1"
    assert first_main["name"] == "Main A"
    assert first_main["file_name"].endswith(".md")
    assert first_main["markdown"] == "MAIN::main_skill_001"

    assert "sub_skill_files" in rendered
    assert isinstance(rendered["sub_skill_files"], list)
    assert len(rendered["sub_skill_files"]) == 1
    first_sub = rendered["sub_skill_files"][0]
    assert first_sub["name"].endswith(".md")
    assert first_sub["content"] == "SUB::Sub A::1"
    assert first_sub["file_name"].endswith(".md")
    assert first_sub["skill_name"] == "Sub A"
    assert first_sub["main_skill_id"] == "main_skill_001"
    assert first_sub["section_id"] == "section-1"
    assert first_sub["normalized_pattern"] == "np-a"
    assert first_sub["markdown"] == "SUB::Sub A::1"
