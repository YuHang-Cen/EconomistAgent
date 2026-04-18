"""执行子技能生成阶段，按 section_id+normalized_pattern 聚合生成 sub_skill。"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.infra.settings import get_settings
from app.services.llm_utils import build_required_llm, load_prompt, render_prompt

PROMPT_PLACEHOLDER = "{{GROUP_METHOD_PATTERNS_JSON}}"


@dataclass(frozen=True)
class MethodPatternRecord:
    """Store one extracted method pattern sample from a chunk."""

    section_id: str
    main_skill_id: str
    chunk_id: int
    raw_pattern: str
    normalized_pattern: str
    actions: list[str]
    method_program: str


def _normalize_actions(value: Any) -> list[str]:
    """Normalize action list by keeping non-empty string items only."""
    if not isinstance(value, list):
        return []
    actions: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                actions.append(text)
    return actions


def _normalize_text(value: Any) -> str:
    """Normalize arbitrary value into a trimmed string or empty string."""
    if isinstance(value, str):
        return value.strip()
    return ""


def _extract_method_pattern_records(
    main_skill_json: dict[str, Any],
    method_analysis: dict[str, Any],
) -> list[MethodPatternRecord]:
    """Extract method pattern records from chunk analyses, scoped by existing main skills."""
    main_skills = main_skill_json.get("main_skills", [])
    chunks = method_analysis.get("chunks", [])
    if not isinstance(main_skills, list) or not isinstance(chunks, list):
        return []

    main_skill_id_by_section: dict[str, str] = {}
    for item in main_skills:
        if not isinstance(item, dict):
            continue
        section_id = item.get("section_id")
        main_skill_id = item.get("main_skill_id")
        if isinstance(section_id, str) and isinstance(main_skill_id, str):
            main_skill_id_by_section[section_id] = main_skill_id

    records: list[MethodPatternRecord] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        section_id = chunk.get("section_id")
        chunk_id = chunk.get("chunk_id")
        if not isinstance(section_id, str) or section_id not in main_skill_id_by_section:
            continue
        if not isinstance(chunk_id, int):
            continue

        analysis = chunk.get("analysis")
        if not isinstance(analysis, dict):
            continue
        method_patterns = analysis.get("methodPatterns")
        if not isinstance(method_patterns, dict):
            continue

        normalized_pattern = method_patterns.get("normalized_pattern")
        if not isinstance(normalized_pattern, str):
            continue
        normalized_pattern = normalized_pattern.strip()
        if not normalized_pattern:
            continue

        raw_pattern = method_patterns.get("raw_pattern")
        method_program = method_patterns.get("method_program")
        actions = _normalize_actions(method_patterns.get("actions"))

        records.append(
            MethodPatternRecord(
                section_id=section_id,
                main_skill_id=main_skill_id_by_section[section_id],
                chunk_id=chunk_id,
                raw_pattern=raw_pattern.strip() if isinstance(raw_pattern, str) else "",
                normalized_pattern=normalized_pattern,
                actions=actions,
                method_program=method_program.strip() if isinstance(method_program, str) else "",
            )
        )

    return records


def _group_by_section_and_normalized_pattern(
    records: list[MethodPatternRecord],
) -> dict[tuple[str, str, str], list[MethodPatternRecord]]:
    """Group extracted records by (section_id, main_skill_id, normalized_pattern)."""
    grouped: dict[tuple[str, str, str], list[MethodPatternRecord]] = defaultdict(list)
    for record in records:
        key = (record.section_id, record.main_skill_id, record.normalized_pattern)
        grouped[key].append(record)

    for key, items in grouped.items():
        grouped[key] = sorted(items, key=lambda item: item.chunk_id)
    return grouped


def _build_llm(settings: Any) -> Any:
    """Create LLM client using effective runtime config."""
    _ = settings
    return build_required_llm()


def _normalize_message_content(content: Any) -> str:
    """Convert model response content into a plain text string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return str(content)


def _extract_fenced_json(text: str) -> str | None:
    """Extract JSON body from fenced markdown blocks, if present."""
    pattern = re.compile(r"```json\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()

    fallback = re.compile(r"```\s*(.*?)\s*```", re.DOTALL)
    fallback_match = fallback.search(text)
    if fallback_match:
        return fallback_match.group(1).strip()
    return None


def _extract_balanced_json_object(text: str) -> str | None:
    """Extract first balanced JSON object from free-form text."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        char = text[idx]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _parse_json_with_recovery(raw_text: str) -> dict[str, Any]:
    """Recover and parse JSON object from model output text."""
    candidates: list[str] = [raw_text.strip()]

    fenced = _extract_fenced_json(raw_text)
    if fenced:
        candidates.append(fenced)

    balanced = _extract_balanced_json_object(raw_text)
    if balanced:
        candidates.append(balanced)

    for candidate in candidates:
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    raise ValueError("Model output is not a valid JSON object.")


def _normalize_sub_skill_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM output into the required sub-skill fields."""
    name = data.get("name")
    description = data.get("description")
    abstract_action_chain = data.get("abstract_action_chain")
    method_program_summary = data.get("method_program_summary")

    if not isinstance(name, str):
        name = ""
    if not isinstance(description, str):
        description = ""
    if not isinstance(method_program_summary, str):
        method_program_summary = ""

    if not isinstance(abstract_action_chain, list):
        abstract_action_chain = []
    abstract_action_chain = [
        item.strip() for item in abstract_action_chain if isinstance(item, str) and item.strip()
    ]

    return {
        "name": name.strip(),
        "description": description.strip(),
        "abstract_action_chain": abstract_action_chain,
        "method_program_summary": method_program_summary.strip(),
    }


def _choose_method_program_example(records: list[MethodPatternRecord]) -> str:
    """Pick the first non-empty method_program by ascending chunk_id."""
    for record in sorted(records, key=lambda item: item.chunk_id):
        if record.method_program:
            return record.method_program
    return ""


def _render_group_prompt(template: str, records: list[MethodPatternRecord]) -> str:
    """Render prompt with grouped method pattern samples as JSON."""
    group_payload = [
        {
            "chunk_id": item.chunk_id,
            "raw_pattern": item.raw_pattern,
            "normalized_pattern": item.normalized_pattern,
            "actions": item.actions,
            "method_program": item.method_program,
        }
        for item in records
    ]
    grouped_json = json.dumps(group_payload, ensure_ascii=False, indent=2)
    return render_prompt(template, {PROMPT_PLACEHOLDER: grouped_json})


def _invoke_group_summary(
    llm: ChatOpenAI,
    prompt_template: str,
    records: list[MethodPatternRecord],
) -> dict[str, Any]:
    """Call LLM for one grouped pattern and return normalized fields."""
    prompt = _render_group_prompt(prompt_template, records)
    response = llm.invoke(prompt)
    raw_text = _normalize_message_content(response.content)
    parsed = _parse_json_with_recovery(raw_text)
    return _normalize_sub_skill_shape(parsed)


def _enrich_non_llm_fields(
    llm_result: dict[str, Any],
    section_id: str,
    main_skill_id: str,
    normalized_pattern: str,
    records: list[MethodPatternRecord],
) -> dict[str, Any]:
    """Add deterministic fields derived without LLM."""
    source_chunk_ids = sorted({item.chunk_id for item in records})
    enriched = dict(llm_result)
    enriched["section_id"] = section_id
    enriched["main_skill_id"] = main_skill_id
    enriched["normalized_pattern"] = normalized_pattern
    enriched["source_chunk_ids"] = source_chunk_ids
    enriched["method_program_example"] = _choose_method_program_example(records)
    return enriched


def run_sub_skill(
    main_skill_json: dict[str, Any], method_analysis: dict[str, Any]
) -> dict[str, Any]:
    """按章节主技能与方法模式生成子技能列表。"""
    records = _extract_method_pattern_records(main_skill_json, method_analysis)
    if not records:
        return {"sub_skills": []}

    grouped = _group_by_section_and_normalized_pattern(records)
    prompt_template = load_prompt("sub_skills_prompt.md", required_placeholders=[PROMPT_PLACEHOLDER])
    settings = get_settings()
    llm = _build_llm(settings)

    sub_skills: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for section_id, main_skill_id, normalized_pattern in sorted(grouped.keys()):
        pattern_records = grouped[(section_id, main_skill_id, normalized_pattern)]
        try:
            llm_result = _invoke_group_summary(
                llm=llm,
                prompt_template=prompt_template,
                records=pattern_records,
            )
            sub_skills.append(
                _enrich_non_llm_fields(
                    llm_result=llm_result,
                    section_id=section_id,
                    main_skill_id=main_skill_id,
                    normalized_pattern=normalized_pattern,
                    records=pattern_records,
                )
            )
        except Exception:
            # 保持当前服务风格：不向外暴露 meta/errors，只跳过失败分组
            continue

    return {"sub_skills": sub_skills}
