"""
职能：按 normalized_pattern 聚合方法样本，调用 LLM 生成 sub_skill JSON。
输入：method_analysis JSON 路径
输出：
{
  "sub_skills": [
    {
      "name": "技能名称",
      "description": "技能描述",
      "abstract_action_chain": ["抽象动作1", "抽象动作2"],
      "method_program_summary": "方法程序摘要",
      "normalized_pattern": "规范化的方法模式",
      "source_chunk_ids": [1, 2, 3],
      "method_program_example": "方法程序示例"
    }
  ],
  "meta": {
    "source_file": "method_analysis.json",
    "input_path": "/path/to/input",
    "generated_at_utc": "2024-01-01T00:00:00+00:00",
    "group_count": 5,
    "generated_count": 5,
    "error_count": 0,
    "model": {
      "provider": "deepseek",
      "model_name": "deepseek-chat",
      "api_base": "https://api.deepseek.com/v1"
    }
  },
  "errors": []
}
处理流程：
1. 数据提取
- 从每个 chunk 提取 methodPatterns 字段
- 过滤 normalized_pattern 为空的记录
2. 分组聚合
- 按 normalized_pattern 分组
- 同一 pattern 的样本聚合为一条记录
3. LLM 生成
- 每个分组调用一次 LLM
- 提示词包含该组所有样本
- 占位符：{{GROUP_METHOD_PATTERNS_JSON}}
4. 字段补充
- LLM 生成：name、description、abstract_action_chain、method_program_summary
- 自动计算：normalized_pattern、source_chunk_ids、method_program_example

"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

DEFAULT_INPUT = Path(__file__).resolve().parent / "analysis_outputs/method_analysis.json"
DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "prompts/generate_sub_skills_prompt_v1_en.md"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "sub_skill_json"
DEFAULT_OUTPUT_FILE = "sub_skill.json"
DEFAULT_PROVIDER = "deepseek"
DEFAULT_MODEL_NAME = "deepseek-chat"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
PROMPT_PLACEHOLDER = "{{GROUP_METHOD_PATTERNS_JSON}}"


@dataclass
class MethodPatternRecord:
    """Store one extracted method pattern sample from a chunk."""

    chunk_id: int
    raw_pattern: str
    normalized_pattern: str
    actions: list[str]
    method_program: str


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for sub-skill generation."""
    parser = argparse.ArgumentParser(
        description="Group method patterns by normalized pattern and generate sub_skill JSON."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input method analysis JSON path.")
    parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE, help="Prompt template path.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory path.")
    parser.add_argument("--output-file", type=str, default=DEFAULT_OUTPUT_FILE, help="Output JSON filename.")
    parser.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME, help="LLM model name.")
    parser.add_argument("--api-base", type=str, default=DEFAULT_API_BASE, help="LLM API base URL.")
    parser.add_argument(
        "--force-invalid-pattern",
        type=str,
        default="",
        help="Optional normalized_pattern to force malformed response for testing error handling.",
    )
    return parser.parse_args()


def load_input_json(input_path: Path) -> dict[str, Any]:
    """Load and validate the top-level input JSON object."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Input JSON must be an object.")
    chunks = raw.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("Input JSON must contain a 'chunks' array.")
    return raw


def normalize_actions(value: Any) -> list[str]:
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


def extract_method_pattern_records(data: dict[str, Any]) -> list[MethodPatternRecord]:
    """Extract method pattern records from chunk analyses."""
    records: list[MethodPatternRecord] = []
    for chunk in data.get("chunks", []):
        if not isinstance(chunk, dict):
            continue
        chunk_id = chunk.get("chunk_id")
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
        actions = normalize_actions(method_patterns.get("actions"))

        records.append(
            MethodPatternRecord(
                chunk_id=chunk_id,
                raw_pattern=raw_pattern.strip() if isinstance(raw_pattern, str) else "",
                normalized_pattern=normalized_pattern,
                actions=actions,
                method_program=method_program.strip() if isinstance(method_program, str) else "",
            )
        )
    return records


def group_by_normalized_pattern(
    records: list[MethodPatternRecord],
) -> dict[str, list[MethodPatternRecord]]:
    """Group extracted records by exact normalized pattern."""
    grouped: dict[str, list[MethodPatternRecord]] = {}
    for record in records:
        grouped.setdefault(record.normalized_pattern, []).append(record)

    for pattern, items in grouped.items():
        grouped[pattern] = sorted(items, key=lambda item: item.chunk_id)
    return grouped


def load_prompt_template(prompt_path: Path) -> str:
    """Load prompt template and verify required placeholder."""
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    template = prompt_path.read_text(encoding="utf-8")
    if PROMPT_PLACEHOLDER not in template:
        raise ValueError(f"Prompt file missing placeholder: {PROMPT_PLACEHOLDER}")
    return template


def render_group_prompt(template: str, records: list[MethodPatternRecord]) -> str:
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
    return template.replace(PROMPT_PLACEHOLDER, grouped_json)


def build_llm(model_name: str, api_base: str) -> ChatOpenAI:
    """Create a ChatOpenAI client using DeepSeek-compatible settings."""
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


def extract_fenced_json(text: str) -> str | None:
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
    """Recover and parse JSON object from model output text."""
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
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    raise ValueError("Model output is not a valid JSON object.")


def normalize_sub_skill_shape(data: dict[str, Any]) -> dict[str, Any]:
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


def choose_method_program_example(records: list[MethodPatternRecord]) -> str:
    """Pick the first non-empty method_program by ascending chunk_id."""
    for record in sorted(records, key=lambda item: item.chunk_id):
        if record.method_program:
            return record.method_program
    return ""


def invoke_group_summary(
    llm: ChatOpenAI,
    prompt_template: str,
    records: list[MethodPatternRecord],
    normalized_pattern: str,
    force_invalid_pattern: str = "",
) -> dict[str, Any]:
    """Call LLM for one grouped pattern and return normalized fields."""
    if force_invalid_pattern and normalized_pattern == force_invalid_pattern:
        raw_text = "this is intentionally malformed json"
    else:
        prompt = render_group_prompt(prompt_template, records)
        response = llm.invoke(prompt)
        raw_text = normalize_message_content(response.content)

    parsed = parse_json_with_recovery(raw_text)
    return normalize_sub_skill_shape(parsed)


def enrich_non_llm_fields(
    llm_result: dict[str, Any],
    normalized_pattern: str,
    records: list[MethodPatternRecord],
) -> dict[str, Any]:
    """Add deterministic fields derived without LLM."""
    source_chunk_ids = sorted({item.chunk_id for item in records})
    enriched = dict(llm_result)
    enriched["normalized_pattern"] = normalized_pattern
    enriched["source_chunk_ids"] = source_chunk_ids
    enriched["method_program_example"] = choose_method_program_example(records)
    return enriched


def generate_sub_skills(
    grouped_records: dict[str, list[MethodPatternRecord]],
    llm: ChatOpenAI,
    prompt_template: str,
    force_invalid_pattern: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate sub-skills per normalized pattern and collect errors."""
    sub_skills: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for normalized_pattern in sorted(grouped_records.keys()):
        records = grouped_records[normalized_pattern]
        try:
            llm_result = invoke_group_summary(
                llm=llm,
                prompt_template=prompt_template,
                records=records,
                normalized_pattern=normalized_pattern,
                force_invalid_pattern=force_invalid_pattern,
            )
            sub_skills.append(enrich_non_llm_fields(llm_result, normalized_pattern, records))
        except Exception as exc:  # pragma: no cover
            errors.append(
                {
                    "normalized_pattern": normalized_pattern,
                    "source_chunk_ids": sorted({item.chunk_id for item in records}),
                    "error": str(exc),
                }
            )

    return sub_skills, errors


def build_payload(
    input_path: Path,
    input_data: dict[str, Any],
    provider: str,
    model_name: str,
    api_base: str,
    grouped_count: int,
    sub_skills: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build final output payload with metadata and error report."""
    return {
        "sub_skills": sub_skills,
        "meta": {
            "source_file": input_data.get("source_file", input_path.name),
            "input_path": str(input_path),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "group_count": grouped_count,
            "generated_count": len(sub_skills),
            "error_count": len(errors),
            "model": {
                "provider": provider,
                "model_name": model_name,
                "api_base": api_base,
            },
        },
        "errors": errors,
    }


def save_output(output_dir: Path, output_file: str, payload: dict[str, Any]) -> Path:
    """Save JSON payload to output directory and return full output path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_file
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def print_summary(
    record_count: int,
    grouped_count: int,
    generated_count: int,
    error_count: int,
    output_path: Path,
) -> None:
    """Print a concise processing summary to stdout."""
    print(
        f"Processed records: {record_count}, groups: {grouped_count}, "
        f"generated: {generated_count}, errors: {error_count}"
    )
    print(f"Output file: {output_path}")


def main() -> None:
    """Program entry point for sub-skill aggregation."""
    args = parse_args()
    input_data = load_input_json(args.input)
    records = extract_method_pattern_records(input_data)
    grouped = group_by_normalized_pattern(records)
    prompt_template = load_prompt_template(args.prompt_file)
    llm = build_llm(model_name=args.model_name, api_base=args.api_base)
    sub_skills, errors = generate_sub_skills(
        grouped_records=grouped,
        llm=llm,
        prompt_template=prompt_template,
        force_invalid_pattern=args.force_invalid_pattern.strip(),
    )
    payload = build_payload(
        input_path=args.input,
        input_data=input_data,
        provider=DEFAULT_PROVIDER,
        model_name=args.model_name,
        api_base=args.api_base,
        grouped_count=len(grouped),
        sub_skills=sub_skills,
        errors=errors,
    )
    output_path = save_output(args.output_dir, args.output_file, payload)
    print_summary(
        record_count=len(records),
        grouped_count=len(grouped),
        generated_count=len(sub_skills),
        error_count=len(errors),
        output_path=output_path,
    )


if __name__ == "__main__":
    try:
        load_dotenv()
        main()
    except Exception as exc:  # pragma: no cover
        print(f"Execution failed: {exc}", file=sys.stderr)
        sys.exit(1)
