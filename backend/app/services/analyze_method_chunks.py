"""执行方法分析阶段，按词数分块并产出 method_analysis 结构。"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI

from app.infra.settings import get_settings
from app.services.llm_utils import load_prompt, render_prompt

PROMPT_PLACEHOLDER = "{{CHUNK_TEXT}}"


@dataclass(frozen=True)
class ParagraphRecord:
    """保存单个段落的基础信息。"""

    index: str
    context: str
    chapter_id: str
    chapter_title: str


@dataclass(frozen=True)
class ChunkRecord:
    """保存分块后的文本与索引信息。"""

    chunk_id: int
    paragraph_indexes: list[str]
    text: str
    word_count: int
    section_id: str
    section_title: str


def _count_words(text: str) -> int:
    """统计词数用于分块边界控制。"""
    return len(re.findall(r"\b[\w'-]+\b", text))


def _normalize_segments(segments: list[dict[str, Any]]) -> list[ParagraphRecord]:
    """将服务侧 segment 记录映射为内部标准段落对象。"""
    paragraphs: list[ParagraphRecord] = []

    for item in segments:
        if not isinstance(item, dict):
            continue

        index = str(item.get("chunk_id", "")).strip()
        context = str(item.get("content", "")).strip()
        chapter_id = str(item.get("chapter_id", "")).strip()
        chapter_title = str(
            item.get("chapter_title")
            or item.get("section_title")
            or item.get("chapter_name")
            or ""
        ).strip()

        if not index or not context:
            continue

        paragraphs.append(
            ParagraphRecord(
                index=index,
                context=context,
                chapter_id=chapter_id,
                chapter_title=chapter_title,
            )
        )

    return paragraphs


def _create_chunks(paragraphs: list[ParagraphRecord], max_words: int) -> list[ChunkRecord]:
    """按最大词数把段落合并成多个 chunk。"""
    if max_words <= 0:
        raise ValueError("max_words must be greater than 0")

    chunks: list[ChunkRecord] = []
    current_paragraphs: list[ParagraphRecord] = []
    current_word_count = 0

    def flush_current() -> None:
        nonlocal current_paragraphs, current_word_count
        if not current_paragraphs:
            return

        first = current_paragraphs[0]
        chunks.append(
            ChunkRecord(
                chunk_id=len(chunks) + 1,
                paragraph_indexes=[p.index for p in current_paragraphs],
                text="\n\n".join(p.context for p in current_paragraphs),
                word_count=current_word_count,
                section_id=first.chapter_id,
                section_title=first.chapter_title,
            )
        )
        current_paragraphs = []
        current_word_count = 0

    for paragraph in paragraphs:
        paragraph_words = _count_words(paragraph.context)

        # 超长单段独立成块，不做截断。
        if paragraph_words > max_words:
            flush_current()
            chunks.append(
                ChunkRecord(
                    chunk_id=len(chunks) + 1,
                    paragraph_indexes=[paragraph.index],
                    text=paragraph.context,
                    word_count=paragraph_words,
                    section_id=paragraph.chapter_id,
                    section_title=paragraph.chapter_title,
                )
            )
            continue

        next_word_count = current_word_count + paragraph_words
        if current_paragraphs and next_word_count > max_words:
            flush_current()

        current_paragraphs.append(paragraph)
        current_word_count += paragraph_words

    flush_current()
    return chunks


def _build_llm(settings: Any) -> ChatOpenAI:
    """初始化 LangChain ChatOpenAI 客户端。"""
    provider = str(getattr(settings, "provider", os.getenv("PROVIDER", "deepseek"))).strip()
    model_name = str(getattr(settings, "model_name", os.getenv("MODEL_NAME", "deepseek-chat"))).strip()
    api_base = str(
        getattr(settings, "api_base", os.getenv("API_BASE", "https://api.deepseek.com"))
    ).strip()

    if provider.lower() != "deepseek":
        raise RuntimeError(f"unsupported provider for analyze stage: {provider}")

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("missing environment variable DEEPSEEK_API_KEY")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_base,
        temperature=0,
    )


def _normalize_message_content(content: Any) -> str:
    """把模型响应内容统一转换成字符串。"""
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
    """优先提取 Markdown 代码块中的 JSON。"""
    pattern = re.compile(r"```json\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()

    fallback_pattern = re.compile(r"```\s*(.*?)\s*```", re.DOTALL)
    fallback_match = fallback_pattern.search(text)
    if fallback_match:
        return fallback_match.group(1).strip()
    return None


def _extract_balanced_json_object(text: str) -> str | None:
    """从文本中提取首个括号平衡的 JSON 对象。"""
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
    """按“直接解析 -> 代码块 -> 括号平衡”顺序恢复 JSON。"""
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

    raise ValueError("model response cannot be parsed as a JSON object")


def _normalize_analysis_shape(data: dict[str, Any]) -> dict[str, Any]:
    """将模型输出归一为目标 JSON 结构。"""
    method_patterns = data.get("methodPatterns")
    if not isinstance(method_patterns, dict):
        method_patterns = {}

    raw_pattern = method_patterns.get("raw_pattern")
    normalized_pattern = method_patterns.get("normalized_pattern")
    actions = method_patterns.get("actions")
    method_program = method_patterns.get("method_program")

    if not isinstance(raw_pattern, str):
        raw_pattern = ""
    if not isinstance(normalized_pattern, str):
        normalized_pattern = ""
    if not isinstance(actions, list):
        actions = []
    actions = [item for item in actions if isinstance(item, str)]
    if not isinstance(method_program, str):
        method_program = ""

    method_signals = data.get("methodSignals")
    if not isinstance(method_signals, dict):
        method_signals = {}

    perspective = method_signals.get("perspective")
    nature = method_signals.get("nature")
    time_orientation = method_signals.get("time_orientation")
    system_scope = method_signals.get("system_scope")
    equilibrium_view = method_signals.get("equilibrium_view")
    logic = method_signals.get("logic")

    if not isinstance(perspective, str):
        perspective = ""
    if not isinstance(nature, str):
        nature = ""
    if not isinstance(time_orientation, str):
        time_orientation = ""
    if not isinstance(system_scope, str):
        system_scope = ""
    if not isinstance(equilibrium_view, str):
        equilibrium_view = ""
    if not isinstance(logic, list):
        logic = []
    logic = [item for item in logic if isinstance(item, str)]

    return {
        "methodPatterns": {
            "raw_pattern": raw_pattern,
            "normalized_pattern": normalized_pattern,
            "actions": actions,
            "method_program": method_program,
        },
        "methodSignals": {
            "perspective": perspective,
            "nature": nature,
            "time_orientation": time_orientation,
            "system_scope": system_scope,
            "equilibrium_view": equilibrium_view,
            "logic": logic,
        },
    }


def _analyze_chunk(
    chunk: ChunkRecord,
    llm: ChatOpenAI,
    prompt_template: str,
) -> dict[str, Any]:
    """对单个 chunk 调用模型并返回归一化分析结果。"""
    prompt = render_prompt(prompt_template, {PROMPT_PLACEHOLDER: chunk.text})
    response = llm.invoke(prompt)
    raw_text = _normalize_message_content(response.content)
    parsed = _parse_json_with_recovery(raw_text)
    return _normalize_analysis_shape(parsed)


def run_analyze_method_chunks(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """执行 analyze 阶段并返回 method_analysis JSON。"""
    if not segments:
        return {"chunks": [], "errors": []}

    settings = get_settings()
    paragraphs = _normalize_segments(segments)
    if not paragraphs:
        return {"chunks": [], "errors": []}

    max_words = max(100, int(getattr(settings, "method_chunk_max_words", 800)))
    chunk_inputs = _create_chunks(paragraphs=paragraphs, max_words=max_words)

    prompt_template = load_prompt(
        "method_analysis_prompt.md",
        required_placeholders=[PROMPT_PLACEHOLDER],
    )
    llm = _build_llm(settings)

    result_chunks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for chunk in chunk_inputs:
        try:
            analysis = _analyze_chunk(
                chunk=chunk,
                llm=llm,
                prompt_template=prompt_template,
            )
            result_chunks.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "section_id": chunk.section_id,
                    "section_title": chunk.section_title,
                    "paragraph_indexes": chunk.paragraph_indexes,
                    "word_count": chunk.word_count,
                    "analysis": analysis,
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "section_id": chunk.section_id,
                    "section_title": chunk.section_title,
                    "paragraph_indexes": chunk.paragraph_indexes,
                    "word_count": chunk.word_count,
                    "error": str(exc),
                }
            )

    return {"chunks": result_chunks, "errors": errors}