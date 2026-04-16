"""执行主技能生成阶段，按章节产出 main_skill_json。"""

from __future__ import annotations

from typing import Any


def run_main_skill(method_analysis: dict[str, Any]) -> dict[str, Any]:
    """从 method_analysis 聚合出章节级 main skills。"""
    by_chapter: dict[str, list[dict[str, Any]]] = {}
    for chunk in method_analysis.get("chunks", []):
        chapter_id = str(chunk["chapter_id"])
        by_chapter.setdefault(chapter_id, []).append(chunk)

    main_skills: list[dict[str, Any]] = []
    for idx, (chapter_id, chunks) in enumerate(by_chapter.items(), start=1):
        main_skills.append(
            {
                "section_id": chapter_id,
                "main_skill_id": f"main-skill-{idx}",
                "pattern_summary": {
                    "name": f"Chapter {idx} causal diagnosis",
                    "description": "Explain assumptions and causal links in chapter arguments.",
                    "applicability": "Use when analyzing policy claims in this chapter.",
                    "core_steps": [
                        "identify assumptions",
                        "trace mechanism",
                        "evaluate outcomes",
                    ],
                    "pattern_flow": ["assumption", "mechanism", "outcome"],
                    "chapter_method_summary": f"Derived from {len(chunks)} method chunks.",
                },
                "signal_summary": {
                    "perspective": {"value": "institutional", "notes": "chapter-level aggregation"},
                    "nature": {"value": "analytical", "notes": "deterministic scaffold"},
                    "time_orientation": {"value": "dynamic", "notes": "tracks changes over time"},
                    "system_scope": {"value": "macro", "notes": "system-level narrative"},
                    "equilibrium_view": {
                        "value": "non-equilibrium",
                        "notes": "focus on transitions",
                    },
                    "logic": {
                        "value": ["causal", "comparative"],
                        "notes": "minimal deterministic set",
                    },
                },
                "confidence": 0.8,
            }
        )
    return {"main_skills": main_skills}
