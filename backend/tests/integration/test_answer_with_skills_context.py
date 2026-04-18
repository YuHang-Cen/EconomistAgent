"""Unit coverage for answer context source selection."""

from __future__ import annotations

from app.services import answer_with_skills


def test_answer_prefers_markdown_outputs_when_available(monkeypatch: object) -> None:
    """When markdown artifacts exist, answer context should use selected markdown content."""
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: None)
    monkeypatch.setattr(
        answer_with_skills,
        "_fallback_answer",
        lambda query, context: {"title": "", "summary": "", "markdown": context},
    )

    snapshot_outputs = {
        "main_skill_json": {
            "main_skills": [
                {
                    "main_skill_id": "main_skill_001",
                    "section_id": "section-1",
                    "pattern_summary": {
                        "name": "JSON Main",
                        "description": "JSON main description",
                        "applicability": "JSON applicability",
                        "core_steps": ["json step"],
                    },
                }
            ]
        },
        "sub_skill_json": {
            "sub_skills": [
                {
                    "main_skill_id": "main_skill_001",
                    "section_id": "section-1",
                    "name": "JSON Sub",
                    "description": "JSON sub description",
                }
            ]
        },
        "main_skills_md_json": [
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "section_title": "Section One",
                "name": "Main Skill One",
                "file_name": "main_skill_001.md",
                "markdown": "MAIN_MARKER_ABC\nMain markdown body",
            }
        ],
        "sub_skills_md_json": [
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "name": "Chosen Sub",
                "normalized_pattern": "pattern-a",
                "file_name": "chosen_sub.md",
                "markdown": "SUB_MARKER_XYZ\nSub markdown body",
            },
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "name": "Other Sub",
                "normalized_pattern": "pattern-b",
                "file_name": "other_sub.md",
                "markdown": "SHOULD_NOT_APPEAR",
            },
        ],
    }
    selected = {
        "selected_skill_index": 1,
        "selected_section_id": "section-1",
        "selection_mode": "llm",
        "selection_warning": None,
    }

    result = answer_with_skills.run_answer_with_skills(
        query="explain mechanism",
        selected=selected,
        snapshot_outputs=snapshot_outputs,
    )

    markdown = result["answer"]["markdown"]
    assert result["selected_main_skill_name"] == "Main Skill One"
    assert result["selected_sub_skill_names"] == ["Chosen Sub", "Other Sub"]
    assert "MAIN_MARKER_ABC" in markdown
    assert "SUB_MARKER_XYZ" in markdown
    assert "SHOULD_NOT_APPEAR" in markdown


def test_answer_falls_back_to_json_when_markdown_outputs_missing(monkeypatch: object) -> None:
    """If markdown artifacts are absent, answer context should fallback to JSON summaries."""
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: None)
    monkeypatch.setattr(
        answer_with_skills,
        "_fallback_answer",
        lambda query, context: {"title": "", "summary": "", "markdown": context},
    )

    snapshot_outputs = {
        "main_skill_json": {
            "main_skills": [
                {
                    "main_skill_id": "main_skill_009",
                    "section_id": "section-9",
                    "pattern_summary": {
                        "name": "JSON_ONLY_MAIN_NAME",
                        "description": "JSON_ONLY_DESC",
                        "applicability": "JSON_ONLY_APPLY",
                        "core_steps": ["JSON_STEP_1"],
                    },
                }
            ]
        },
        "sub_skill_json": {
            "sub_skills": [
                {
                    "main_skill_id": "main_skill_009",
                    "section_id": "section-9",
                    "name": "JSON_ONLY_SUB",
                    "description": "JSON_ONLY_SUB_DESC",
                }
            ]
        },
    }
    selected = {
        "selected_skill_index": 1,
        "selected_section_id": "section-9",
        "selection_mode": "llm",
        "selection_warning": None,
    }

    result = answer_with_skills.run_answer_with_skills(
        query="what happened",
        selected=selected,
        snapshot_outputs=snapshot_outputs,
    )

    markdown = result["answer"]["markdown"]
    assert result["selected_main_skill_name"] == "JSON_ONLY_MAIN_NAME"
    assert result["selected_sub_skill_names"] == ["JSON_ONLY_SUB"]
    assert "JSON_ONLY_MAIN_NAME" in markdown
    assert "JSON_ONLY_SUB" in markdown
