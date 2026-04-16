"""执行子技能生成阶段，基于 main_skill 产出 sub_skill_json。"""

from __future__ import annotations

from typing import Any


def run_sub_skill(
    main_skill_json: dict[str, Any], method_analysis: dict[str, Any]
) -> dict[str, Any]:
    """为每个 main skill 生成一个最小可复用 sub skill。"""
    sub_skills: list[dict[str, Any]] = []
    chunks = method_analysis.get("chunks", [])
    for item in main_skill_json.get("main_skills", []):
        section_id = str(item["section_id"])
        main_skill_id = str(item["main_skill_id"])
        source_chunk_ids = [
            int(chunk["chunk_id"]) for chunk in chunks if str(chunk["chapter_id"]) == section_id
        ]
        sub_skills.append(
            {
                "section_id": section_id,
                "main_skill_id": main_skill_id,
                "name": f"Sub skill for {main_skill_id}",
                "description": "Operational checklist for chapter-level causal diagnosis.",
                "abstract_action_chain": [
                    "extract claim",
                    "match assumptions",
                    "assess mechanism",
                ],
                "method_program_summary": "Convert arguments into comparable causal chains.",
                "normalized_pattern": "causal-diagnosis",
                "source_chunk_ids": source_chunk_ids,
                "method_program_example": "Claim -> assumptions -> mechanism -> implication.",
            }
        )
    return {"sub_skills": sub_skills}
