"""封装回答生成阶段，基于选中技能输出 answer_json。"""

from __future__ import annotations

from pathlib import Path


def run_answer_with_skills(
    selected_skills_md: Path, query: str, output_json: Path
) -> dict[str, str]:
    """执行 answer_with_skills 阶段骨架逻辑。"""
    _ = (selected_skills_md, query, output_json)
    return {"stage": "answer", "status": "stub"}
