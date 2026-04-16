"""执行渲染阶段，将技能 JSON 转换为主技能与子技能 Markdown。"""

from __future__ import annotations

import json
from typing import Any


def _yaml_quote(value: str) -> str:
    """使用 JSON 字符串语法保证 frontmatter 转义安全。"""
    return json.dumps(value, ensure_ascii=False)


def _render_main_skill_md(main_skill: dict[str, Any]) -> str:
    """渲染单个主技能 Markdown。"""
    pattern_summary = main_skill.get("pattern_summary", {})
    signal_summary = main_skill.get("signal_summary", {})

    perspective = signal_summary.get("perspective", {})
    nature = signal_summary.get("nature", {})
    time_orientation = signal_summary.get("time_orientation", {})
    system_scope = signal_summary.get("system_scope", {})
    equilibrium_view = signal_summary.get("equilibrium_view", {})
    logic = signal_summary.get("logic", {})
    logic_values = logic.get("value", []) if isinstance(logic, dict) else []

    lines = [
        "---",
        f"name: {_yaml_quote(str(pattern_summary.get('name', 'Main Skill')))}",
        f"type: {_yaml_quote('main_skill')}",
        f"description: {_yaml_quote(str(pattern_summary.get('description', '')))}",
        f"section_id: {_yaml_quote(str(main_skill.get('section_id', '')))}",
        f"main_skill_id: {_yaml_quote(str(main_skill.get('main_skill_id', '')))}",
        f"perspective: {_yaml_quote(str(perspective.get('value', '')))}",
        f"nature: {_yaml_quote(str(nature.get('value', '')))}",
        f"time_orientation: {_yaml_quote(str(time_orientation.get('value', '')))}",
        f"system_scope: {_yaml_quote(str(system_scope.get('value', '')))}",
        f"equilibrium_view: {_yaml_quote(str(equilibrium_view.get('value', '')))}",
        "logic:",
    ]
    for item in logic_values if isinstance(logic_values, list) else []:
        lines.append(f"  - {_yaml_quote(str(item))}")

    lines.extend(
        [
            "---",
            "",
            "# Skill Summary",
            "",
            str(pattern_summary.get("description", "")),
            "",
            "# When to Use",
            "",
            str(pattern_summary.get("applicability", "")),
            "",
            "# Method Program",
            "",
            str(pattern_summary.get("chapter_method_summary", "")),
            "",
            "# Execution Skeleton",
            "",
        ]
    )
    core_steps = pattern_summary.get("core_steps", [])
    if isinstance(core_steps, list):
        for index, step in enumerate(core_steps, start=1):
            lines.append(f"{index}. {step}")

    lines.extend(["", "# Pattern Flow", ""])
    pattern_flow = pattern_summary.get("pattern_flow", [])
    if isinstance(pattern_flow, list):
        lines.append(" -> ".join(str(item) for item in pattern_flow))

    return "\n".join(lines).strip()


def _render_sub_skill_md(sub_skill: dict[str, Any]) -> str:
    """渲染单个子技能 Markdown。"""
    action_chain = sub_skill.get("abstract_action_chain", [])
    source_chunk_ids = sub_skill.get("source_chunk_ids", [])
    lines = [
        "---",
        f"name: {_yaml_quote(str(sub_skill.get('name', 'Sub Skill')))}",
        f"type: {_yaml_quote('sub_skill')}",
        f"section_id: {_yaml_quote(str(sub_skill.get('section_id', '')))}",
        f"main_skill_id: {_yaml_quote(str(sub_skill.get('main_skill_id', '')))}",
        f"normalized_pattern: {_yaml_quote(str(sub_skill.get('normalized_pattern', '')))}",
        "source_chunk_ids:",
    ]
    if isinstance(source_chunk_ids, list):
        for item in source_chunk_ids:
            lines.append(f"  - {item}")

    lines.extend(
        [
            "---",
            "",
            f"# {sub_skill.get('name', 'Sub Skill')}",
            "",
            "## Description",
            "",
            str(sub_skill.get("description", "")),
            "",
            "## Method Program Summary",
            "",
            str(sub_skill.get("method_program_summary", "")),
            "",
            "## Method Program Example",
            "",
            str(sub_skill.get("method_program_example", "")),
            "",
            "## Abstract Action Chain",
            "",
        ]
    )
    if isinstance(action_chain, list):
        for index, action in enumerate(action_chain, start=1):
            lines.append(f"{index}. {action}")
    return "\n".join(lines).strip()


def run_render(main_skill_json: dict[str, Any], sub_skill_json: dict[str, Any]) -> dict[str, Any]:
    """渲染主技能与子技能 Markdown 产物。"""
    main_skills = main_skill_json.get("main_skills", [])
    sub_skills = sub_skill_json.get("sub_skills", [])
    if not isinstance(main_skills, list):
        main_skills = []
    if not isinstance(sub_skills, list):
        sub_skills = []

    main_docs: list[str] = []
    for skill in main_skills:
        if isinstance(skill, dict):
            main_docs.append(_render_main_skill_md(skill))
    main_skill_md = "\n\n\n".join(main_docs).strip()

    sub_skill_files: list[dict[str, str]] = []
    for index, skill in enumerate(sub_skills, start=1):
        if not isinstance(skill, dict):
            continue
        name = str(skill.get("name", f"sub_skill_{index}"))
        safe_name = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in name).strip(
            "_"
        )
        if not safe_name:
            safe_name = f"sub_skill_{index}"
        sub_skill_files.append(
            {
                "name": f"{index:03d}_{safe_name}.md",
                "content": _render_sub_skill_md(skill),
            }
        )

    return {
        "main_skill_md": main_skill_md,
        "sub_skill_files": sub_skill_files,
    }
