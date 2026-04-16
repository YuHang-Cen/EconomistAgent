"""封装渲染阶段，负责将技能 JSON 生成 Markdown 产物。"""

from __future__ import annotations

from pathlib import Path


def run_render(main_skill_json: Path, sub_skill_json: Path, output_dir: Path) -> dict[str, str]:
    """执行 render 阶段骨架逻辑。"""
    _ = (main_skill_json, sub_skill_json, output_dir)
    return {"stage": "render", "status": "stub"}
