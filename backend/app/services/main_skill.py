"""封装主技能生成阶段，负责输出 main_skill_json。"""

from __future__ import annotations

from pathlib import Path


def run_main_skill(input_json: Path, output_json: Path) -> dict[str, str]:
    """执行 main_skill 阶段骨架逻辑。"""
    _ = (input_json, output_json)
    return {"stage": "main_skill", "status": "stub"}
