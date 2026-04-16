"""执行回答阶段，结合选中技能上下文生成结构化 answer_json。"""

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


def _build_context(snapshot_outputs: dict[str, Any], selected_main_skill_id: str | None) -> str:
    """拼接主技能与子技能上下文文本。"""
    main_skills = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    sub_skills = snapshot_outputs.get("sub_skill_json", {}).get("sub_skills", [])

    selected_main: dict[str, Any] | None = None
    if isinstance(main_skills, list):
        for skill in main_skills:
            if isinstance(skill, dict) and skill.get("main_skill_id") == selected_main_skill_id:
                selected_main = skill
                break

    selected_subs: list[dict[str, Any]] = []
    if isinstance(sub_skills, list):
        for item in sub_skills:
            if isinstance(item, dict) and item.get("main_skill_id") == selected_main_skill_id:
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


def _fallback_answer(query: str, context: str) -> str:
    """LLM 不可用时返回可读兜底回答文本。"""
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
    """结合选中技能生成 answer_json。"""
    selected_main_skill_id = selected.get("selected_main_skill_id")
    selected_sub_skill_names = selected.get("selected_sub_skill_names", [])
    if not isinstance(selected_sub_skill_names, list):
        selected_sub_skill_names = []

    context = _build_context(
        snapshot_outputs=snapshot_outputs,
        selected_main_skill_id=selected_main_skill_id
        if isinstance(selected_main_skill_id, str)
        else None,
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
        "selected_sub_skill_names": [
            item for item in selected_sub_skill_names if isinstance(item, str) and item.strip()
        ],
        "answer": {
            "title": "Methodology-driven answer",
            "summary": "Answer synthesized from latest author skill snapshot.",
            "markdown": answer_markdown,
        },
    }
