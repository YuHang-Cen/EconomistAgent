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


def _settings(*, recall_limit: int = 20, select_count: int = 3) -> object:
    return type(
        "S",
        (),
        {
            "skills_select_recall_limit": recall_limit,
            "skills_select_count": select_count,
        },
    )()


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
                {
                    "section_id": "section-3",
                    "main_skill_id": "main_skill_003",
                    "pattern_summary": {
                        "name": "Financial Contagion",
                        "description": "Trace balance-sheet spillovers and liquidity stress.",
                        "applicability": "Use for banking and credit shock questions.",
                    },
                },
            ]
        }
    }


def _snapshot_outputs_with_count(count: int) -> dict[str, Any]:
    return {
        "main_skill_json": {
            "main_skills": [
                {
                    "section_id": f"section-{index}",
                    "main_skill_id": f"main_skill_{index:03d}",
                    "pattern_summary": {
                        "name": f"Skill {index}",
                        "description": f"Description {index}",
                        "applicability": (
                            "Use for labor market wage questions."
                            if index == count
                            else f"Use for general topic {index}."
                        ),
                    },
                }
                for index in range(1, count + 1)
            ]
        }
    }


def test_run_select_skills_uses_llm_skill_indices_when_valid(monkeypatch: object) -> None:
    monkeypatch.setattr(select_skills, "get_settings", lambda: _settings(select_count=3))
    monkeypatch.setattr(
        select_skills,
        "build_optional_llm",
        lambda: _FakeLlm('{"skill_indices": [2, 3]}'),
    )

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs(),
        query="how wages, productivity and banking pressure interact",
    )

    assert result["selected_skill_indices"] == [2, 3]
    assert result["selected_section_ids"] == ["section-2", "section-3"]
    assert result["selected_skill_index"] == 2
    assert result["selected_section_id"] == "section-2"
    assert result["selection_mode"] == "llm"
    assert result["selection_warning"] is None


def test_run_select_skills_fallbacks_when_llm_output_invalid_json(monkeypatch: object) -> None:
    monkeypatch.setattr(select_skills, "get_settings", lambda: _settings(select_count=2))
    monkeypatch.setattr(select_skills, "build_optional_llm", lambda: _FakeLlm("invalid-json"))

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs(),
        query="unemployment and wage pressure",
    )

    assert result["selected_skill_indices"] == [1, 2]
    assert result["selected_section_ids"] == ["section-1", "section-2"]
    assert result["selected_skill_index"] == 1
    assert result["selected_section_id"] == "section-1"
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: llm_invalid_json"


def test_run_select_skills_rejects_invalid_json_shape_and_fallbacks(monkeypatch: object) -> None:
    monkeypatch.setattr(select_skills, "get_settings", lambda: _settings(select_count=2))
    monkeypatch.setattr(
        select_skills,
        "build_optional_llm",
        lambda: _FakeLlm('{"skill_index": 1}'),
    )

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs(),
        query="recession demand decline",
    )

    assert result["selected_skill_indices"] == [1, 2]
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: llm_invalid_json_shape"


def test_run_select_skills_rejects_duplicate_indices_and_fallbacks(monkeypatch: object) -> None:
    monkeypatch.setattr(select_skills, "get_settings", lambda: _settings(select_count=3))
    monkeypatch.setattr(
        select_skills,
        "build_optional_llm",
        lambda: _FakeLlm('{"skill_indices": [2, 2]}'),
    )

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs(),
        query="unemployment and wage pressure",
    )

    assert result["selected_skill_indices"] == [1, 2, 3]
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: llm_skill_indices_duplicated"


def test_run_select_skills_rejects_too_many_indices_and_fallbacks(monkeypatch: object) -> None:
    monkeypatch.setattr(select_skills, "get_settings", lambda: _settings(select_count=2))
    monkeypatch.setattr(
        select_skills,
        "build_optional_llm",
        lambda: _FakeLlm('{"skill_indices": [1, 2, 3]}'),
    )

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs(),
        query="general macro mechanism",
    )

    assert result["selected_skill_indices"] == [1, 2]
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: llm_skill_indices_exceed_max_count"


def test_run_select_skills_returns_empty_selection_when_no_templates() -> None:
    result = select_skills.run_select_skills(
        snapshot_outputs={"main_skill_json": {"main_skills": []}},
        query="anything",
    )

    assert result["selected_skill_indices"] == []
    assert result["selected_section_ids"] == []
    assert result["selected_skill_index"] is None
    assert result["selected_section_id"] is None
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: no_skill_templates"


def test_run_select_skills_recalls_top_candidates_before_llm(monkeypatch: object) -> None:
    monkeypatch.setattr(
        select_skills,
        "get_settings",
        lambda: _settings(recall_limit=20, select_count=3),
    )
    monkeypatch.setattr(
        select_skills,
        "build_optional_llm",
        lambda: _FakeLlm('{"skill_indices": [29]}'),
    )

    result = select_skills.run_select_skills(
        snapshot_outputs=_snapshot_outputs_with_count(30),
        query="labor market wage pressure",
    )

    assert result["selected_skill_indices"] == [1, 2, 30]
    assert result["selected_section_ids"] == ["section-1", "section-2", "section-30"]
    assert result["selected_skill_index"] == 1
    assert result["selected_section_id"] == "section-1"
    assert result["selection_mode"] == "fallback_rule"
    assert result["selection_warning"] == "fallback_used: llm_skill_index_out_of_range"
