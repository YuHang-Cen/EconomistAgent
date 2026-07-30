"""Coverage for answer context selection, paper normalization, and fallback behavior."""

from __future__ import annotations

from app.services import answer_with_skills


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> _FakeResponse:
        self.prompts.append(prompt)
        if not self._responses:
            raise RuntimeError("no fake llm response available")
        return _FakeResponse(self._responses.pop(0))


class _ExplodingLLM:
    def invoke(self, prompt: str) -> _FakeResponse:
        raise RuntimeError("boom")


def _selected() -> dict[str, object]:
    return {
        "selected_skill_indices": [1, 2],
        "selected_section_ids": ["section-1", "section-2"],
        "selection_mode": "llm",
        "selection_warning": None,
    }


def _markdown_snapshot_outputs() -> dict[str, object]:
    return {
        "main_skill_json": {
            "main_skills": [
                {
                    "main_skill_id": "main_skill_001",
                    "section_id": "section-1",
                    "pattern_summary": {
                        "name": "JSON Main One",
                        "description": "JSON main one description",
                        "applicability": "JSON applicability one",
                        "core_steps": ["json step one"],
                    },
                },
                {
                    "main_skill_id": "main_skill_002",
                    "section_id": "section-2",
                    "pattern_summary": {
                        "name": "JSON Main Two",
                        "description": "JSON main two description",
                        "applicability": "JSON applicability two",
                        "core_steps": ["json step two"],
                    },
                },
            ]
        },
        "sub_skill_json": {
            "sub_skills": [
                {
                    "main_skill_id": "main_skill_001",
                    "section_id": "section-1",
                    "name": "JSON Sub One",
                    "description": "JSON sub one description",
                },
                {
                    "main_skill_id": "main_skill_002",
                    "section_id": "section-2",
                    "name": "JSON Sub Shared",
                    "description": "JSON sub shared description",
                },
            ]
        },
        "main_skills_md_json": [
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "section_title": "Section One",
                "name": "Main Skill One",
                "file_name": "main_skill_001.md",
                "markdown": "MAIN_MARKER_ABC\nMain markdown body one",
            },
            {
                "main_skill_id": "main_skill_002",
                "section_id": "section-2",
                "section_title": "Section Two",
                "name": "Main Skill Two",
                "file_name": "main_skill_002.md",
                "markdown": "MAIN_MARKER_DEF\nMain markdown body two",
            },
        ],
        "sub_skills_md_json": [
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "name": "Chosen Sub",
                "normalized_pattern": "pattern-a",
                "file_name": "chosen_sub.md",
                "markdown": "SUB_MARKER_XYZ\nSub markdown body one",
            },
            {
                "main_skill_id": "main_skill_001",
                "section_id": "section-1",
                "name": "Shared Sub",
                "normalized_pattern": "pattern-b",
                "file_name": "shared_sub_1.md",
                "markdown": "SHOULD_APPEAR_ONE",
            },
            {
                "main_skill_id": "main_skill_002",
                "section_id": "section-2",
                "name": "Shared Sub",
                "normalized_pattern": "pattern-c",
                "file_name": "shared_sub_2.md",
                "markdown": "SHOULD_APPEAR_TWO",
            },
            {
                "main_skill_id": "main_skill_002",
                "section_id": "section-2",
                "name": "Second Section Sub",
                "normalized_pattern": "pattern-d",
                "file_name": "second_sub.md",
                "markdown": "SUB_MARKER_SECOND\nSub markdown body two",
            },
        ],
    }


def _json_only_snapshot_outputs() -> dict[str, object]:
    return {
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
                },
                {
                    "main_skill_id": "main_skill_010",
                    "section_id": "section-10",
                    "pattern_summary": {
                        "name": "JSON_ONLY_MAIN_NAME_TWO",
                        "description": "JSON_ONLY_DESC_TWO",
                        "applicability": "JSON_ONLY_APPLY_TWO",
                        "core_steps": ["JSON_STEP_2"],
                    },
                },
            ]
        },
        "sub_skill_json": {
            "sub_skills": [
                {
                    "main_skill_id": "main_skill_009",
                    "section_id": "section-9",
                    "name": "JSON_ONLY_SUB",
                    "description": "JSON_ONLY_SUB_DESC",
                },
                {
                    "main_skill_id": "main_skill_010",
                    "section_id": "section-10",
                    "name": "JSON_ONLY_SUB_TWO",
                    "description": "JSON_ONLY_SUB_DESC_TWO",
                },
            ]
        },
    }


def test_answer_prefers_markdown_outputs_when_available(monkeypatch: object) -> None:
    """When markdown artifacts exist, answer context should use selected markdown content."""
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: None)
    monkeypatch.setattr(
        answer_with_skills,
        "_fallback_answer",
        lambda query, context, **kwargs: {
            "title": "fallback",
            "topic": "topic",
            "summary": "summary",
            "markdown": context,
        },
    )

    result = answer_with_skills.run_answer_with_skills(
        query="explain mechanism",
        selected=_selected(),
        snapshot_outputs=_markdown_snapshot_outputs(),
    )

    markdown = result["answer"]["markdown"]
    assert result["selected_skill_indices"] == [1, 2]
    assert result["selected_section_ids"] == ["section-1", "section-2"]
    assert result["selected_skill_index"] == 1
    assert result["selected_section_id"] == "section-1"
    assert result["selected_main_skill_names"] == ["Main Skill One", "Main Skill Two"]
    assert result["selected_main_skill_name"] == "Main Skill One"
    assert result["selected_sub_skill_names"] == [
        "Chosen Sub",
        "Shared Sub",
        "Second Section Sub",
    ]
    assert result["answer_source"] == "fallback"
    assert "MAIN_MARKER_ABC" in markdown
    assert "MAIN_MARKER_DEF" in markdown
    assert "SUB_MARKER_XYZ" in markdown
    assert "SUB_MARKER_SECOND" in markdown
    assert "SHOULD_APPEAR_ONE" in markdown
    assert "SHOULD_APPEAR_TWO" in markdown


def test_answer_falls_back_to_json_when_markdown_outputs_missing(monkeypatch: object) -> None:
    """If markdown artifacts are absent, answer context should fallback to JSON summaries."""
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: None)
    monkeypatch.setattr(
        answer_with_skills,
        "_fallback_answer",
        lambda query, context, **kwargs: {
            "title": "fallback",
            "topic": "topic",
            "summary": "summary",
            "markdown": context,
        },
    )

    selected = {
        "selected_skill_indices": [1, 2],
        "selected_section_ids": ["section-9", "section-10"],
        "selection_mode": "llm",
        "selection_warning": None,
    }

    result = answer_with_skills.run_answer_with_skills(
        query="what happened",
        selected=selected,
        snapshot_outputs=_json_only_snapshot_outputs(),
    )

    markdown = result["answer"]["markdown"]
    assert result["selected_skill_indices"] == [1, 2]
    assert result["selected_section_ids"] == ["section-9", "section-10"]
    assert result["selected_skill_index"] == 1
    assert result["selected_section_id"] == "section-9"
    assert result["selected_main_skill_names"] == [
        "JSON_ONLY_MAIN_NAME",
        "JSON_ONLY_MAIN_NAME_TWO",
    ]
    assert result["selected_main_skill_name"] == "JSON_ONLY_MAIN_NAME"
    assert result["selected_sub_skill_names"] == ["JSON_ONLY_SUB", "JSON_ONLY_SUB_TWO"]
    assert "JSON_ONLY_MAIN_NAME" in markdown
    assert "JSON_ONLY_MAIN_NAME_TWO" in markdown
    assert "JSON_ONLY_SUB" in markdown
    assert "JSON_ONLY_SUB_TWO" in markdown


def test_answer_classifies_paper_text_and_cleans_prompt_input(monkeypatch: object) -> None:
    """Paper-like inputs should use the paper mode and omit noisy metadata in prompts."""
    fake_llm = _FakeLLM(
        [
            (
                '{"title":"Referee Points","topic":"industrial policy",'
                '"summary":"Core review issues are identified.",'
                '"markdown":"# Referee Points\\n\\n'
                "1. Framing is promising but needs a sharper general-equilibrium contribution."
                '"}'
            )
        ]
    )
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: fake_llm)

    paper_query = """
Abstract

This paper studies robot subsidies and financial frictions in China.

Keywords: industrial policy, robots, China
JEL codes: O25, O33
author@email.com

1 Introduction

China provides an ideal setting because robot adoption is large and capital misallocation is severe.

Related Literature

This section should not appear in the normalized paper brief.
"""

    result = answer_with_skills.run_answer_with_skills(
        query=paper_query,
        selected=_selected(),
        snapshot_outputs=_markdown_snapshot_outputs(),
    )

    assert result["query_kind"] == "paper_text"
    assert result["answer_source"] == "llm"
    used_prompt = fake_llm.prompts[0]
    assert "Keywords:" not in used_prompt
    assert "JEL codes" not in used_prompt
    assert "author@email.com" not in used_prompt
    assert "Related Literature" not in used_prompt
    assert "China provides an ideal setting" in used_prompt


def test_answer_repairs_invalid_json_and_marks_source(monkeypatch: object) -> None:
    """When the first LLM output is invalid, the repair round should recover it."""
    fake_llm = _FakeLLM(
        [
            "Here are concise referee points without JSON.",
            (
                '{"title":"Repaired Output","topic":"paper review",'
                '"summary":"The output was repaired into valid JSON.",'
                '"markdown":"# Repaired\\n\\n1. Clarify the main identification threat."}'
            ),
        ]
    )
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: fake_llm)

    result = answer_with_skills.run_answer_with_skills(
        query="1. Why China?\n2. What is the mechanism?",
        selected=_selected(),
        snapshot_outputs=_markdown_snapshot_outputs(),
    )

    assert result["query_kind"] == "question_list"
    assert result["answer_source"] == "llm_repaired"
    assert result["answer_warning"] == "Answer JSON was repaired after validation failure."
    assert result["answer"]["title"] == "Repaired Output"
    assert len(fake_llm.prompts) == 2


def test_fallback_does_not_echo_raw_paper_text(monkeypatch: object) -> None:
    """Fallback answers should stay short and avoid dumping the raw manuscript text."""
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: _ExplodingLLM())

    query = """
Abstract

This paper studies robot subsidies in China.

Keywords: robots, subsidies
JEL codes: O25

1 Introduction

China provides an ideal setting for studying misallocation under industrial policy.
"""

    result = answer_with_skills.run_answer_with_skills(
        query=query,
        selected=_selected(),
        snapshot_outputs=_markdown_snapshot_outputs(),
    )

    assert result["query_kind"] == "paper_text"
    assert result["answer_source"] == "fallback"
    assert result["answer_fallback_reason"] == "llm_invoke_failed"
    markdown = result["answer"]["markdown"]
    assert "Keywords:" not in markdown
    assert "JEL codes" not in markdown
    assert "1 Introduction" not in markdown
    assert "Source preview:" in markdown
