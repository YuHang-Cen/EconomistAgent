"""
职能：从 method_analysis 按章节提取方法链路，调用 LLM 生成带置信度的章节级主技能 JSON，并过滤低置信度结果。
输入：method_analysis JSON 路径
中间产物（main_skill_input.json）：
  {
    "sections": [
      {
        "section_title": "...",
        "raw_pattern_chain": [{"chunk_id": 1, "raw_pattern": "..."}],
        "method_signals_chain": [
          {
            "chunk_id": 1,
            "perspective": "...",
            "nature": "...",
            "time_orientation": "...",
            "system_scope": "...",
            "equilibrium_view": "...",
            "logic": ["..."]
          }
        ]
      }
    ]
  }

最终输出（main_skill.json[list]）:
[
  {
    "section_title": "Chapter 1",
    "confidence": 0.85,
    "pattern_summary": {
      "description": "...",
      "applicability": "...",
      "core_steps": ["..."],
      "pattern_flow": ["..."],
      "chapter_method_summary": "..."
    },
    "signal_summary": {
      "perspective": {"value": "...", "notes": "..."},
      "nature": {"value": "...", "notes": "..."},
      "time_orientation": {"value": "...", "notes": "..."},
      "system_scope": {"value": "...", "notes": "..."},
      "equilibrium_view": {"value": "...", "notes": "..."},
      "logic": {"value": ["..."], "notes": "..."}
    }
  }
]
处理流程：
1. 数据提取
- 从每个 chunk 提取 raw_pattern 和 methodSignals
- 按 section_title 分组
2. 章节级 LLM 生成
- 每个章节调用一次 LLM
- 返回结果必须包含 confidence 字段（0-1）
- 占位符：{{MAIN_SKILL_INPUT_JSON}}
3. 置信度过滤
- 丢弃最低的 floor(N * 0.2) 条结果
- 保留置信度较高的章节主技能
4. 输出验证
- confidence 必须是 0-1 之间的有限数值
- pattern_summary 必须包含非空字段
- signal_summary 各字段必须为 {value, notes} 结构
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

DEFAULT_INPUT = Path(__file__).resolve().parent / "analysis_outputs/method_analysis.json"
DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "prompts/generate_main_skill_prompt_v1_en.md"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "main_skill_json"
DEFAULT_INPUT_FILE = "main_skill_input.json"
DEFAULT_OUTPUT_FILE = "main_skill.json"
DEFAULT_MODEL_NAME = "deepseek-chat"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
PROMPT_PLACEHOLDER = "{{MAIN_SKILL_INPUT_JSON}}"
DEFAULT_SINGLE_SECTION_TITLE = "Full Book"
DEFAULT_UNKNOWN_SECTION_TITLE = "Unknown Section"


@dataclass
class ChunkMethodRecord:
    """Store extracted per-chunk method pattern and signal fields."""

    chunk_id: int
    section_title: str
    raw_pattern: str
    perspective: str
    nature: str
    time_orientation: str
    system_scope: str
    equilibrium_view: str
    logic: list[str]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for main-skill generation."""
    parser = argparse.ArgumentParser(description="Generate chapter-level main_skill JSON from method_analysis output.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input method_analysis JSON path.")
    parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE, help="Prompt template path.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory path.")
    parser.add_argument("--input-file", type=str, default=DEFAULT_INPUT_FILE, help="Intermediate input filename.")
    parser.add_argument("--output-file", type=str, default=DEFAULT_OUTPUT_FILE, help="Final output filename.")
    parser.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME, help="LLM model name.")
    parser.add_argument("--api-base", type=str, default=DEFAULT_API_BASE, help="LLM API base URL.")
    parser.add_argument(
        "--force-malformed-output",
        action="store_true",
        help="Force malformed model output for error-path testing.",
    )
    return parser.parse_args()


def load_input_json(input_path: Path) -> dict[str, Any]:
    """Load and validate the input JSON root and chunks array."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input JSON must be an object.")
    chunks = data.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("Input JSON must contain a 'chunks' list.")
    return data


def normalize_logic(value: Any) -> list[str]:
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


def normalize_text(value: Any) -> str:
    """Normalize arbitrary value into a trimmed string or empty string."""
    if isinstance(value, str):
        return value.strip()
    return ""


def extract_chunk_records(data: dict[str, Any]) -> list[ChunkMethodRecord]:
    """Extract method fields from chunks sorted by chunk_id and grouped by section_title."""
    chunks = data.get("chunks", [])
    has_section_title = any(
        isinstance(chunk, dict) and normalize_text(chunk.get("section_title"))
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

        raw_section_title = normalize_text(chunk.get("section_title"))
        if has_section_title:
            section_title = raw_section_title or DEFAULT_UNKNOWN_SECTION_TITLE
        else:
            section_title = DEFAULT_SINGLE_SECTION_TITLE

        extracted.append(
            ChunkMethodRecord(
                chunk_id=chunk_id,
                section_title=section_title,
                raw_pattern=normalize_text(method_patterns.get("raw_pattern")),
                perspective=normalize_text(method_signals.get("perspective")),
                nature=normalize_text(method_signals.get("nature")),
                time_orientation=normalize_text(method_signals.get("time_orientation")),
                system_scope=normalize_text(method_signals.get("system_scope")),
                equilibrium_view=normalize_text(method_signals.get("equilibrium_view")),
                logic=normalize_logic(method_signals.get("logic")),
            )
        )

    if not extracted:
        raise ValueError("No valid chunk analysis records found in input.")
    return sorted(extracted, key=lambda item: item.chunk_id)


def group_records_by_section(records: list[ChunkMethodRecord]) -> list[tuple[str, list[ChunkMethodRecord]]]:
    """Group records by section title while preserving section appearance order."""
    section_map: OrderedDict[str, list[ChunkMethodRecord]] = OrderedDict()
    for record in records:
        section_map.setdefault(record.section_title, []).append(record)
    return list(section_map.items())


def build_intermediate_payload(records: list[ChunkMethodRecord]) -> dict[str, Any]:
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


def save_json(path: Path, payload: Any) -> None:
    """Save JSON payload to disk with UTF-8 and indentation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_prompt_template(prompt_path: Path) -> str:
    """Load prompt template and verify placeholder exists."""
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    template = prompt_path.read_text(encoding="utf-8")
    if PROMPT_PLACEHOLDER not in template:
        raise ValueError(f"Prompt file missing placeholder: {PROMPT_PLACEHOLDER}")
    return template


def render_prompt(template: str, intermediate_payload: dict[str, Any]) -> str:
    """Render final prompt with intermediate input JSON injected."""
    input_json = json.dumps(intermediate_payload, ensure_ascii=False, indent=2)
    return template.replace(PROMPT_PLACEHOLDER, input_json)


def build_llm(model_name: str, api_base: str) -> ChatOpenAI:
    """Build DeepSeek-compatible LLM client via ChatOpenAI."""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing environment variable: DEEPSEEK_API_KEY")
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_base,
        temperature=0,
    )


def normalize_message_content(content: Any) -> str:
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


def extract_fenced_json(text: str) -> str | None:
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


def extract_balanced_json_object(text: str) -> str | None:
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


def parse_json_with_recovery(raw_text: str) -> dict[str, Any]:
    """Parse model output JSON with fallback extraction strategies."""
    candidates: list[str] = [raw_text.strip()]

    fenced = extract_fenced_json(raw_text)
    if fenced:
        candidates.append(fenced)

    balanced = extract_balanced_json_object(raw_text)
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


def require_string(value: Any, field_path: str) -> str:
    """Validate and return a string value for a required field."""
    if not isinstance(value, str):
        raise ValueError(f"Field '{field_path}' must be a string.")
    text = value.strip()
    if not text:
        raise ValueError(f"Field '{field_path}' cannot be empty.")
    return text


def require_string_list(value: Any, field_path: str) -> list[str]:
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


def require_confidence(value: Any, field_path: str) -> float:
    """Validate confidence score as a finite number in [0, 1]."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Field '{field_path}' must be a number in [0, 1].")
    score = float(value)
    if not math.isfinite(score):
        raise ValueError(f"Field '{field_path}' must be finite.")
    if score < 0 or score > 1:
        raise ValueError(f"Field '{field_path}' must be within [0, 1].")
    return score


def normalize_main_skill_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize output into strict section main_skill schema."""
    if "pattern_summary" not in data or "signal_summary" not in data or "confidence" not in data:
        raise ValueError("Output must include 'pattern_summary', 'signal_summary' and 'confidence'.")

    pattern_summary = data.get("pattern_summary")
    signal_summary = data.get("signal_summary")
    confidence = require_confidence(data.get("confidence"), "confidence")
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
            value = require_string_list(node.get("value"), f"signal_summary.{key}.value")
        else:
            value = require_string(node.get("value"), f"signal_summary.{key}.value")
        notes = require_string(node.get("notes"), f"signal_summary.{key}.notes")
        normalized_signals[key] = {"value": value, "notes": notes}

    normalized_pattern_summary = {
        "description": require_string(pattern_summary.get("description"), "pattern_summary.description"),
        "applicability": require_string(pattern_summary.get("applicability"), "pattern_summary.applicability"),
        "core_steps": require_string_list(pattern_summary.get("core_steps"), "pattern_summary.core_steps"),
        "pattern_flow": require_string_list(pattern_summary.get("pattern_flow"), "pattern_summary.pattern_flow"),
        "chapter_method_summary": require_string(
            pattern_summary.get("chapter_method_summary"),
            "pattern_summary.chapter_method_summary",
        ),
    }

    return {
        "confidence": confidence,
        "pattern_summary": normalized_pattern_summary,
        "signal_summary": normalized_signals,
    }


def generate_main_skill_output(
    llm: ChatOpenAI,
    prompt: str,
    force_malformed_output: bool,
) -> dict[str, Any]:
    """Invoke model and return validated section-level main-skill JSON."""
    if force_malformed_output:
        raw_text = "forced malformed output for test"
    else:
        response = llm.invoke(prompt)
        raw_text = normalize_message_content(response.content)
    parsed = parse_json_with_recovery(raw_text)
    return normalize_main_skill_shape(parsed)


def drop_lowest_confidence_items(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Drop lowest floor(N * 0.2) items by confidence while preserving original order."""
    total = len(items)
    drop_count = math.floor(total * 0.2)
    if drop_count <= 0:
        return items, 0

    indexed = list(enumerate(items))
    to_drop = {
        idx for idx, _item in sorted(indexed, key=lambda pair: (pair[1]["confidence"], pair[0]))[:drop_count]
    }
    filtered = [item for idx, item in indexed if idx not in to_drop]
    return filtered, drop_count


def print_summary(
    chunk_count: int,
    section_count: int,
    kept_count: int,
    dropped_count: int,
    intermediate_path: Path,
    output_path: Path,
) -> None:
    """Print concise processing summary for the pipeline run."""
    print(
        f"Processed chunks: {chunk_count}, sections: {section_count}, "
        f"kept: {kept_count}, dropped: {dropped_count}"
    )
    print(f"Intermediate file: {intermediate_path}")
    print(f"Output file: {output_path}")


def main() -> None:
    """Program entry point for generating filtered section-level main_skill list."""
    args = parse_args()
    input_data = load_input_json(args.input)
    records = extract_chunk_records(input_data)
    section_groups = group_records_by_section(records)

    intermediate_sections: list[dict[str, Any]] = []
    for section_title, section_records in section_groups:
        section_payload = build_intermediate_payload(section_records)
        intermediate_sections.append(
            {
                "section_title": section_title,
                **section_payload,
            }
        )

    intermediate_path = args.output_dir / args.input_file
    save_json(intermediate_path, {"sections": intermediate_sections})

    prompt_template = load_prompt_template(args.prompt_file)
    llm = build_llm(model_name=args.model_name, api_base=args.api_base)

    section_outputs: list[dict[str, Any]] = []
    for section in intermediate_sections:
        section_title = section["section_title"]
        section_payload = {
            "raw_pattern_chain": section["raw_pattern_chain"],
            "method_signals_chain": section["method_signals_chain"],
        }
        prompt = render_prompt(prompt_template, section_payload)
        output = generate_main_skill_output(
            llm=llm,
            prompt=prompt,
            force_malformed_output=args.force_malformed_output,
        )
        section_outputs.append(
            {
                "section_title": section_title,
                **output,
            }
        )

    filtered_outputs, dropped_count = drop_lowest_confidence_items(section_outputs)

    output_path = args.output_dir / args.output_file
    save_json(output_path, filtered_outputs)

    print_summary(
        chunk_count=len(records),
        section_count=len(section_outputs),
        kept_count=len(filtered_outputs),
        dropped_count=dropped_count,
        intermediate_path=intermediate_path,
        output_path=output_path,
    )


if __name__ == "__main__":
    try:
        load_dotenv()
        main()
    except Exception as exc:  # pragma: no cover
        print(f"Execution failed: {exc}", file=sys.stderr)
        sys.exit(1)
