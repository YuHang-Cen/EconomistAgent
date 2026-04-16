"""执行主技能生成阶段，按章节聚合 method_analysis 产出 main_skill。"""

from __future__ import annotations

import json
import math
from typing import Any

from app.services.llm_utils import invoke_prompt_for_json, load_prompt, render_prompt

PROMPT_PLACEHOLDER = "{{MAIN_SKILL_INPUT_JSON}}"


def _require_non_empty_string(value: Any) -> str:
    """校验并返回非空字符串。"""
    if not isinstance(value, str):
        return ""
    return value.strip()


def _normalize_signal_node(value: Any, allow_list: bool = False) -> tuple[Any, str] | None:
    """归一化 signal_summary 的 {value, notes} 结构。"""
    if not isinstance(value, dict):
        return None
    notes = _require_non_empty_string(value.get("notes"))
    if not notes:
        return None

    raw_value = value.get("value")
    if allow_list:
        if not isinstance(raw_value, list):
            return None
        normalized_list = [item for item in raw_value if isinstance(item, str) and item.strip()]
        if not normalized_list:
            return None
        return normalized_list, notes

    scalar = _require_non_empty_string(raw_value)
    if not scalar:
        return None
    return scalar, notes


def _heuristic_main_skill(section_title: str, section_payload: dict[str, Any]) -> dict[str, Any]:
    """模型不可用时的主技能兜底生成。"""
    raw_patterns = section_payload["raw_pattern_chain"]
    method_signals = section_payload["method_signals_chain"]
    perspective = method_signals[0].get("perspective", "Institutional Analysis")
    nature = method_signals[0].get("nature", "Positive")
    time_orientation = method_signals[0].get("time_orientation", "Dynamic Analysis")
    system_scope = method_signals[0].get("system_scope", "Open System")
    equilibrium_view = method_signals[0].get("equilibrium_view", "Process Analysis")
    logic = method_signals[0].get("logic", ["Causal Reasoning"])
    if not isinstance(logic, list) or not logic:
        logic = ["Causal Reasoning"]

    return {
        "pattern_summary": {
            "name": f"{section_title} Method Pattern",
            "description": (
                "Extract the chapter's core assumptions and trace causal transmission paths."
            ),
            "applicability": (
                "Use this method when the question asks for mechanism tracing under explicit "
                "institutional constraints."
            ),
            "core_steps": [
                "define baseline assumptions",
                "trace mechanism progression",
                "compare outcome under constraints",
            ],
            "pattern_flow": ["assumption", "mechanism", "outcome"],
            "chapter_method_summary": (
                f"Synthesize {len(raw_patterns)} chunk-level patterns into one executable "
                "causal analysis program."
            ),
        },
        "signal_summary": {
            "perspective": {"value": str(perspective), "notes": "stable across chapter"},
            "nature": {"value": str(nature), "notes": "primarily explanatory"},
            "time_orientation": {
                "value": str(time_orientation),
                "notes": "tracks transitions over time",
            },
            "system_scope": {"value": str(system_scope), "notes": "considers system interactions"},
            "equilibrium_view": {
                "value": str(equilibrium_view),
                "notes": "focus on adjustment process",
            },
            "logic": {
                "value": [str(item) for item in logic if isinstance(item, str)]
                or ["Causal Reasoning"],
                "notes": "dominant reasoning families",
            },
        },
        "confidence": 0.8,
    }


def _invoke_main_skill(section_title: str, section_payload: dict[str, Any]) -> dict[str, Any]:
    """调用 Prompt+LLM 生成章节主技能，不可用时使用兜底。"""
    template = load_prompt("main_skills_prompt.md", required_placeholders=[PROMPT_PLACEHOLDER])
    prompt = render_prompt(
        template,
        {PROMPT_PLACEHOLDER: json.dumps(section_payload, ensure_ascii=False, indent=2)},
    )
    parsed = invoke_prompt_for_json(prompt)
    if parsed is None:
        return _heuristic_main_skill(section_title=section_title, section_payload=section_payload)

    pattern_summary = parsed.get("pattern_summary")
    signal_summary = parsed.get("signal_summary")
    confidence = parsed.get("confidence")

    if not isinstance(pattern_summary, dict) or not isinstance(signal_summary, dict):
        return _heuristic_main_skill(section_title=section_title, section_payload=section_payload)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return _heuristic_main_skill(section_title=section_title, section_payload=section_payload)
    confidence_value = float(confidence)
    if confidence_value < 0 or confidence_value > 1 or math.isnan(confidence_value):
        return _heuristic_main_skill(section_title=section_title, section_payload=section_payload)

    description = _require_non_empty_string(pattern_summary.get("description"))
    applicability = _require_non_empty_string(pattern_summary.get("applicability"))
    chapter_method_summary = _require_non_empty_string(
        pattern_summary.get("chapter_method_summary")
    )
    raw_core_steps = pattern_summary.get("core_steps")
    raw_pattern_flow = pattern_summary.get("pattern_flow")
    if not isinstance(raw_core_steps, list) or not isinstance(raw_pattern_flow, list):
        return _heuristic_main_skill(section_title=section_title, section_payload=section_payload)
    core_steps = [item for item in raw_core_steps if isinstance(item, str) and item.strip()]
    pattern_flow = [item for item in raw_pattern_flow if isinstance(item, str) and item.strip()]
    if (
        not all([description, applicability, chapter_method_summary])
        or not core_steps
        or not pattern_flow
    ):
        return _heuristic_main_skill(section_title=section_title, section_payload=section_payload)

    perspective = _normalize_signal_node(signal_summary.get("perspective"))
    nature = _normalize_signal_node(signal_summary.get("nature"))
    time_orientation = _normalize_signal_node(signal_summary.get("time_orientation"))
    system_scope = _normalize_signal_node(signal_summary.get("system_scope"))
    equilibrium_view = _normalize_signal_node(signal_summary.get("equilibrium_view"))
    logic = _normalize_signal_node(signal_summary.get("logic"), allow_list=True)
    if not all([perspective, nature, time_orientation, system_scope, equilibrium_view, logic]):
        return _heuristic_main_skill(section_title=section_title, section_payload=section_payload)
    assert perspective is not None
    assert nature is not None
    assert time_orientation is not None
    assert system_scope is not None
    assert equilibrium_view is not None
    assert logic is not None
    perspective_value, perspective_notes = perspective
    nature_value, nature_notes = nature
    time_orientation_value, time_orientation_notes = time_orientation
    system_scope_value, system_scope_notes = system_scope
    equilibrium_view_value, equilibrium_view_notes = equilibrium_view
    logic_values, logic_notes = logic

    return {
        "pattern_summary": {
            "name": f"{section_title} Method Pattern",
            "description": description,
            "applicability": applicability,
            "core_steps": core_steps,
            "pattern_flow": pattern_flow,
            "chapter_method_summary": chapter_method_summary,
        },
        "signal_summary": {
            "perspective": {"value": perspective_value, "notes": perspective_notes},
            "nature": {"value": nature_value, "notes": nature_notes},
            "time_orientation": {
                "value": time_orientation_value,
                "notes": time_orientation_notes,
            },
            "system_scope": {"value": system_scope_value, "notes": system_scope_notes},
            "equilibrium_view": {
                "value": equilibrium_view_value,
                "notes": equilibrium_view_notes,
            },
            "logic": {"value": logic_values, "notes": logic_notes},
        },
        "confidence": round(confidence_value, 4),
    }


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


def run_main_skill(method_analysis: dict[str, Any]) -> dict[str, Any]:
    """从 method_analysis 聚合生成章节主技能。"""
    chunks = method_analysis.get("chunks", [])
    if not isinstance(chunks, list) or not chunks:
        return {"main_skills": []}

    sections: dict[str, dict[str, Any]] = {}
    section_order: list[str] = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        section_id = _require_non_empty_string(chunk.get("section_id"))
        section_title = _require_non_empty_string(chunk.get("section_title")) or "Section"
        analysis = chunk.get("analysis")
        if not section_id or not isinstance(analysis, dict):
            continue
        method_patterns = analysis.get("methodPatterns")
        method_signals = analysis.get("methodSignals")
        if not isinstance(method_patterns, dict) or not isinstance(method_signals, dict):
            continue

        if section_id not in sections:
            section_order.append(section_id)
            sections[section_id] = {
                "section_title": section_title,
                "raw_pattern_chain": [],
                "method_signals_chain": [],
            }
        sections[section_id]["raw_pattern_chain"].append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "raw_pattern": method_patterns.get("raw_pattern", ""),
            }
        )
        sections[section_id]["method_signals_chain"].append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "perspective": method_signals.get("perspective", ""),
                "nature": method_signals.get("nature", ""),
                "time_orientation": method_signals.get("time_orientation", ""),
                "system_scope": method_signals.get("system_scope", ""),
                "equilibrium_view": method_signals.get("equilibrium_view", ""),
                "logic": method_signals.get("logic", []),
            }
        )

    main_skills: list[dict[str, Any]] = []
    for index, section_id in enumerate(section_order, start=1):
        payload = sections[section_id]
        section_title = payload["section_title"]
        generated = _invoke_main_skill(section_title=section_title, section_payload=payload)
        main_skills.append(
            {
                "section_id": section_id,
                "main_skill_id": f"main_skill_{index:03d}",
                "pattern_summary": generated["pattern_summary"],
                "signal_summary": generated["signal_summary"],
                "confidence": generated["confidence"],
            }
        )

    filtered = _drop_low_confidence(main_skills)
    return {"main_skills": filtered}
