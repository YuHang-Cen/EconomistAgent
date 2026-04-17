"""Generate answer_json using selected skills context."""

from __future__ import annotations

from typing import Any

from app.services.llm_utils import (
    build_optional_llm,
    load_prompt,
    normalize_message_content,
    render_prompt,
)

SKILLS_PLACEHOLDER = "{{SKILLS_CONTEXT}}"
QUERY_PLACEHOLDER = "{{QUERY}}"
MAIN_SKILLS_MD_KEY = "main_skills_md_json"
SUB_SKILLS_MD_KEY = "sub_skills_md_json"


def _normalize_selected_sub_skill_names(value: Any) -> list[str]:
    """Normalize selected sub-skill names into non-empty strings."""
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
    return normalized


def _build_context_from_markdown(
    snapshot_outputs: dict[str, Any],
    selected_main_skill_id: str | None,
    selected_sub_skill_names: list[str],
) -> str:
    """Build context from markdown JSON artifacts when available."""
    if not selected_main_skill_id:
        return ""

    main_skills_md = snapshot_outputs.get(MAIN_SKILLS_MD_KEY)
    sub_skills_md = snapshot_outputs.get(SUB_SKILLS_MD_KEY)
    if not isinstance(main_skills_md, list) or not isinstance(sub_skills_md, list):
        return ""

    selected_main_item: dict[str, Any] | None = None
    for item in main_skills_md:
        if not isinstance(item, dict):
            continue
        if item.get("main_skill_id") != selected_main_skill_id:
            continue
        markdown = item.get("markdown")
        if isinstance(markdown, str) and markdown.strip():
            selected_main_item = item
            break

    if selected_main_item is None:
        return ""

    selected_names = set(selected_sub_skill_names)
    selected_sub_items: list[dict[str, Any]] = []
    for item in sub_skills_md:
        if not isinstance(item, dict):
            continue
        if item.get("main_skill_id") != selected_main_skill_id:
            continue
        sub_name = item.get("name")
        markdown = item.get("markdown")
        if not isinstance(sub_name, str) or not isinstance(markdown, str) or not markdown.strip():
            continue
        if selected_names and sub_name not in selected_names:
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
            sub_name = item.get("name", "")
            file_name = item.get("file_name", "")
            lines.append(f"\n--- {sub_name} ({file_name}) ---")
            lines.append(item["markdown"])

    return "\n".join(lines).strip()


def _build_context_from_json(
    snapshot_outputs: dict[str, Any],
    selected_main_skill_id: str | None,
    selected_sub_skill_names: list[str],
) -> str:
    """Build fallback context from main/sub skill JSON artifacts."""
    main_skills = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    sub_skills = snapshot_outputs.get("sub_skill_json", {}).get("sub_skills", [])

    selected_main: dict[str, Any] | None = None
    if isinstance(main_skills, list):
        for skill in main_skills:
            if isinstance(skill, dict) and skill.get("main_skill_id") == selected_main_skill_id:
                selected_main = skill
                break

    selected_names = set(selected_sub_skill_names)
    selected_subs: list[dict[str, Any]] = []
    if isinstance(sub_skills, list):
        for item in sub_skills:
            if not isinstance(item, dict):
                continue
            if item.get("main_skill_id") != selected_main_skill_id:
                continue
            if selected_names:
                name = item.get("name")
                if not isinstance(name, str) or name not in selected_names:
                    continue
            selected_subs.append(item)

    lines: list[str] = []
    if selected_main:
        pattern = selected_main.get("pattern_summary", {})
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

    return "\n".join(lines).strip()


def _build_context(
    snapshot_outputs: dict[str, Any],
    selected_main_skill_id: str | None,
    selected_sub_skill_names: list[str],
) -> str:
    """Prefer markdown artifacts, fallback to JSON summary context."""
    markdown_context = _build_context_from_markdown(
        snapshot_outputs=snapshot_outputs,
        selected_main_skill_id=selected_main_skill_id,
        selected_sub_skill_names=selected_sub_skill_names,
    )
    if markdown_context:
        return markdown_context
    return _build_context_from_json(
        snapshot_outputs=snapshot_outputs,
        selected_main_skill_id=selected_main_skill_id,
        selected_sub_skill_names=selected_sub_skill_names,
    )


def _fallback_answer(query: str, context: str) -> str:
    """Return deterministic readable answer when LLM is unavailable."""
    summary = context.splitlines()[:8]
    summary_text = " ".join(summary)
    return (
        "# Analysis\n\n"
        "This response uses the selected methodology baseline and deterministic synthesis. "
        "It explains assumptions, mechanism transitions, and likely outcomes under constraints.\n\n"
        f"Question: {query}\n\n"
        f"Skill context summary: {summary_text}"
    )


def run_answer_with_skills(
    query: str, selected: dict[str, Any], snapshot_outputs: dict[str, Any]
) -> dict[str, Any]:
    """Generate answer_json using selected skills and snapshot outputs."""
    selected_main_skill_id = selected.get("selected_main_skill_id")
    normalized_sub_skill_names = _normalize_selected_sub_skill_names(
        selected.get("selected_sub_skill_names", [])
    )

    context = _build_context(
        snapshot_outputs=snapshot_outputs,
        selected_main_skill_id=selected_main_skill_id
        if isinstance(selected_main_skill_id, str)
        else None,
        selected_sub_skill_names=normalized_sub_skill_names,
    )
    answer_markdown = _fallback_answer(query=query, context=context)

    template = load_prompt(
        "answer_with_skills_prompt.md",
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
            candidate = normalize_message_content(response.content).strip()
            if candidate:
                answer_markdown = candidate
        except Exception:
            pass

    return {
        "query": query,
        "selected_main_skill_id": selected_main_skill_id,
        "selected_sub_skill_names": normalized_sub_skill_names,
        "answer": {
            "title": "Methodology-driven answer",
            "summary": "Answer synthesized from latest author skill snapshot.",
            "markdown": answer_markdown,
        },
    }
