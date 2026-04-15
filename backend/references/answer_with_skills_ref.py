"""加载主/子技能 Markdown，结合用户问题调用 LLM 生成并保存答案 Markdown。"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

DEFAULT_MAIN_SKILL_DIR = Path(__file__).resolve().parent / "main_skill_md"
DEFAULT_SUB_SKILL_DIR = Path(__file__).resolve().parent / "sub_skill_md"
DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "prompts/answer_with_skills_prompt_v1_en.md"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "answer_outputs"
DEFAULT_MODEL_NAME = "deepseek-chat"
DEFAULT_API_BASE = "https://api.deepseek.com/v1"
SKILLS_PLACEHOLDER = "{{SKILLS_CONTEXT}}"
QUERY_PLACEHOLDER = "{{QUERY}}"


@dataclass
class SkillDoc:
    """Represent one loaded skill markdown document."""

    path: Path
    content: str


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for skill-driven answer generation."""
    parser = argparse.ArgumentParser(description="Answer one query using main/sub skill markdown context.")
    parser.add_argument("--query", type=str, required=True, help="The question to analyze and answer.")
    parser.add_argument("--main-skill-dir", type=Path, default=DEFAULT_MAIN_SKILL_DIR, help="Main skill md directory.")
    parser.add_argument("--sub-skill-dir", type=Path, default=DEFAULT_SUB_SKILL_DIR, help="Sub skill md directory.")
    parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE, help="Prompt template file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for markdown.")
    parser.add_argument("--output-file", type=str, default="", help="Optional output filename. If empty, auto-generate.")
    parser.add_argument("--model-name", type=str, default=DEFAULT_MODEL_NAME, help="LLM model name.")
    parser.add_argument("--api-base", type=str, default=DEFAULT_API_BASE, help="LLM API base URL.")
    return parser.parse_args()


def load_prompt_template(prompt_file: Path) -> str:
    """Load prompt template and validate required placeholders."""
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    template = prompt_file.read_text(encoding="utf-8")
    if SKILLS_PLACEHOLDER not in template:
        raise ValueError(f"Prompt file missing placeholder: {SKILLS_PLACEHOLDER}")
    if QUERY_PLACEHOLDER not in template:
        raise ValueError(f"Prompt file missing placeholder: {QUERY_PLACEHOLDER}")
    return template


def load_skill_docs(skill_dir: Path) -> list[SkillDoc]:
    """Load all markdown skill files from a directory in stable filename order."""
    if not skill_dir.exists():
        raise FileNotFoundError(f"Skill directory not found: {skill_dir}")
    files = sorted(skill_dir.glob("*.md"), key=lambda p: p.name.lower())
    docs: list[SkillDoc] = []
    for path in files:
        content = path.read_text(encoding="utf-8").strip()
        if content:
            docs.append(SkillDoc(path=path, content=content))
    return docs


def build_skills_context(main_docs: list[SkillDoc], sub_docs: list[SkillDoc]) -> str:
    """Build structured skills context block for prompt injection."""
    main_block = "\n\n".join(doc.content for doc in main_docs)
    sub_block = "\n\n".join(doc.content for doc in sub_docs)
    return (
        "=== Main Skill ===\n"
        f"{main_block}\n\n"
        "=== Sub Skills ===\n"
        f"{sub_block}"
    )


def render_prompt(template: str, skills_context: str, query: str) -> str:
    """Render final prompt by injecting skills context and query."""
    prompt = template.replace(SKILLS_PLACEHOLDER, skills_context)
    prompt = prompt.replace(QUERY_PLACEHOLDER, query.strip())
    return prompt


def build_llm(model_name: str, api_base: str) -> ChatOpenAI:
    """Build DeepSeek-compatible LLM client."""
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
    """Normalize LLM response content to plain text."""
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
    return str(content).strip()


def ensure_markdown_quality(markdown_text: str) -> None:
    """Validate minimum output quality constraints for generated markdown."""
    if not markdown_text.strip():
        raise ValueError("LLM returned empty output.")
    if "# Analysis" not in markdown_text:
        raise ValueError("Generated markdown missing required heading: # Analysis")


def slugify_query(query: str, max_len: int = 80) -> str:
    """Convert query into a safe filename slug using alnum and underscores only."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", query.strip())
    slug = slug.strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        return "answer"
    return slug[:max_len].rstrip("_") or "answer"


def allocate_output_path(output_dir: Path, output_file: str, query: str) -> Path:
    """Allocate output path using explicit filename or query-based slug with dedupe suffix."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_file:
        filename = output_file if output_file.lower().endswith(".md") else f"{output_file}.md"
        return output_dir / filename

    base = slugify_query(query)
    candidate = output_dir / f"{base}.md"
    if not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = output_dir / f"{base}_{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1


def save_markdown(path: Path, markdown_text: str) -> None:
    """Write markdown text to disk."""
    path.write_text(markdown_text, encoding="utf-8")


def print_summary(
    query: str,
    main_count: int,
    sub_count: int,
    output_path: Path,
) -> None:
    """Print concise processing summary."""
    print(f"Query: {query}")
    print(f"Loaded skills: main={main_count}, sub={sub_count}")
    print(f"Output file: {output_path}")


def main() -> None:
    """Program entry point for query-to-markdown skill-based answering."""
    args = parse_args()
    query = args.query.strip()
    if not query:
        raise ValueError("Argument --query cannot be empty.")

    main_docs = load_skill_docs(args.main_skill_dir)
    sub_docs = load_skill_docs(args.sub_skill_dir)
    if not main_docs:
        raise ValueError(f"No main skill markdown files found in: {args.main_skill_dir}")
    if not sub_docs:
        raise ValueError(f"No sub skill markdown files found in: {args.sub_skill_dir}")

    skills_context = build_skills_context(main_docs=main_docs, sub_docs=sub_docs)
    prompt_template = load_prompt_template(args.prompt_file)
    prompt = render_prompt(prompt_template, skills_context=skills_context, query=query)

    llm = build_llm(model_name=args.model_name, api_base=args.api_base)
    response = llm.invoke(prompt)
    markdown_text = normalize_message_content(response.content)
    ensure_markdown_quality(markdown_text)

    output_path = allocate_output_path(args.output_dir, args.output_file, query)
    save_markdown(output_path, markdown_text)
    print_summary(query=query, main_count=len(main_docs), sub_count=len(sub_docs), output_path=output_path)


if __name__ == "__main__":
    try:
        load_dotenv()
        main()
    except Exception as exc:  # pragma: no cover
        print(f"Execution failed: {exc}", file=sys.stderr)
        sys.exit(1)
