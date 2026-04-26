"""Generate a question-by-author Markdown comparison from demo_storage answers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

AUTHOR_ORDER = [
    "F. A. Hayek",
    "J. M. Keynes",
    "M. Friedman",
]


@dataclass(frozen=True)
class AnswerRecord:
    author_name: str
    query_raw: str
    query_display: str
    query_key: str
    markdown: str


def _clean_query_for_display(raw: str) -> str:
    cleaned = raw.replace("_", " ").replace("？", "?")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _query_group_key(display_query: str) -> str:
    key = display_query.lower().strip()
    key = re.sub(r"\?+$", "", key).strip()
    return key


def _load_author_name(author_dir: Path) -> str:
    meta = json.loads((author_dir / "author_meta.json").read_text(encoding="utf-8"))
    name = str(meta.get("author_name", "")).strip()
    if not name:
        raise ValueError(f"missing author_name in {author_dir / 'author_meta.json'}")
    return name


def _load_records(authors_root: Path) -> list[AnswerRecord]:
    records: list[AnswerRecord] = []
    for author_dir in sorted([p for p in authors_root.iterdir() if p.is_dir()]):
        author_name = _load_author_name(author_dir)
        answer_files = sorted((author_dir / "answers").glob("*/answer.json"))
        for answer_file in answer_files:
            data = json.loads(answer_file.read_text(encoding="utf-8"))
            query_raw = str(data.get("query", "")).strip()
            answer = data.get("answer")
            markdown = ""
            if isinstance(answer, dict):
                markdown = str(answer.get("markdown", "")).strip()
            if not query_raw:
                raise ValueError(f"missing query in {answer_file}")
            if not markdown:
                raise ValueError(f"missing answer.markdown in {answer_file}")
            query_display = _clean_query_for_display(query_raw)
            query_key = _query_group_key(query_display)
            records.append(
                AnswerRecord(
                    author_name=author_name,
                    query_raw=query_raw,
                    query_display=query_display,
                    query_key=query_key,
                    markdown=markdown,
                )
            )
    return records


def _author_sort_key(author_name: str) -> tuple[int, str]:
    if author_name in AUTHOR_ORDER:
        return (AUTHOR_ORDER.index(author_name), author_name)
    return (len(AUTHOR_ORDER), author_name)


def _render_overview_table(
    question_order: list[str], display_title_by_key: dict[str, str], by_key: dict[str, dict[str, str]]
) -> str:
    header = [
        "## 问题总览",
        "",
        "| 序号 | 问题 | F. A. Hayek | J. M. Keynes | M. Friedman |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows: list[str] = []
    for index, key in enumerate(question_order, start=1):
        title = display_title_by_key[key]
        answers = by_key.get(key, {})
        marks = []
        for author_name in AUTHOR_ORDER:
            marks.append("✅" if author_name in answers else "❌")
        rows.append(
            f"| Q{index} | {title} | {marks[0]} | {marks[1]} | {marks[2]} |"
        )
    return "\n".join(header + rows)


def _render_markdown(records: list[AnswerRecord]) -> str:
    by_key: dict[str, dict[str, str]] = {}
    display_title_by_key: dict[str, str] = {}

    for record in records:
        by_key.setdefault(record.query_key, {})
        by_key[record.query_key][record.author_name] = record.markdown
        existing = display_title_by_key.get(record.query_key)
        if existing is None or ("?" not in existing and "?" in record.query_display):
            display_title_by_key[record.query_key] = record.query_display

    question_order = sorted(
        by_key.keys(),
        key=lambda key: display_title_by_key.get(key, key).lower(),
    )

    lines: list[str] = []
    lines.append("# Demo 回答对比（按问题 → 作者）")
    lines.append("")
    lines.append("本文档基于 `backend/demo_storage` 自动生成。")
    lines.append("组织方式：先按问题分组，再按固定作者顺序展示完整回答原文。")
    lines.append("")
    lines.append(_render_overview_table(question_order, display_title_by_key, by_key))
    lines.append("")

    for index, key in enumerate(question_order, start=1):
        lines.append(f"## Q{index}. {display_title_by_key[key]}")
        lines.append("")
        for author_name in AUTHOR_ORDER:
            lines.append(f"### {author_name}")
            lines.append("")
            markdown = by_key[key].get(author_name)
            if markdown:
                lines.append(markdown)
            else:
                lines.append("（该作者此题无回答）")
            lines.append("")

        extra_authors = sorted(
            [name for name in by_key[key].keys() if name not in AUTHOR_ORDER],
            key=_author_sort_key,
        )
        for author_name in extra_authors:
            lines.append(f"### {author_name}")
            lines.append("")
            lines.append(by_key[key][author_name])
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    demo_root = repo_root / "backend" / "demo_storage"
    authors_root = demo_root / "authors"
    output_path = demo_root / "answers_by_question_author.md"

    if not authors_root.exists():
        raise FileNotFoundError(f"authors directory not found: {authors_root}")

    records = _load_records(authors_root)
    markdown = _render_markdown(records)
    output_path.write_text(markdown, encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "records": len(records),
                "questions": len(
                    {
                        _query_group_key(_clean_query_for_display(record.query_raw))
                        for record in records
                    }
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
