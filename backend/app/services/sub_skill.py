"""执行子技能生成阶段，按 section_id+normalized_pattern 聚合生成 sub_skill。"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from app.services.llm_utils import invoke_prompt_for_json, load_prompt, render_prompt

PROMPT_PLACEHOLDER = "{{GROUP_METHOD_PATTERNS_JSON}}"


def _heuristic_sub_skill(
    section_id: str,
    main_skill_id: str,
    normalized_pattern: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """模型不可用时的子技能兜底生成。"""
    source_chunk_id_set: set[int] = set()
    for item in records:
        chunk_id = item.get("chunk_id")
        if isinstance(chunk_id, int):
            source_chunk_id_set.add(chunk_id)
    source_chunk_ids = sorted(source_chunk_id_set)
    example = ""
    for item in records:
        method_program = item.get("method_program")
        if isinstance(method_program, str) and method_program.strip():
            example = method_program.strip()
            break

    return {
        "section_id": section_id,
        "main_skill_id": main_skill_id,
        "name": f"{normalized_pattern} Sub Skill",
        "description": "Reusable micro-procedure for recurring method pattern in this section.",
        "abstract_action_chain": [
            "identify trigger condition",
            "apply core reasoning steps",
            "validate mechanism against outcomes",
        ],
        "method_program_summary": (
            "Abstract repeated actions into a compact procedure and adapt it to question context."
        ),
        "normalized_pattern": normalized_pattern,
        "source_chunk_ids": source_chunk_ids,
        "method_program_example": example,
    }


def _invoke_sub_skill(
    section_id: str,
    main_skill_id: str,
    normalized_pattern: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """调用 Prompt+LLM 生成子技能，不可用时使用兜底。"""
    template = load_prompt("sub_skills_prompt.md", required_placeholders=[PROMPT_PLACEHOLDER])
    prompt_payload = [
        {
            "chunk_id": item.get("chunk_id"),
            "raw_pattern": item.get("raw_pattern", ""),
            "normalized_pattern": normalized_pattern,
            "actions": item.get("actions", []),
            "method_program": item.get("method_program", ""),
        }
        for item in records
    ]
    prompt = render_prompt(
        template,
        {PROMPT_PLACEHOLDER: json.dumps(prompt_payload, ensure_ascii=False, indent=2)},
    )
    parsed = invoke_prompt_for_json(prompt)
    if parsed is None:
        return _heuristic_sub_skill(
            section_id=section_id,
            main_skill_id=main_skill_id,
            normalized_pattern=normalized_pattern,
            records=records,
        )

    name = parsed.get("name")
    description = parsed.get("description")
    abstract_action_chain = parsed.get("abstract_action_chain")
    method_program_summary = parsed.get("method_program_summary")
    if not isinstance(name, str) or not name.strip():
        return _heuristic_sub_skill(section_id, main_skill_id, normalized_pattern, records)
    if not isinstance(description, str) or not description.strip():
        return _heuristic_sub_skill(section_id, main_skill_id, normalized_pattern, records)
    if not isinstance(abstract_action_chain, list):
        return _heuristic_sub_skill(section_id, main_skill_id, normalized_pattern, records)
    normalized_chain = [
        item for item in abstract_action_chain if isinstance(item, str) and item.strip()
    ]
    if not normalized_chain:
        return _heuristic_sub_skill(section_id, main_skill_id, normalized_pattern, records)
    if not isinstance(method_program_summary, str) or not method_program_summary.strip():
        return _heuristic_sub_skill(section_id, main_skill_id, normalized_pattern, records)

    source_chunk_id_set: set[int] = set()
    for item in records:
        chunk_id = item.get("chunk_id")
        if isinstance(chunk_id, int):
            source_chunk_id_set.add(chunk_id)
    source_chunk_ids = sorted(source_chunk_id_set)
    example = ""
    for item in records:
        method_program = item.get("method_program")
        if isinstance(method_program, str) and method_program.strip():
            example = method_program.strip()
            break

    return {
        "section_id": section_id,
        "main_skill_id": main_skill_id,
        "name": name.strip(),
        "description": description.strip(),
        "abstract_action_chain": normalized_chain,
        "method_program_summary": method_program_summary.strip(),
        "normalized_pattern": normalized_pattern,
        "source_chunk_ids": source_chunk_ids,
        "method_program_example": example,
    }


def run_sub_skill(
    main_skill_json: dict[str, Any], method_analysis: dict[str, Any]
) -> dict[str, Any]:
    """按章节主技能与方法模式生成子技能列表。"""
    main_skills = main_skill_json.get("main_skills", [])
    chunks = method_analysis.get("chunks", [])
    if not isinstance(main_skills, list) or not isinstance(chunks, list):
        return {"sub_skills": []}

    main_skill_id_by_section: dict[str, str] = {}
    for item in main_skills:
        if not isinstance(item, dict):
            continue
        section_id = item.get("section_id")
        main_skill_id = item.get("main_skill_id")
        if isinstance(section_id, str) and isinstance(main_skill_id, str):
            main_skill_id_by_section[section_id] = main_skill_id

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        section_id = chunk.get("section_id")
        if not isinstance(section_id, str) or section_id not in main_skill_id_by_section:
            continue
        analysis = chunk.get("analysis")
        if not isinstance(analysis, dict):
            continue
        method_patterns = analysis.get("methodPatterns")
        if not isinstance(method_patterns, dict):
            continue
        normalized_pattern = method_patterns.get("normalized_pattern")
        if not isinstance(normalized_pattern, str) or not normalized_pattern.strip():
            continue

        grouped[(section_id, normalized_pattern.strip())].append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "raw_pattern": method_patterns.get("raw_pattern", ""),
                "actions": method_patterns.get("actions", []),
                "method_program": method_patterns.get("method_program", ""),
            }
        )

    sub_skills: list[dict[str, Any]] = []
    for section_id, normalized_pattern in sorted(grouped.keys()):
        records = grouped[(section_id, normalized_pattern)]
        main_skill_id = main_skill_id_by_section[section_id]
        sub_skills.append(
            _invoke_sub_skill(
                section_id=section_id,
                main_skill_id=main_skill_id,
                normalized_pattern=normalized_pattern,
                records=records,
            )
        )

    return {"sub_skills": sub_skills}
