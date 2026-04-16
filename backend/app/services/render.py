"""执行渲染阶段，将主/子技能 JSON 转为 Markdown 产物。"""

from __future__ import annotations

from typing import Any


def run_render(main_skill_json: dict[str, Any], sub_skill_json: dict[str, Any]) -> dict[str, Any]:
    """渲染 main_skill_md 与 sub_skills_md_zip（最小结构）。"""
    main_lines = ["# Main Skills", ""]
    for skill in main_skill_json.get("main_skills", []):
        main_lines.extend(
            [
                f"## {skill['pattern_summary']['name']}",
                f"- section_id: {skill['section_id']}",
                f"- main_skill_id: {skill['main_skill_id']}",
                f"- description: {skill['pattern_summary']['description']}",
                "",
            ]
        )
    main_skill_md = "\n".join(main_lines).strip()

    sub_files: list[dict[str, str]] = []
    for sub in sub_skill_json.get("sub_skills", []):
        filename = f"{sub['main_skill_id']}_{sub['name'].replace(' ', '_').lower()}.md"
        content = "\n".join(
            [
                f"# {sub['name']}",
                "",
                f"- section_id: {sub['section_id']}",
                f"- main_skill_id: {sub['main_skill_id']}",
                f"- normalized_pattern: {sub['normalized_pattern']}",
                "",
                f"{sub['description']}",
            ]
        )
        sub_files.append({"name": filename, "content": content})

    return {"main_skill_md": main_skill_md, "sub_skills_md_zip": {"files": sub_files}}
