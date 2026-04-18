"""Select one main skill via LLM skill_index with deterministic fallback."""

from __future__ import annotations

import json
from typing import Any

from app.services.llm_utils import (
    build_optional_llm,
    load_prompt,
    normalize_message_content,
    parse_json_with_recovery,
    render_prompt,
)

QUERY_PLACEHOLDER = "{{QUERY}}"
TEMPLATES_PLACEHOLDER = "{{SKILL_TEMPLATES_JSON}}"


def _empty_selection(selection_warning: str | None = None) -> dict[str, Any]:
    return {
        "selected_skill_index": None,
        "selected_section_id": None,
        "selection_mode": "fallback_rule",
        "selection_warning": selection_warning,
    }


def _tokenize(text: str) -> list[str]:
    """Normalize input text into lowercase tokens."""
    return [token for token in text.lower().replace("_", " ").split() if token]


def _score(query_tokens: list[str], text: str) -> int:
    """Count query-token hits in candidate text."""
    body = text.lower()
    return sum(1 for token in query_tokens if token in body)


def _build_skill_templates(snapshot_outputs: dict[str, Any]) -> list[dict[str, Any]]:
    main_skills = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    if not isinstance(main_skills, list):
        return []

    templates: list[dict[str, Any]] = []
    for skill in main_skills:
        if not isinstance(skill, dict):
            continue

        section_id = str(skill.get("section_id", "")).strip()
        if not section_id:
            continue

        pattern_summary = skill.get("pattern_summary", {})
        if not isinstance(pattern_summary, dict):
            pattern_summary = {}

        name = str(pattern_summary.get("name", "")).strip()
        description = str(pattern_summary.get("description", "")).strip()
        applicability = str(pattern_summary.get("applicability", "")).strip()
        if not name:
            name = str(skill.get("section_title", "")).strip() or str(
                skill.get("main_skill_id", "")
            ).strip()

        templates.append(
            {
                "skill_index": len(templates) + 1,
                "section_id": section_id,
                "name": name,
                "description": description,
                "applicability": applicability,
            }
        )

    return templates


def _fallback_select_skill_index(query: str, templates: list[dict[str, Any]]) -> int | None:
    if not templates:
        return None

    query_tokens = _tokenize(query)
    ranked: list[tuple[int, int]] = []
    for index, item in enumerate(templates):
        text = (
            f"{item.get('name', '')} "
            f"{item.get('description', '')} "
            f"{item.get('applicability', '')}"
        )
        ranked.append((_score(query_tokens, text), -index))

    ranked.sort(reverse=True)
    best_index = -ranked[0][1]
    skill_index = templates[best_index].get("skill_index")
    return skill_index if isinstance(skill_index, int) else None


def _select_with_llm(
    query: str, templates: list[dict[str, Any]]
) -> tuple[int | None, str | None]:
    llm = build_optional_llm()
    if llm is None:
        return None, "llm_unavailable"

    prompt_template = load_prompt(
        "select_skills_prompt.md",
        required_placeholders=[QUERY_PLACEHOLDER, TEMPLATES_PLACEHOLDER],
    )
    prompt = render_prompt(
        prompt_template,
        {
            QUERY_PLACEHOLDER: query,
            TEMPLATES_PLACEHOLDER: json.dumps(templates, ensure_ascii=False, indent=2),
        },
    )

    try:
        response = llm.invoke(prompt)
    except Exception:
        return None, "llm_invoke_error"

    raw_content = normalize_message_content(response.content).strip()
    try:
        parsed = parse_json_with_recovery(raw_content)
    except Exception:
        return None, "llm_invalid_json"

    skill_index = parsed.get("skill_index")
    if isinstance(skill_index, bool) or not isinstance(skill_index, int):
        return None, "llm_invalid_skill_index_type"
    if skill_index < 1 or skill_index > len(templates):
        return None, "llm_skill_index_out_of_range"

    return skill_index, None


def run_select_skills(snapshot_outputs: dict[str, Any], query: str) -> dict[str, Any]:
    """Select one skill by index and map it to section_id."""
    templates = _build_skill_templates(snapshot_outputs)
    if not templates:
        return _empty_selection("fallback_used: no_skill_templates")

    selected_skill_index, llm_error_reason = _select_with_llm(query=query, templates=templates)
    selection_mode = "llm"
    selection_warning: str | None = None

    if selected_skill_index is None:
        selected_skill_index = _fallback_select_skill_index(query=query, templates=templates)
        selection_mode = "fallback_rule"
        if llm_error_reason:
            selection_warning = f"fallback_used: {llm_error_reason}"
        else:
            selection_warning = "fallback_used: no_reason"

    if not isinstance(selected_skill_index, int):
        return _empty_selection(selection_warning or "fallback_used: no_skill_selected")

    selected_template = next(
        (item for item in templates if item.get("skill_index") == selected_skill_index),
        None,
    )
    selected_section_id = (
        str(selected_template.get("section_id", "")).strip()
        if isinstance(selected_template, dict)
        else ""
    )
    if not selected_section_id:
        return _empty_selection(selection_warning or "fallback_used: section_id_not_found")

    return {
        "selected_skill_index": selected_skill_index,
        "selected_section_id": selected_section_id,
        "selection_mode": selection_mode,
        "selection_warning": selection_warning,
    }
