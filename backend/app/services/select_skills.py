"""Select one or more main skills via LLM skill_indices with deterministic fallback."""

from __future__ import annotations

import json
import re
from typing import Any

from app.domain.language import normalize_author_language
from app.infra.settings import get_settings
from app.services.llm_utils import (
    build_optional_llm,
    load_prompt_by_language,
    normalize_message_content,
    parse_json_with_recovery,
    render_prompt,
)

MAX_SELECTED_COUNT_PLACEHOLDER = "{{MAX_SELECTED_COUNT}}"
QUERY_PLACEHOLDER = "{{QUERY}}"
TEMPLATES_PLACEHOLDER = "{{SKILL_TEMPLATES_JSON}}"


def _empty_selection(selection_warning: str | None = None) -> dict[str, Any]:
    return {
        "selected_skill_indices": [],
        "selected_section_ids": [],
        "selected_skill_index": None,
        "selected_section_id": None,
        "selection_mode": "fallback_rule",
        "selection_warning": selection_warning,
    }


def _tokenize(text: str) -> list[str]:
    """Normalize mixed Chinese/English text into matchable tokens."""
    lowered = text.lower().replace("_", " ")
    ascii_tokens = re.findall(r"[a-z0-9]+", lowered)

    cjk_tokens: list[str] = []
    for seq in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(seq) >= 2:
            cjk_tokens.append(seq)
            cjk_tokens.extend(seq[idx : idx + 2] for idx in range(len(seq) - 1))

    seen: set[str] = set()
    merged: list[str] = []
    for token in [*ascii_tokens, *cjk_tokens]:
        if token in seen:
            continue
        seen.add(token)
        merged.append(token)
    return merged


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


def _rank_templates(query: str, templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    query_tokens = _tokenize(query)
    ranked = sorted(
        enumerate(templates),
        key=lambda pair: (
            -_score(
                query_tokens,
                (
                    f"{pair[1].get('name', '')} "
                    f"{pair[1].get('description', '')} "
                    f"{pair[1].get('applicability', '')}"
                ),
            ),
            pair[0],
        ),
    )
    return [item for _index, item in ranked]


def _fallback_select_skill_indices(
    query: str,
    templates: list[dict[str, Any]],
    *,
    max_count: int,
) -> list[int]:
    if not templates:
        return []

    fallback_indices: list[int] = []
    for item in _rank_templates(query, templates):
        skill_index = item.get("skill_index")
        if isinstance(skill_index, bool) or not isinstance(skill_index, int):
            continue
        fallback_indices.append(skill_index)
        if len(fallback_indices) >= max_count:
            break
    return sorted(fallback_indices)


def _recall_skill_templates(
    query: str,
    templates: list[dict[str, Any]],
    *,
    recall_limit: int | None,
) -> list[dict[str, Any]]:
    if not templates:
        return []
    if recall_limit is None or recall_limit <= 0 or len(templates) <= recall_limit:
        return templates
    return _rank_templates(query, templates)[:recall_limit]


def _validate_selected_skill_indices(
    parsed: Any,
    *,
    templates: list[dict[str, Any]],
    max_count: int,
) -> tuple[list[int] | None, str | None]:
    if not isinstance(parsed, dict) or set(parsed.keys()) != {"skill_indices"}:
        return None, "llm_invalid_json_shape"

    raw_skill_indices = parsed.get("skill_indices")
    if not isinstance(raw_skill_indices, list):
        return None, "llm_invalid_skill_indices_type"
    if not raw_skill_indices:
        return None, "llm_empty_skill_indices"
    if len(raw_skill_indices) > max_count:
        return None, "llm_skill_indices_exceed_max_count"

    valid_skill_indices = {
        item.get("skill_index") for item in templates if isinstance(item.get("skill_index"), int)
    }
    normalized: list[int] = []
    seen: set[int] = set()
    for skill_index in raw_skill_indices:
        if isinstance(skill_index, bool) or not isinstance(skill_index, int):
            return None, "llm_invalid_skill_index_type"
        if skill_index in seen:
            return None, "llm_skill_indices_duplicated"
        if skill_index not in valid_skill_indices:
            return None, "llm_skill_index_out_of_range"
        seen.add(skill_index)
        normalized.append(skill_index)

    if normalized != sorted(normalized):
        return None, "llm_skill_indices_not_sorted"

    return normalized, None


def _select_with_llm(
    query: str,
    templates: list[dict[str, Any]],
    *,
    language: str,
    max_count: int,
) -> tuple[list[int] | None, str | None]:
    llm = build_optional_llm()
    if llm is None:
        return None, "llm_unavailable"

    prompt_template = load_prompt_by_language(
        "select_skills_prompt.md",
        language=language,
        required_placeholders=[
            QUERY_PLACEHOLDER,
            TEMPLATES_PLACEHOLDER,
            MAX_SELECTED_COUNT_PLACEHOLDER,
        ],
    )
    prompt = render_prompt(
        prompt_template,
        {
            QUERY_PLACEHOLDER: query,
            TEMPLATES_PLACEHOLDER: json.dumps(templates, ensure_ascii=False, indent=2),
            MAX_SELECTED_COUNT_PLACEHOLDER: str(max_count),
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

    return _validate_selected_skill_indices(
        parsed,
        templates=templates,
        max_count=max_count,
    )


def _build_selection_result(
    *,
    templates: list[dict[str, Any]],
    selected_skill_indices: list[int],
    selection_mode: str,
    selection_warning: str | None,
) -> dict[str, Any]:
    if not selected_skill_indices:
        return _empty_selection(selection_warning or "fallback_used: no_skill_selected")

    template_by_index = {
        item.get("skill_index"): item
        for item in templates
        if isinstance(item, dict) and isinstance(item.get("skill_index"), int)
    }
    normalized_skill_indices: list[int] = []
    selected_section_ids: list[str] = []
    for skill_index in selected_skill_indices:
        selected_template = template_by_index.get(skill_index)
        if not isinstance(selected_template, dict):
            continue
        selected_section_id = str(selected_template.get("section_id", "")).strip()
        if not selected_section_id:
            continue
        normalized_skill_indices.append(skill_index)
        selected_section_ids.append(selected_section_id)

    if not selected_section_ids:
        return _empty_selection(selection_warning or "fallback_used: section_id_not_found")

    return {
        "selected_skill_indices": normalized_skill_indices,
        "selected_section_ids": selected_section_ids,
        "selected_skill_index": normalized_skill_indices[0],
        "selected_section_id": selected_section_ids[0],
        "selection_mode": selection_mode,
        "selection_warning": selection_warning,
    }


def run_select_skills(
    snapshot_outputs: dict[str, Any],
    query: str,
    *,
    language: str = "english",
) -> dict[str, Any]:
    """Select one or more skills by index and map them to section_ids."""
    templates = _build_skill_templates(snapshot_outputs)
    if not templates:
        return _empty_selection("fallback_used: no_skill_templates")

    settings = get_settings()

    raw_recall_limit = getattr(settings, "skills_select_recall_limit", 20)
    try:
        recall_limit = int(raw_recall_limit)
    except (TypeError, ValueError):
        recall_limit = 20

    raw_select_count = getattr(settings, "skills_select_count", 3)
    try:
        max_count = int(raw_select_count)
    except (TypeError, ValueError):
        max_count = 3
    if max_count <= 0:
        max_count = 3

    candidate_templates = _recall_skill_templates(
        query=query,
        templates=templates,
        recall_limit=recall_limit,
    )
    if not candidate_templates:
        return _empty_selection("fallback_used: no_recalled_skill_templates")

    normalized_language = normalize_author_language(language)
    selected_skill_indices, llm_error_reason = _select_with_llm(
        query=query,
        templates=candidate_templates,
        language=normalized_language,
        max_count=max_count,
    )
    selection_mode = "llm"
    selection_warning: str | None = None

    if selected_skill_indices is None:
        selected_skill_indices = _fallback_select_skill_indices(
            query=query,
            templates=candidate_templates,
            max_count=max_count,
        )
        selection_mode = "fallback_rule"
        if llm_error_reason:
            selection_warning = f"fallback_used: {llm_error_reason}"
        else:
            selection_warning = "fallback_used: no_reason"

    return _build_selection_result(
        templates=templates,
        selected_skill_indices=selected_skill_indices,
        selection_mode=selection_mode,
        selection_warning=selection_warning,
    )
