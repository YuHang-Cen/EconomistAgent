"""Unit coverage for answer context source selection."""

from __future__ import annotations

import json
import logging

import pytest
from app.services import answer_with_skills


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content


class _EchoPromptLlm:
    def invoke(self, prompt: str) -> _Response:
        return _Response(
            json.dumps(
                {
                    "title": "Generated title",
                    "topic": "Generated topic",
                    "summary": "Generated summary",
                    "markdown": prompt,
                }
            )
        )


class _SequenceLlm:
    def __init__(self, responses: list[str | Exception]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def invoke(self, prompt: str) -> _Response:
        self.prompts.append(prompt)
        response = self.responses[len(self.prompts) - 1]
        if isinstance(response, Exception):
            raise response
        return _Response(response)


def test_answer_prefers_markdown_outputs_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """When markdown artifacts exist, answer context should use selected markdown content."""
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", _EchoPromptLlm)

    snapshot_outputs = {
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
    selected = {
        "selected_skill_indices": [1, 2],
        "selected_section_ids": ["section-1", "section-2"],
        "selection_mode": "llm",
        "selection_warning": None,
    }

    result = answer_with_skills.run_answer_with_skills(
        query="explain mechanism",
        selected=selected,
        snapshot_outputs=snapshot_outputs,
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
    assert "MAIN_MARKER_ABC" in markdown
    assert "MAIN_MARKER_DEF" in markdown
    assert "SUB_MARKER_XYZ" in markdown
    assert "SUB_MARKER_SECOND" in markdown
    assert "SHOULD_APPEAR_ONE" in markdown
    assert "SHOULD_APPEAR_TWO" in markdown


def test_answer_falls_back_to_json_when_markdown_outputs_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If markdown artifacts are absent, answer context should fallback to JSON summaries."""
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", _EchoPromptLlm)

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
    selected = {
        "selected_skill_indices": [1, 2],
        "selected_section_ids": ["section-9", "section-10"],
        "selection_mode": "llm",
        "selection_warning": None,
    }

    result = answer_with_skills.run_answer_with_skills(
        query="what happened",
        selected=selected,
        snapshot_outputs=snapshot_outputs,
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


def test_answer_accepts_extra_model_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "title": "Generated title",
        "topic": "Generated topic",
        "summary": "Generated summary",
        "markdown": "Generated markdown",
        "reasoning_note": "This harmless field must not invalidate the answer.",
    }
    llm = _SequenceLlm([json.dumps(payload)])
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: llm)

    result = answer_with_skills.run_answer_with_skills(
        query="test query",
        selected={},
        snapshot_outputs={},
    )

    assert result["answer"] == {
        "title": "Generated title",
        "topic": "Generated topic",
        "summary": "Generated summary",
        "markdown": "Generated markdown",
    }
    assert len(llm.prompts) == 1


def test_answer_retries_once_after_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    valid_payload = json.dumps(
        {
            "title": "Recovered title",
            "topic": "Recovered topic",
            "summary": "Recovered summary",
            "markdown": "Recovered markdown",
        }
    )
    llm = _SequenceLlm(["not-json", valid_payload])
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: llm)

    result = answer_with_skills.run_answer_with_skills(
        query="test query",
        selected={},
        snapshot_outputs={},
    )

    assert result["answer"]["title"] == "Recovered title"
    assert len(llm.prompts) == 2
    assert "Output Correction" in llm.prompts[1]


def test_answer_raises_after_two_invalid_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = _SequenceLlm(["not-json", '{"title": "still incomplete"}'])
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: llm)

    with pytest.raises(
        answer_with_skills.AnswerGenerationError,
        match="answer_generation_failed:invalid_answer_schema",
    ):
        answer_with_skills.run_answer_with_skills(
            query="test query",
            selected={},
            snapshot_outputs={},
        )

    assert len(llm.prompts) == 2


def test_answer_invoke_failure_is_not_converted_to_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm = _SequenceLlm([RuntimeError("private upstream detail")])
    monkeypatch.setattr(answer_with_skills, "build_optional_llm", lambda: llm)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            answer_with_skills.AnswerGenerationError,
            match="answer_generation_failed:llm_invoke_failed",
        ):
            answer_with_skills.run_answer_with_skills(
                query="private query text",
                selected={},
                snapshot_outputs={},
            )

    assert len(llm.prompts) == 1
    assert "error_code=llm_invoke_failed" in caplog.text
    assert "query_hash=" in caplog.text
    assert "private query text" not in caplog.text
    assert "private upstream detail" not in caplog.text
