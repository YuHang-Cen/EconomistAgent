"""校验 sub_skill JSON 条目，并逐条转换输出为子技能 Markdown 文件。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path(__file__).resolve().parent / "sub_skill_json/sub_skill.json"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "sub_skill_md"
DEFAULT_TYPE = "sub_skill"


@dataclass
class SkillRecord:
    """Store one validated sub-skill item for markdown rendering."""

    name: str
    description: str
    method_program_summary: str
    method_program_example: str
    abstract_action_chain: list[str]
    source_chunk_ids: list[int]


@dataclass
class ProcessFailure:
    """Represent one skill rendering failure with index and reason."""

    index: int
    name: str
    reason: str


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for sub-skill markdown generation."""
    parser = argparse.ArgumentParser(description="Convert sub_skill.json into per-skill markdown files.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input sub_skill JSON file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output markdown directory.")
    parser.add_argument("--type", type=str, default=DEFAULT_TYPE, help="Frontmatter type field.")
    return parser.parse_args()


def load_input_json(input_path: Path) -> dict[str, Any]:
    """Load input JSON and ensure the root object is valid."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input JSON root must be an object.")
    sub_skills = data.get("sub_skills")
    if not isinstance(sub_skills, list):
        raise ValueError("Input JSON must contain a 'sub_skills' list.")
    return data


def validate_and_normalize_skill(raw_skill: Any, index: int) -> SkillRecord:
    """Validate one skill item and normalize it into a typed record."""
    if not isinstance(raw_skill, dict):
        raise ValueError(f"Item {index} is not an object.")

    name = raw_skill.get("name")
    description = raw_skill.get("description")
    method_program_summary = raw_skill.get("method_program_summary")
    method_program_example = raw_skill.get("method_program_example")
    abstract_action_chain = raw_skill.get("abstract_action_chain")
    source_chunk_ids = raw_skill.get("source_chunk_ids")

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Missing or invalid field: name")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Missing or invalid field: description")
    if not isinstance(method_program_summary, str):
        raise ValueError("Missing or invalid field: method_program_summary")
    if "method_program_example" not in raw_skill or not isinstance(method_program_example, str):
        raise ValueError("Missing or invalid field: method_program_example")
    if not isinstance(abstract_action_chain, list):
        raise ValueError("Missing or invalid field: abstract_action_chain")
    if not isinstance(source_chunk_ids, list):
        raise ValueError("Missing or invalid field: source_chunk_ids")

    normalized_actions: list[str] = []
    for item in abstract_action_chain:
        if isinstance(item, str) and item.strip():
            normalized_actions.append(item.strip())

    normalized_chunk_ids: list[int] = []
    for item in source_chunk_ids:
        if isinstance(item, int):
            normalized_chunk_ids.append(item)
        else:
            raise ValueError("Invalid field item in source_chunk_ids: must be int")

    return SkillRecord(
        name=name.strip(),
        description=description.strip(),
        method_program_summary=method_program_summary.strip(),
        method_program_example=method_program_example.strip(),
        abstract_action_chain=normalized_actions,
        source_chunk_ids=normalized_chunk_ids,
    )


def yaml_quote(value: str) -> str:
    """Quote a text value as a JSON-style string for safe YAML frontmatter embedding."""
    return json.dumps(value, ensure_ascii=False)


def render_skill_markdown(skill: SkillRecord, skill_type: str) -> str:
    """Render one skill markdown text with frontmatter and required sections."""
    chunk_ids_text = ", ".join(str(item) for item in skill.source_chunk_ids)

    lines = [
        "---",
        f"name: {yaml_quote(skill.name)}",
        f"type: {yaml_quote(skill_type)}",
        f"description: {yaml_quote(skill.description)}",
        f"source_chunk_ids: [{chunk_ids_text}]",
        "---",
        "",
        f"# {skill.name}",
        "",
        "## Description",
        "",
        skill.description,
        "",
        "## Method Program Summary",
        "",
        skill.method_program_summary,
        "",
        "## Method Program Example",
        "",
        skill.method_program_example if skill.method_program_example else "N/A",
        "",
        "## Abstract Action Chain",
        "",
    ]

    if skill.abstract_action_chain:
        for idx, action in enumerate(skill.abstract_action_chain, 1):
            lines.append(f"{idx}. {action}")
    else:
        lines.append("- N/A")

    lines.append("")
    return "\n".join(lines)


def validate_rendered_markdown(markdown_text: str, skill_name: str) -> list[str]:
    """Check whether rendered markdown contains all required key sections."""
    issues: list[str] = []
    lines = markdown_text.splitlines()

    if not lines or lines[0].strip() != "---":
        issues.append("Missing frontmatter opening --- at first line")
    else:
        closing_index = None
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                closing_index = idx
                break
        if closing_index is None:
            issues.append("Missing frontmatter closing ---")

    required_sections = [
        f"# {skill_name}",
        "## Description",
        "## Method Program Summary",
        "## Method Program Example",
        "## Abstract Action Chain",
    ]
    for section in required_sections:
        if section not in markdown_text:
            issues.append(f"Missing section: {section}")

    return issues


def sanitize_filename(name: str) -> str:
    """Sanitize a skill name into a Windows-safe markdown filename stem."""
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    sanitized = sanitized.replace(" ", "_")
    sanitized = sanitized.strip().rstrip(". ")
    return sanitized or "unnamed_skill"


def allocate_output_path(output_dir: Path, base_stem: str, used_names: set[str]) -> Path:
    """Allocate a non-conflicting output path by appending numeric suffixes when needed."""
    counter = 1
    while True:
        stem = base_stem if counter == 1 else f"{base_stem}_{counter}"
        filename = f"{stem}.md"
        candidate = output_dir / filename
        if filename not in used_names and not candidate.exists():
            used_names.add(filename)
            return candidate
        counter += 1


def write_markdown(output_path: Path, markdown_text: str) -> None:
    """Write rendered markdown content to file."""
    output_path.write_text(markdown_text, encoding="utf-8")


def process_sub_skills(
    sub_skills: list[Any],
    output_dir: Path,
    skill_type: str,
) -> tuple[list[Path], list[ProcessFailure]]:
    """Render, validate, and save markdown files for all sub-skills."""
    output_dir.mkdir(parents=True, exist_ok=True)
    created_files: list[Path] = []
    failures: list[ProcessFailure] = []
    used_names: set[str] = set()

    for index, raw_skill in enumerate(sub_skills, 1):
        display_name = ""
        if isinstance(raw_skill, dict):
            maybe_name = raw_skill.get("name")
            if isinstance(maybe_name, str):
                display_name = maybe_name
        try:
            skill = validate_and_normalize_skill(raw_skill, index)
            markdown_text = render_skill_markdown(skill, skill_type=skill_type)
            issues = validate_rendered_markdown(markdown_text, skill_name=skill.name)
            if issues:
                failures.append(ProcessFailure(index=index, name=skill.name, reason="; ".join(issues)))
                continue

            base_stem = sanitize_filename(skill.name)
            output_path = allocate_output_path(output_dir, base_stem, used_names)
            write_markdown(output_path, markdown_text)
            created_files.append(output_path)
        except Exception as exc:
            failures.append(ProcessFailure(index=index, name=display_name, reason=str(exc)))

    return created_files, failures


def print_summary(
    total: int,
    created_files: list[Path],
    failures: list[ProcessFailure],
    output_dir: Path,
) -> None:
    """Print concise processing summary with optional failure details."""
    print(
        f"Processed skills: {total}, succeeded: {len(created_files)}, failed: {len(failures)}"
    )
    print(f"Output directory: {output_dir}")
    for path in created_files:
        print(f"Generated: {path.name}")
    for failure in failures:
        name_label = failure.name if failure.name else "<unknown>"
        print(f"Failed item {failure.index} ({name_label}): {failure.reason}")


def main() -> None:
    """Program entry point for converting sub_skill.json into markdown files."""
    args = parse_args()
    data = load_input_json(args.input)
    sub_skills = data.get("sub_skills", [])
    created_files, failures = process_sub_skills(
        sub_skills=sub_skills,
        output_dir=args.output_dir,
        skill_type=args.type,
    )
    print_summary(
        total=len(sub_skills),
        created_files=created_files,
        failures=failures,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        print(f"Execution failed: {exc}", file=sys.stderr)
        sys.exit(1)
