"""执行主技能生成阶段，按章节聚合 method_analysis 产出 main_skill。"""

from __future__ import annotations

import json
import math
import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI

from app.infra.settings import get_settings
from app.services.llm_utils import load_prompt, render_prompt

PROMPT_PLACEHOLDER = "{{MAIN_SKILL_INPUT_JSON}}"
DEFAULT_SINGLE_SECTION_TITLE = "Full Book"
DEFAULT_UNKNOWN_SECTION_TITLE = "Unknown Section"


@dataclass(frozen=True)
class ChunkMethodRecord:
    """Store extracted per-chunk method pattern and signal fields."""

    chunk_id: int
    section_id: str
    section_title: str
    raw_pattern: str
    perspective: str
    nature: str
    time_orientation: str
    system_scope: str
    equilibrium_view: str
    logic: list[str]


def _require_non_empty_string(value: Any) -> str:
    """校验并返回非空字符串。"""
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_text(value: Any) -> str:
    """Normalize arbitrary value into a trimmed string or empty string."""
    if isinstance(value, str):
        return value.strip()
    return ""


def _normalize_logic(value: Any) -> list[str]:
    """Normalize logic list by keeping only non-empty string items."""
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                items.append(text)
    return items


def _extract_chunk_records(data: dict[str, Any]) -> list[ChunkMethodRecord]:
    """Extract method fields from chunks sorted by chunk_id and grouped by section_title."""
    chunks = data.get("chunks", [])
    if not isinstance(chunks, list):
        raise ValueError("method_analysis must contain a 'chunks' list")

    has_section_title = any(
        isinstance(chunk, dict) and _normalize_text(chunk.get("section_title"))
        for chunk in chunks
    )

    extracted: list[ChunkMethodRecord] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue

        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, int):
            continue

        analysis = chunk.get("analysis")
        if not isinstance(analysis, dict):
            continue

        method_patterns = analysis.get("methodPatterns")
        method_signals = analysis.get("methodSignals")
        if not isinstance(method_patterns, dict) or not isinstance(method_signals, dict):
            continue

        raw_section_title = _normalize_text(chunk.get("section_title"))
        if has_section_title:
            section_title = raw_section_title or DEFAULT_UNKNOWN_SECTION_TITLE
        else:
            section_title = DEFAULT_SINGLE_SECTION_TITLE

        extracted.append(
            ChunkMethodRecord(
                chunk_id=chunk_id,
                section_id=_normalize_text(chunk.get("section_id")),
                section_title=section_title,
                raw_pattern=_normalize_text(method_patterns.get("raw_pattern")),
                perspective=_normalize_text(method_signals.get("perspective")),
                nature=_normalize_text(method_signals.get("nature")),
                time_orientation=_normalize_text(method_signals.get("time_orientation")),
                system_scope=_normalize_text(method_signals.get("system_scope")),
                equilibrium_view=_normalize_text(method_signals.get("equilibrium_view")),
                logic=_normalize_logic(method_signals.get("logic")),
            )
        )

    if not extracted:
        return []
    return sorted(extracted, key=lambda item: item.chunk_id)


def _group_records_by_section(
    records: list[ChunkMethodRecord],
) -> list[tuple[str, str, list[ChunkMethodRecord]]]:
    """Group records by section title while preserving appearance order."""
    section_map: OrderedDict[tuple[str, str], list[ChunkMethodRecord]] = OrderedDict()
    for record in records:
        key = (record.section_id, record.section_title)
        section_map.setdefault(key, []).append(record)

    grouped: list[tuple[str, str, list[ChunkMethodRecord]]] = []
    for (section_id, section_title), section_records in section_map.items():
        grouped.append((section_id, section_title, section_records))
    return grouped


def _build_intermediate_payload(records: list[ChunkMethodRecord]) -> dict[str, Any]:
    """Build per-section payload for main-skill synthesis."""
    return {
        "raw_pattern_chain": [
            {"chunk_id": item.chunk_id, "raw_pattern": item.raw_pattern}
            for item in records
        ],
        "method_signals_chain": [
            {
                "chunk_id": item.chunk_id,
                "perspective": item.perspective,
                "nature": item.nature,
                "time_orientation": item.time_orientation,
                "system_scope": item.system_scope,
                "equilibrium_view": item.equilibrium_view,
                "logic": item.logic,
            }
            for item in records
        ],
    }


def _build_llm(settings: Any) -> ChatOpenAI:
    """Build DeepSeek-compatible LLM client via ChatOpenAI."""
    api_key = _normalize_text(getattr(settings, "deepseek_api_key", None))
    if not api_key:
        api_key = _normalize_text(getattr(settings, "DEEPSEEK_API_KEY", None))
    if not api_key:
        import os

        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing environment variable: DEEPSEEK_API_KEY")

    model_name = (
        _normalize_text(getattr(settings, "model_name", None))
        or _normalize_text(getattr(settings, "MODEL_NAME", None))
        or "deepseek-chat"
    )
    api_base = (
        _normalize_text(getattr(settings, "api_base", None))
        or _normalize_text(getattr(settings, "API_BASE", None))
        or "https://api.deepseek.com"
    )

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_base,
        temperature=0,
    )


def _normalize_message_content(content: Any) -> str:
    """Normalize model response content to plain text."""
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
    """Extract JSON from fenced code block if present."""
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
    """Parse model output JSON with fallback extraction strategies."""
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
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError("Model output is not a valid JSON object.")


def _require_string(value: Any, field_path: str) -> str:
    """Validate and return a string value for a required field."""
    if not isinstance(value, str):
        raise ValueError(f"Field '{field_path}' must be a string.")
    text = value.strip()
    if not text:
        raise ValueError(f"Field '{field_path}' cannot be empty.")
    return text


def _require_string_allow_empty(value: Any, field_path: str) -> str:
    """Validate and return a string value (may be empty after trimming)."""
    if not isinstance(value, str):
        raise ValueError(f"Field '{field_path}' must be a string.")
    return value.strip()


def _require_string_list(value: Any, field_path: str) -> list[str]:
    """Validate and return a list of non-empty strings for a required field."""
    if not isinstance(value, list):
        raise ValueError(f"Field '{field_path}' must be a list.")
    items: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"Field '{field_path}[{idx}]' must be a string.")
        text = item.strip()
        if not text:
            raise ValueError(f"Field '{field_path}[{idx}]' cannot be empty.")
        items.append(text)
    return items


def _require_confidence(value: Any, field_path: str) -> float:
    """Validate confidence score as a finite number in [0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Field '{field_path}' must be a number in [0, 1].")
    score = float(value)
    if not math.isfinite(score):
        raise ValueError(f"Field '{field_path}' must be finite.")
    if score < 0 or score > 1:
        raise ValueError(f"Field '{field_path}' must be within [0, 1].")
    return score


def _normalize_main_skill_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize output into strict section main_skill schema."""
    if "pattern_summary" not in data or "signal_summary" not in data or "confidence" not in data:
        raise ValueError("Output must include 'pattern_summary', 'signal_summary' and 'confidence'.")

    pattern_summary = data.get("pattern_summary")
    signal_summary = data.get("signal_summary")
    confidence = _require_confidence(data.get("confidence"), "confidence")
    if not isinstance(pattern_summary, dict):
        raise ValueError("Field 'pattern_summary' must be an object.")
    if not isinstance(signal_summary, dict):
        raise ValueError("Field 'signal_summary' must be an object.")

    required_signal_keys = [
        "perspective",
        "nature",
        "time_orientation",
        "system_scope",
        "equilibrium_view",
        "logic",
    ]

    normalized_signals: dict[str, Any] = {}
    for key in required_signal_keys:
        node = signal_summary.get(key)
        if not isinstance(node, dict):
            raise ValueError(f"Field 'signal_summary.{key}' must be an object.")
        if key == "logic":
            value = _require_string_list(node.get("value"), f"signal_summary.{key}.value")
        else:
            value = _require_string(node.get("value"), f"signal_summary.{key}.value")
        notes = _require_string_allow_empty(node.get("notes"), f"signal_summary.{key}.notes")
        normalized_signals[key] = {"value": value, "notes": notes}

    name_raw = pattern_summary.get("name")
    name = name_raw.strip() if isinstance(name_raw, str) else ""
    normalized_pattern_summary = {
        # `name` is optional for backward compatibility; it will be filled later if empty.
        "name": name,
        "description": _require_string(pattern_summary.get("description"), "pattern_summary.description"),
        "applicability": _require_string(pattern_summary.get("applicability"), "pattern_summary.applicability"),
        "core_steps": _require_string_list(pattern_summary.get("core_steps"), "pattern_summary.core_steps"),
        "pattern_flow": _require_string_list(pattern_summary.get("pattern_flow"), "pattern_summary.pattern_flow"),
        "chapter_method_summary": _require_string(
            pattern_summary.get("chapter_method_summary"),
            "pattern_summary.chapter_method_summary",
        ),
    }

    return {
        "confidence": round(confidence, 4),
        "pattern_summary": normalized_pattern_summary,
        "signal_summary": normalized_signals,
    }


def _invoke_main_skill(section_payload: dict[str, Any], llm: ChatOpenAI) -> dict[str, Any]:
    """调用 Prompt+LLM 生成章节主技能。"""
    template = load_prompt("main_skills_prompt.md", required_placeholders=[PROMPT_PLACEHOLDER])
    prompt = render_prompt(
        template,
        {PROMPT_PLACEHOLDER: json.dumps(section_payload, ensure_ascii=False, indent=2)},
    )
    response = llm.invoke(prompt)
    raw_text = _normalize_message_content(response.content)
    parsed = _parse_json_with_recovery(raw_text)
    return _normalize_main_skill_shape(parsed)


def _drop_low_confidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 V3 规则删除最低 floor(N*0.2) 置信度项。"""
    drop_count = math.floor(len(items) * 0.2)
    if drop_count <= 0:
        return items

    ranked = sorted(
        list(enumerate(items)),
        key=lambda pair: (float(pair[1].get("confidence", 0.0)), pair[0]),
    )
    drop_indexes = {index for index, _ in ranked[:drop_count]}
    return [item for index, item in enumerate(items) if index not in drop_indexes]


def run_main_skill(
    method_analysis: dict[str, Any], *, drop_low_confidence: bool = True
) -> dict[str, Any]:
    """从 method_analysis 聚合生成章节主技能。"""
    if not isinstance(method_analysis, dict):
        return {"main_skills": []}

    records = _extract_chunk_records(method_analysis)
    if not records:
        return {"main_skills": []}

    section_groups = _group_records_by_section(records)
    settings = get_settings()
    llm = _build_llm(settings)

    main_skills: list[dict[str, Any]] = []
    for index, (section_id, section_title, section_records) in enumerate(section_groups, start=1):
        section_payload = _build_intermediate_payload(section_records)
        generated = _invoke_main_skill(section_payload=section_payload, llm=llm)
        if not str(generated.get("pattern_summary", {}).get("name", "")).strip():
            generated["pattern_summary"]["name"] = section_title or f"main_skill_{index:03d}"

        main_skills.append(
            {
                "section_id": section_id,
                "main_skill_id": f"main_skill_{index:03d}",
                "section_title": section_title,
                "pattern_summary": generated["pattern_summary"],
                "signal_summary": generated["signal_summary"],
                "confidence": generated["confidence"],
            }
        )

    if drop_low_confidence:
        filtered = _drop_low_confidence(main_skills)
        return {"main_skills": filtered}
    return {"main_skills": main_skills}
