"""执行回答阶段，基于选中的技能生成结构化 answer_json。"""

from __future__ import annotations

from typing import Any


def run_answer_with_skills(
    query: str, selected: dict[str, Any], snapshot_outputs: dict[str, Any]
) -> dict[str, Any]:
    """构造最小可读的 answer_json。"""
    selected_main_skill_id = selected.get("selected_main_skill_id")
    selected_sub_skill_names = selected.get("selected_sub_skill_names", [])
    main_skills = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])

    selected_main = next(
        (skill for skill in main_skills if skill["main_skill_id"] == selected_main_skill_id),
        None,
    )

    reasoning_summary = (
        selected_main["pattern_summary"]["chapter_method_summary"]
        if selected_main
        else "No matching main skill found."
    )
    return {
        "query": query,
        "selected_main_skill_id": selected_main_skill_id,
        "selected_sub_skill_names": selected_sub_skill_names,
        "answer": {
            "title": "Methodology-driven answer",
            "summary": reasoning_summary,
            "body": (
                "This answer is generated with a deterministic skill-selection baseline. "
                "It traces assumptions, mechanism, and implications."
            ),
        },
    }
