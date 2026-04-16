"""执行技能选择阶段，按可复现规则从快照中选择主技能与子技能。"""

from __future__ import annotations

from typing import Any


def _tokenize(text: str) -> list[str]:
    """把输入文本标准化为小写词项。"""
    return [token for token in text.lower().replace("_", " ").split() if token]


def _score(query_tokens: list[str], text: str) -> int:
    """按词项命中数计算稳定得分。"""
    body = text.lower()
    return sum(1 for token in query_tokens if token in body)


def run_select_skills(snapshot_outputs: dict[str, Any], query: str) -> dict[str, Any]:
    """基于 query 对 main/sub skills 执行确定性选择。"""
    main_skills = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    sub_skills = snapshot_outputs.get("sub_skill_json", {}).get("sub_skills", [])
    if not isinstance(main_skills, list) or not main_skills:
        return {"selected_main_skill_id": None, "selected_sub_skill_names": []}

    query_tokens = _tokenize(query)
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for index, skill in enumerate(main_skills):
        if not isinstance(skill, dict):
            continue
        pattern_summary = skill.get("pattern_summary", {})
        name = pattern_summary.get("name", "") if isinstance(pattern_summary, dict) else ""
        description = (
            pattern_summary.get("description", "") if isinstance(pattern_summary, dict) else ""
        )
        score = _score(query_tokens, f"{name} {description}")
        ranked.append((score, -index, skill))

    if not ranked:
        return {"selected_main_skill_id": None, "selected_sub_skill_names": []}

    ranked.sort(reverse=True)
    selected_main = ranked[0][2]
    selected_main_skill_id = selected_main.get("main_skill_id")
    if not isinstance(selected_main_skill_id, str) or not selected_main_skill_id:
        return {"selected_main_skill_id": None, "selected_sub_skill_names": []}

    selected_sub_skill_names: list[str] = []
    if isinstance(sub_skills, list):
        for item in sub_skills:
            if not isinstance(item, dict):
                continue
            if item.get("main_skill_id") != selected_main_skill_id:
                continue
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                selected_sub_skill_names.append(name.strip())

    return {
        "selected_main_skill_id": selected_main_skill_id,
        "selected_sub_skill_names": selected_sub_skill_names,
    }
