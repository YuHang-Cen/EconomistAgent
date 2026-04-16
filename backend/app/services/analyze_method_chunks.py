"""执行方法分析阶段，按词数分块并产出 method_analysis 结构。"""

from __future__ import annotations

import re
from typing import Any

from app.infra.settings import get_settings
from app.services.llm_utils import invoke_prompt_for_json, load_prompt, render_prompt

PROMPT_PLACEHOLDER = "{{CHUNK_TEXT}}"


def _count_words(text: str) -> int:
    """统计词数用于分块边界控制。"""
    return len(re.findall(r"\b[\w'-]+\b", text))


def _chunk_segments(segments: list[dict[str, Any]], max_words: int) -> list[dict[str, Any]]:
    """按最大词数把段落合并成分析块。"""
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_words = 0

    for segment in segments:
        text = str(segment.get("content", "")).strip()
        if not text:
            continue
        words = _count_words(text)
        if current and current_words + words > max_words:
            chunks.append({"segments": current})
            current = []
            current_words = 0
        current.append(segment)
        current_words += words

    if current:
        chunks.append({"segments": current})
    return chunks


def _heuristic_analysis(chunk_text: str) -> dict[str, Any]:
    """在不可调用模型时给出可复现分析结果。"""
    first_line = " ".join(chunk_text.split()[:12])
    return {
        "methodPatterns": {
            "raw_pattern": f"Start from assumptions and causal links in: {first_line}.",
            "normalized_pattern": "Causal Derivation",
            "actions": [
                "establish assumptions",
                "trace causal mechanism",
                "evaluate comparative outcomes",
            ],
            "method_program": (
                "Establish assumptions, trace mechanisms across agents, and evaluate outcomes "
                "under changing constraints."
            ),
        },
        "methodSignals": {
            "perspective": "Institutional Analysis",
            "nature": "Positive",
            "time_orientation": "Dynamic Analysis",
            "system_scope": "Open System",
            "equilibrium_view": "Process Analysis",
            "logic": ["Causal Reasoning", "Comparative Reasoning"],
        },
    }


def _invoke_analysis_with_prompt(chunk_text: str) -> tuple[dict[str, Any], str | None]:
    """优先使用 Prompt+LLM 生成结构化分析，失败时返回兜底结果。"""
    template = load_prompt(
        "method_analysis_prompt.md",
        required_placeholders=[PROMPT_PLACEHOLDER],
    )
    prompt = render_prompt(template, {PROMPT_PLACEHOLDER: chunk_text})
    parsed = invoke_prompt_for_json(prompt)
    if parsed is None:
        return _heuristic_analysis(chunk_text), None

    method_patterns = parsed.get("methodPatterns")
    method_signals = parsed.get("methodSignals")
    if not isinstance(method_patterns, dict) or not isinstance(method_signals, dict):
        return _heuristic_analysis(chunk_text), "invalid model schema"

    raw_pattern = method_patterns.get("raw_pattern")
    normalized_pattern = method_patterns.get("normalized_pattern")
    actions = method_patterns.get("actions")
    method_program = method_patterns.get("method_program")

    if not isinstance(raw_pattern, str) or not raw_pattern.strip():
        return _heuristic_analysis(chunk_text), "invalid raw_pattern"
    if not isinstance(normalized_pattern, str) or not normalized_pattern.strip():
        return _heuristic_analysis(chunk_text), "invalid normalized_pattern"
    if not isinstance(actions, list):
        return _heuristic_analysis(chunk_text), "invalid actions"
    normalized_actions = [item for item in actions if isinstance(item, str) and item.strip()]
    if not normalized_actions:
        return _heuristic_analysis(chunk_text), "empty actions"
    if not isinstance(method_program, str) or not method_program.strip():
        return _heuristic_analysis(chunk_text), "invalid method_program"

    perspective = method_signals.get("perspective")
    nature = method_signals.get("nature")
    time_orientation = method_signals.get("time_orientation")
    system_scope = method_signals.get("system_scope")
    equilibrium_view = method_signals.get("equilibrium_view")
    logic = method_signals.get("logic")

    if not isinstance(perspective, str) or not perspective.strip():
        return _heuristic_analysis(chunk_text), "invalid methodSignals labels"
    if not isinstance(nature, str) or not nature.strip():
        return _heuristic_analysis(chunk_text), "invalid methodSignals labels"
    if not isinstance(time_orientation, str) or not time_orientation.strip():
        return _heuristic_analysis(chunk_text), "invalid methodSignals labels"
    if not isinstance(system_scope, str) or not system_scope.strip():
        return _heuristic_analysis(chunk_text), "invalid methodSignals labels"
    if not isinstance(equilibrium_view, str) or not equilibrium_view.strip():
        return _heuristic_analysis(chunk_text), "invalid methodSignals labels"
    if not isinstance(logic, list):
        return _heuristic_analysis(chunk_text), "invalid logic"
    normalized_logic = [item for item in logic if isinstance(item, str) and item.strip()]
    if not normalized_logic:
        return _heuristic_analysis(chunk_text), "empty logic"
    perspective_text = perspective.strip()
    nature_text = nature.strip()
    time_orientation_text = time_orientation.strip()
    system_scope_text = system_scope.strip()
    equilibrium_view_text = equilibrium_view.strip()

    return {
        "methodPatterns": {
            "raw_pattern": raw_pattern.strip(),
            "normalized_pattern": normalized_pattern.strip(),
            "actions": normalized_actions,
            "method_program": method_program.strip(),
        },
        "methodSignals": {
            "perspective": perspective_text,
            "nature": nature_text,
            "time_orientation": time_orientation_text,
            "system_scope": system_scope_text,
            "equilibrium_view": equilibrium_view_text,
            "logic": normalized_logic,
        },
    }, None


def run_analyze_method_chunks(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """执行 analyze 阶段并返回 method_analysis JSON。"""
    if not segments:
        return {"chunks": [], "errors": []}

    settings = get_settings()
    chunk_inputs = _chunk_segments(
        segments=segments, max_words=max(100, settings.method_chunk_max_words)
    )

    result_chunks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for chunk_index, chunk_input in enumerate(chunk_inputs, start=1):
        source_segments = chunk_input["segments"]
        chunk_text = "\n\n".join(str(item["content"]) for item in source_segments)
        paragraph_indexes = [str(item["chunk_id"]) for item in source_segments]
        chapter_id = str(source_segments[0]["chapter_id"])
        section_title = str(source_segments[0]["chapter_title"])

        analysis, warning = _invoke_analysis_with_prompt(chunk_text)
        if warning:
            errors.append(
                {
                    "chunk_id": chunk_index,
                    "paragraph_indexes": paragraph_indexes,
                    "error": warning,
                }
            )

        result_chunks.append(
            {
                "chunk_id": chunk_index,
                "section_id": chapter_id,
                "section_title": section_title,
                "paragraph_indexes": paragraph_indexes,
                "word_count": _count_words(chunk_text),
                "analysis": analysis,
            }
        )

    return {"chunks": result_chunks, "errors": errors}
