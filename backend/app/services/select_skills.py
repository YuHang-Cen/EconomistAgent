"""封装技能选择阶段，按 query 选择 main/sub skills。"""

from __future__ import annotations

from pathlib import Path


def run_select_skills(snapshot_json: Path, query: str) -> dict[str, str]:
    """执行 select_skills 阶段骨架逻辑。"""
    _ = (snapshot_json, query)
    return {"stage": "select_skills", "status": "stub"}
