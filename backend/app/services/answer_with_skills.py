"""Generate answer_json using selected section-level skill context."""

from __future__ import annotations

from typing import Any

from app.domain.language import normalize_author_language
from app.services.llm_utils import (
    build_optional_llm,
    load_prompt_by_language,
    normalize_message_content,
    parse_json_with_recovery,
    render_prompt,
)

SKILLS_PLACEHOLDER = "{{SKILLS_CONTEXT}}"
QUERY_PLACEHOLDER = "{{QUERY}}"
MAIN_SKILLS_MD_KEY = "main_skills_md_json"
SUB_SKILLS_MD_KEY = "sub_skills_md_json"


def _normalize_selected_skill_index(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 1:
        return None
    return value


def _normalize_selected_skill_indices(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    normalized: list[int] = []
    seen: set[int] = set()
    for item in value:
        skill_index = _normalize_selected_skill_index(item)
        if skill_index is None or skill_index in seen:
            continue
        seen.add(skill_index)
        normalized.append(skill_index)
    return normalized


def _normalize_selected_section_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text else None


def _normalize_selected_section_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        section_id = _normalize_selected_section_id(item)
        if section_id is None or section_id in seen:
            continue
        seen.add(section_id)
        normalized.append(section_id)
    return normalized


def _normalize_selection_mode(value: Any) -> str:
    if value == "llm":
        return "llm"
    return "fallback_rule"


def _normalize_selection_warning(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text else None


def _read_sub_skill_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    skill_name = item.get("skill_name")
    if isinstance(skill_name, str) and skill_name.strip():
        return skill_name.strip()
    return ""


def _read_main_skill_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    pattern_summary = item.get("pattern_summary")
    if isinstance(pattern_summary, dict):
        pattern_name = pattern_summary.get("name")
        if isinstance(pattern_name, str) and pattern_name.strip():
            return pattern_name.strip()
    return ""


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _find_main_skill_name(
    snapshot_outputs: dict[str, Any],
    section_id: str,
) -> str | None:
    main_md_items = snapshot_outputs.get(MAIN_SKILLS_MD_KEY)
    if isinstance(main_md_items, list):
        for item in main_md_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != section_id:
                continue
            name = _read_main_skill_name(item)
            if name:
                return name

    main_json_items = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    if isinstance(main_json_items, list):
        for item in main_json_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != section_id:
                continue
            name = _read_main_skill_name(item)
            if name:
                return name

    return None


def _find_sub_skill_names(
    snapshot_outputs: dict[str, Any],
    section_id: str,
) -> list[str]:
    sub_names: list[str] = []
    sub_md_items = snapshot_outputs.get(SUB_SKILLS_MD_KEY)
    if isinstance(sub_md_items, list):
        for item in sub_md_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != section_id:
                continue
            name = _read_sub_skill_name(item)
            if name:
                sub_names.append(name)

    if sub_names:
        return _dedupe_preserve_order(sub_names)

    sub_json_items = snapshot_outputs.get("sub_skill_json", {}).get("sub_skills", [])
    if isinstance(sub_json_items, list):
        for item in sub_json_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != section_id:
                continue
            name = _read_sub_skill_name(item)
            if name:
                sub_names.append(name)

    return _dedupe_preserve_order(sub_names)


def _resolve_selected_skill_names(
    snapshot_outputs: dict[str, Any],
    selected_section_ids: list[str],
) -> tuple[list[str], list[str]]:
    if not selected_section_ids:
        return [], []

    main_names: list[str] = []
    sub_names: list[str] = []
    for section_id in selected_section_ids:
        main_name = _find_main_skill_name(snapshot_outputs, section_id)
        if main_name:
            main_names.append(main_name)
        sub_names.extend(_find_sub_skill_names(snapshot_outputs, section_id))

    return main_names, _dedupe_preserve_order(sub_names)


def _validate_answer_schema(value: Any) -> dict[str, str] | None:
    """Validate answer payload against the strict JSON schema."""
    if not isinstance(value, dict):
        return None

    expected_keys = {"title", "topic", "summary", "markdown"}
    actual_keys = set(value.keys())
    if actual_keys != expected_keys:
        return None

    normalized: dict[str, str] = {}
    for key in ("title", "topic", "summary", "markdown"):
        field_value = value.get(key)
        if not isinstance(field_value, str):
            return None
        text = field_value.strip()
        if not text:
            return None
        normalized[key] = text

    return normalized


def _build_context_from_markdown(
    snapshot_outputs: dict[str, Any],
    selected_section_ids: list[str],
) -> str:
    """Build context from markdown JSON artifacts when available."""
    if not selected_section_ids:
        return ""

    main_skills_md = snapshot_outputs.get(MAIN_SKILLS_MD_KEY)
    sub_skills_md = snapshot_outputs.get(SUB_SKILLS_MD_KEY)
    if not isinstance(main_skills_md, list) or not isinstance(sub_skills_md, list):
        return ""

    sections: list[str] = []
    for selected_section_id in selected_section_ids:
        selected_main_item: dict[str, Any] | None = None
        for item in main_skills_md:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != selected_section_id:
                continue
            markdown = item.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                selected_main_item = item
                break

        if selected_main_item is None:
            continue

        selected_sub_items: list[dict[str, Any]] = []
        for item in sub_skills_md:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != selected_section_id:
                continue
            markdown = item.get("markdown")
            if not isinstance(markdown, str) or not markdown.strip():
                continue
            selected_sub_items.append(item)

        lines: list[str] = ["=== Main Skill Markdown ==="]
        main_file_name = selected_main_item.get("file_name")
        if isinstance(main_file_name, str) and main_file_name:
            lines.append(f"file: {main_file_name}")
        lines.append(selected_main_item["markdown"])

        if selected_sub_items:
            lines.append("\n=== Sub Skills Markdown ===")
            for item in selected_sub_items:
                sub_name = _read_sub_skill_name(item)
                file_name = item.get("file_name", "")
                lines.append(f"\n--- {sub_name} ({file_name}) ---")
                lines.append(item["markdown"])

        sections.append("\n".join(lines).strip())

    return "\n\n".join(sections).strip()


def _build_context_from_json(
    snapshot_outputs: dict[str, Any],
    selected_section_ids: list[str],
) -> str:
    """Build fallback context from main/sub skill JSON artifacts."""
    if not selected_section_ids:
        return ""

    main_skills = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    sub_skills = snapshot_outputs.get("sub_skill_json", {}).get("sub_skills", [])
    sections: list[str] = []

    for selected_section_id in selected_section_ids:
        selected_main: dict[str, Any] | None = None
        if isinstance(main_skills, list):
            for skill in main_skills:
                if not isinstance(skill, dict):
                    continue
                if str(skill.get("section_id", "")).strip() == selected_section_id:
                    selected_main = skill
                    break

        selected_subs: list[dict[str, Any]] = []
        if isinstance(sub_skills, list):
            for item in sub_skills:
                if not isinstance(item, dict):
                    continue
                if str(item.get("section_id", "")).strip() != selected_section_id:
                    continue
                selected_subs.append(item)

        lines: list[str] = []
        if selected_main:
            pattern = selected_main.get("pattern_summary", {})
            if not isinstance(pattern, dict):
                pattern = {}
            lines.append("=== Main Skill ===")
            lines.append(f"name: {pattern.get('name', '')}")
            lines.append(f"description: {pattern.get('description', '')}")
            lines.append(f"applicability: {pattern.get('applicability', '')}")
            core_steps = pattern.get("core_steps", [])
            if isinstance(core_steps, list):
                lines.append("core_steps:")
                for step in core_steps:
                    lines.append(f"- {step}")

        if selected_subs:
            lines.append("\n=== Sub Skills ===")
            for item in selected_subs:
                lines.append(f"- {item.get('name', '')}: {item.get('description', '')}")

        if lines:
            sections.append("\n".join(lines).strip())

    return "\n\n".join(sections).strip()


def _build_context(
    snapshot_outputs: dict[str, Any],
    selected_section_ids: list[str],
) -> str:
    """Prefer markdown artifacts, fallback to JSON summary context."""
    markdown_context = _build_context_from_markdown(
        snapshot_outputs=snapshot_outputs,
        selected_section_ids=selected_section_ids,
    )
    if markdown_context:
        return markdown_context

    return _build_context_from_json(
        snapshot_outputs=snapshot_outputs,
        selected_section_ids=selected_section_ids,
    )


def _fallback_answer(query: str, context: str, *, language: str) -> dict[str, str]:
    """Return deterministic JSON answer when LLM is unavailable or invalid."""
    summary = context.splitlines()[:8]
    summary_text = " ".join(summary)
    normalized_language = normalize_author_language(language)
    if normalized_language == "chinese":
        return {
            "title": "方法论驱动回答",
            "topic": "经济问题分析",
            "summary": "基于最新作者方法快照进行生成式推演，聚焦机制链条与约束条件。",
            "markdown": (
                "# 分析\n\n"
                "本回答基于所选方法基线进行确定性综合，重点说明关键假设、机制演化和约束下的结果。"
                "\n\n"
                f"问题：{query}\n\n"
                f"技能上下文摘要：{summary_text}"
            ),
        }
    return {
        "title": "Methodology-driven answer",
        "topic": query,
        "summary": "Answer synthesized from latest author skill snapshot.",
        "markdown": (
            "# Analysis\n\n"
            "This response uses the selected methodology baseline and deterministic synthesis. "
            "It explains assumptions, mechanism transitions, and likely outcomes "
            "under constraints.\n\n"
            f"Question: {query}\n\n"
            f"Skill context summary: {summary_text}"
        ),
    }


def run_answer_with_skills(
    query: str,
    selected: dict[str, Any],
    snapshot_outputs: dict[str, Any],
    *,
    language: str = "english",
) -> dict[str, Any]:
    """Generate answer_json using selected skills and snapshot outputs."""
    normalized_language = normalize_author_language(language)

    selected_skill_indices = _normalize_selected_skill_indices(
        selected.get("selected_skill_indices")
    )
    if not selected_skill_indices:
        selected_skill_index = _normalize_selected_skill_index(selected.get("selected_skill_index"))
        if selected_skill_index is not None:
            selected_skill_indices = [selected_skill_index]

    selected_section_ids = _normalize_selected_section_ids(selected.get("selected_section_ids"))
    if not selected_section_ids:
        selected_section_id = _normalize_selected_section_id(selected.get("selected_section_id"))
        if selected_section_id is not None:
            selected_section_ids = [selected_section_id]

    selection_mode = _normalize_selection_mode(selected.get("selection_mode"))
    selection_warning = _normalize_selection_warning(selected.get("selection_warning"))
    selected_main_skill_names, selected_sub_skill_names = _resolve_selected_skill_names(
        snapshot_outputs=snapshot_outputs,
        selected_section_ids=selected_section_ids,
    )

    context = _build_context(
        snapshot_outputs=snapshot_outputs,
        selected_section_ids=selected_section_ids,
    )
    try:
        answer_payload = _fallback_answer(
            query=query,
            context=context,
            language=normalized_language,
        )
    except TypeError:
        answer_payload = _fallback_answer(query=query, context=context)

    template = load_prompt_by_language(
        "answer_with_skills_prompt.md",
        language=normalized_language,
        required_placeholders=[SKILLS_PLACEHOLDER, QUERY_PLACEHOLDER],
    )
    prompt = render_prompt(
        template,
        {
            SKILLS_PLACEHOLDER: context,
            QUERY_PLACEHOLDER: query,
        },
    )

    llm = build_optional_llm()
    if llm is not None:
        try:
            response = llm.invoke(prompt)
            normalized = normalize_message_content(response.content).strip()
            candidate = parse_json_with_recovery(normalized)
            validated = _validate_answer_schema(candidate)
            if validated is not None:
                answer_payload = validated
        except Exception:
            pass

    selected_skill_index = selected_skill_indices[0] if selected_skill_indices else None
    selected_section_id = selected_section_ids[0] if selected_section_ids else None
    selected_main_skill_name = (
        selected_main_skill_names[0] if selected_main_skill_names else None
    )

    return {
        "query": query,
        "selected_skill_indices": selected_skill_indices,
        "selected_section_ids": selected_section_ids,
        "selected_skill_index": selected_skill_index,
        "selected_section_id": selected_section_id,
        "selected_main_skill_names": selected_main_skill_names,
        "selected_main_skill_name": selected_main_skill_name,
        "selected_sub_skill_names": selected_sub_skill_names,
        "selection_mode": selection_mode,
        "selection_warning": selection_warning,
        "answer": answer_payload,
    }
