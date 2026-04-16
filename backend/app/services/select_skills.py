"""执行技能选择阶段，按 query 稳定选择主/子技能。"""

from __future__ import annotations

from typing import Any


def _score(query: str, text: str) -> int:
    """按词项重叠计算最小可复现得分。"""
    query_terms = [term for term in query.lower().split() if term]
    body = text.lower()
    return sum(1 for term in query_terms if term in body)


def run_select_skills(snapshot_outputs: dict[str, Any], query: str) -> dict[str, Any]:
    """从快照产物中选择最匹配 main_skill 与关联 sub_skills。"""
    main_skills = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    sub_skills = snapshot_outputs.get("sub_skill_json", {}).get("sub_skills", [])
    if not main_skills:
        return {"selected_main_skill_id": None, "selected_sub_skill_names": []}

    ranked = []
    for idx, skill in enumerate(main_skills):
        text = f"{skill['pattern_summary']['name']} {skill['pattern_summary']['description']}"
        ranked.append((_score(query=query, text=text), -idx, skill))
    ranked.sort(reverse=True)
    selected_main = ranked[0][2]
    selected_main_id = selected_main["main_skill_id"]

    matched_sub = [
        sub["name"] for sub in sub_skills if sub.get("main_skill_id") == selected_main_id
    ]
    return {
        "selected_main_skill_id": selected_main_id,
        "selected_sub_skill_names": matched_sub,
    }
