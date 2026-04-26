"""Generate a Chinese translated question-by-author comparison Markdown."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

AUTHOR_ORDER = [
    "F. A. Hayek",
    "J. M. Keynes",
    "M. Friedman",
]


@dataclass(frozen=True)
class AnswerRecord:
    author_name: str
    query_display: str
    query_key: str
    markdown: str


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


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
                    query_display=query_display,
                    query_key=query_key,
                    markdown=markdown,
                )
            )
    return records


class Translator:
    def __init__(self, api_key: str, api_base: str, model_name: str) -> None:
        if not api_key:
            raise RuntimeError("missing DEEPSEEK_API_KEY")
        self.url = f"{api_base.rstrip('/')}/v1/chat/completions"
        self.api_key = api_key
        self.model_name = model_name

    def _chat(self, messages: list[dict[str, str]], max_tokens: int = 4096) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        retry_delays = [1.0, 2.0, 4.0]
        last_error: Exception | None = None
        for attempt in range(len(retry_delays) + 1):
            try:
                response = requests.post(
                    self.url,
                    headers=headers,
                    json=payload,
                    timeout=180,
                )
                if response.status_code >= 400:
                    raise RuntimeError(f"translate api error: {response.status_code} {response.text[:300]}")
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise RuntimeError("empty translation response")
                return content.strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= len(retry_delays):
                    break
                time.sleep(retry_delays[attempt])
        raise RuntimeError(f"translation failed after retries: {last_error}") from last_error

    def translate_question(self, question_en: str) -> str:
        messages = [
            {
                "role": "system",
                "content": "You are a precise translator. Translate English to Simplified Chinese.",
            },
            {
                "role": "user",
                "content": (
                    "请把下面这个英文问题翻译成简体中文。\n"
                    "要求：仅输出中文译文，不要解释，不要加引号。\n\n"
                    f"{question_en}"
                ),
            },
        ]
        return self._chat(messages, max_tokens=512)

    def translate_markdown(self, markdown_en: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a faithful translator for economics and labor-market analysis.\n"
                    "Preserve structure and meaning exactly."
                ),
            },
            {
                "role": "user",
                "content": (
                    "请将以下英文 Markdown 全文翻译为简体中文。\n"
                    "要求：\n"
                    "1) 保留原有 Markdown 结构、段落、标题层级。\n"
                    "2) 不增删信息，不做总结，不改写立场。\n"
                    "3) 术语可直译；必要时在中文后保留英文括注。\n"
                    "4) 仅输出翻译后的 Markdown 内容。\n\n"
                    f"{markdown_en}"
                ),
            },
        ]
        return self._chat(messages, max_tokens=4096)


def _render_markdown(records: list[AnswerRecord], translator: Translator) -> str:
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

    question_zh_by_key: dict[str, str] = {}
    for key in question_order:
        question_zh_by_key[key] = translator.translate_question(display_title_by_key[key])

    translated_answer_by_key_author: dict[str, dict[str, str]] = {}
    for key in question_order:
        translated_answer_by_key_author[key] = {}
        for author_name in AUTHOR_ORDER:
            source = by_key.get(key, {}).get(author_name, "")
            if source:
                translated_answer_by_key_author[key][author_name] = translator.translate_markdown(source)

    lines: list[str] = []
    lines.append("# Demo 回答对比（中文翻译版）")
    lines.append("")
    lines.append("本文档基于 `backend/demo_storage` 自动生成。")
    lines.append("组织方式：先按问题分组，再按固定作者顺序展示完整中文译文。")
    lines.append("")
    lines.append("## 问题总览")
    lines.append("")
    lines.append("| 序号 | 问题（中文） | 原题（英文） | F. A. Hayek | J. M. Keynes | M. Friedman |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for index, key in enumerate(question_order, start=1):
        marks = []
        for author_name in AUTHOR_ORDER:
            marks.append("✅" if author_name in translated_answer_by_key_author[key] else "❌")
        lines.append(
            f"| Q{index} | {question_zh_by_key[key]} | {display_title_by_key[key]} | {marks[0]} | {marks[1]} | {marks[2]} |"
        )
    lines.append("")

    for index, key in enumerate(question_order, start=1):
        lines.append(f"## Q{index}. {question_zh_by_key[key]}")
        lines.append("")
        lines.append(f"> 原题：{display_title_by_key[key]}")
        lines.append("")
        for author_name in AUTHOR_ORDER:
            lines.append(f"### {author_name}")
            lines.append("")
            markdown_zh = translated_answer_by_key_author[key].get(author_name)
            if markdown_zh:
                lines.append(markdown_zh)
            else:
                lines.append("（该作者此题无回答）")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "backend"
    demo_root = backend_root / "demo_storage"
    authors_root = demo_root / "authors"
    output_path = demo_root / "answers_by_question_author_zh.md"

    _load_env_file(backend_root / ".env")
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    api_base = os.getenv("API_BASE", "https://api.deepseek.com").strip()
    model_name = os.getenv("MODEL_NAME", "deepseek-chat").strip()

    translator = Translator(api_key=api_key, api_base=api_base, model_name=model_name)
    records = _load_records(authors_root)
    markdown = _render_markdown(records, translator)
    output_path.write_text(markdown, encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "records": len(records),
                "questions": len({_query_group_key(r.query_display) for r in records}),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
