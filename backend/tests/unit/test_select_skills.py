from __future__ import annotations

from typing import Any

from app.services import select_skills


class _FakeResponse:
    def __init__(self, content: Any) -> None:
        self.content = content


class _FakeLlm:
    def __init__(self, content: Any) -> None:
        self._content = content

    def invoke(self, _prompt: str) -> _FakeResponse:
        return _FakeResponse(self._content)


def _snapshot_outputs() -> dict[str, Any]:
    return {
        "main_skill_json": {
            "main_skills": [
                {
                    "section_id": "section-1",
                    "main_skill_id": "main_skill_001",
                    "pattern_summary": {
                        "name": "Demand Shock Diagnosis",
                        "description": "Analyze demand contraction and spending multipliers.",
                        "applicability": "Use for recession demand-side questions.",
                    },
                },
                {
                    "section_id": "section-2",
                    "main_skill_id": "main_skill_002",
                    "pattern_summary": {
                        "name": "Labor Market Transmission",
                        "description": "Track wage, employment and productivity transmission.",
                        "applicability": "Use for unemployment and wage dynamic questions.",
                    },
                },
            ]
        }
    }


def test_run_select_skills_uses_llm_skill_index_when_valid(monkeypatch: object) -> None:
    monkeypatch.setattr(select_skills, "build_optional_llm", lambda: _FakeLlm('{"skill_index": 2}'))

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs(),
        query="how wages and employment move together",
    )

    assert result["selected_skill_index"] == 2
    assert result["selected_section_id"] == "section-2"
    assert result["selection_mode"] == "llm"
    assert result["selection_warning"] is None


def test_run_select_skills_fallbacks_when_llm_output_invalid_json(monkeypatch: object) -> None:
    monkeypatch.setattr(select_skills, "build_optional_llm", lambda: _FakeLlm("invalid-json"))

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs(),
        query="unemployment and wage pressure",
    )

    assert result["selected_skill_index"] == 2
    assert result["selected_section_id"] == "section-2"
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: llm_invalid_json"


def test_run_select_skills_fallbacks_when_llm_index_out_of_range(monkeypatch: object) -> None:
    monkeypatch.setattr(
        select_skills, "build_optional_llm", lambda: _FakeLlm('{"skill_index": 99}')
    )

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs(),
        query="recession demand decline",
    )

    assert result["selected_skill_index"] == 1
    assert result["selected_section_id"] == "section-1"
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: llm_skill_index_out_of_range"


def test_run_select_skills_returns_empty_selection_when_no_templates() -> None:
    result = select_skills.run_select_skills(
        snapshot_outputs={"main_skill_json": {"main_skills": []}},
        query="anything",
    )

    assert result["selected_skill_index"] is None
    assert result["selected_section_id"] is None
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: no_skill_templates"
