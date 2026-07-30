"""Generate answer_json using selected section-level skill context."""

from __future__ import annotations

import re
from typing import Any, Literal

from app.domain.language import normalize_author_language
from app.services.llm_utils import (
    build_optional_llm,
    load_prompt_by_language,
    normalize_message_content,
    parse_json_with_recovery,
    render_prompt,
)

AUTHOR_PLACEHOLDER = "{{AUTHOR}}"
SKILLS_PLACEHOLDER = "{{SKILLS_CONTEXT}}"
QUERY_PLACEHOLDER = "{{QUERY}}"
MAIN_SKILLS_MD_KEY = "main_skills_md_json"
SUB_SKILLS_MD_KEY = "sub_skills_md_json"
DEFAULT_QUESTION_PROMPT = "answer_with_skills_prompt_question.md"
DEFAULT_PAPER_PROMPT = "answer_with_skills_prompt_paper.md"

QueryKind = Literal["single_question", "question_list", "paper_text"]
AnswerSource = Literal["llm", "llm_repaired", "fallback"]

_NUMBERED_ITEM_RE = re.compile(r"(?m)^\s*\d+[\.\)]\s+")
_PAPER_MARKER_RE = re.compile(
    r"\b(Abstract|Introduction|Keywords?|JEL|Section|Figure|Table|Related Literature|"
    r"Research Background|Empirical Strategy|Fact I|Fact II)\b",
    re.IGNORECASE,
)
_SECTION_HEADING_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\s+)?"
    r"(Abstract|Introduction|Related Literature|Research Background|Empirical Strategy|"
    r"Empirical Investigation|Conclusion)\b",
    re.IGNORECASE,
)
_LATE_SECTION_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\s+)?"
    r"(Related Literature|Research Background|Empirical Strategy|Empirical Investigation|"
    r"Data|Results|Conclusion)\b",
    re.IGNORECASE,
)


def _normalize_selected_skill_index(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 1:
        return None
    return value


def _normalize_selected_skill_indices(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    normalized: list[int] = []
    seen: set[int] = set()
    for item in value:
        skill_index = _normalize_selected_skill_index(item)
        if skill_index is None or skill_index in seen:
            continue
        seen.add(skill_index)
        normalized.append(skill_index)
    return normalized


def _normalize_selected_section_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text else None


def _normalize_selected_section_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        section_id = _normalize_selected_section_id(item)
        if section_id is None or section_id in seen:
            continue
        seen.add(section_id)
        normalized.append(section_id)
    return normalized


def _normalize_selection_mode(value: Any) -> str:
    if value == "llm":
        return "llm"
    return "fallback_rule"


def _normalize_selection_warning(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text else None


def _read_sub_skill_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    skill_name = item.get("skill_name")
    if isinstance(skill_name, str) and skill_name.strip():
        return skill_name.strip()
    return ""


def _read_main_skill_name(item: dict[str, Any]) -> str:
    name = item.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    pattern_summary = item.get("pattern_summary")
    if isinstance(pattern_summary, dict):
        pattern_name = pattern_summary.get("name")
        if isinstance(pattern_name, str) and pattern_name.strip():
            return pattern_name.strip()
    return ""


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _find_main_skill_name(
    snapshot_outputs: dict[str, Any],
    section_id: str,
) -> str | None:
    main_md_items = snapshot_outputs.get(MAIN_SKILLS_MD_KEY)
    if isinstance(main_md_items, list):
        for item in main_md_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != section_id:
                continue
            name = _read_main_skill_name(item)
            if name:
                return name

    main_json_items = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    if isinstance(main_json_items, list):
        for item in main_json_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != section_id:
                continue
            name = _read_main_skill_name(item)
            if name:
                return name

    return None


def _find_sub_skill_names(
    snapshot_outputs: dict[str, Any],
    section_id: str,
) -> list[str]:
    sub_names: list[str] = []
    sub_md_items = snapshot_outputs.get(SUB_SKILLS_MD_KEY)
    if isinstance(sub_md_items, list):
        for item in sub_md_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != section_id:
                continue
            name = _read_sub_skill_name(item)
            if name:
                sub_names.append(name)

    if sub_names:
        return _dedupe_preserve_order(sub_names)

    sub_json_items = snapshot_outputs.get("sub_skill_json", {}).get("sub_skills", [])
    if isinstance(sub_json_items, list):
        for item in sub_json_items:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != section_id:
                continue
            name = _read_sub_skill_name(item)
            if name:
                sub_names.append(name)

    return _dedupe_preserve_order(sub_names)


def _resolve_selected_skill_names(
    snapshot_outputs: dict[str, Any],
    selected_section_ids: list[str],
) -> tuple[list[str], list[str]]:
    if not selected_section_ids:
        return [], []

    main_names: list[str] = []
    sub_names: list[str] = []
    for section_id in selected_section_ids:
        main_name = _find_main_skill_name(snapshot_outputs, section_id)
        if main_name:
            main_names.append(main_name)
        sub_names.extend(_find_sub_skill_names(snapshot_outputs, section_id))

    return main_names, _dedupe_preserve_order(sub_names)


def _validate_answer_schema(value: Any) -> dict[str, str] | None:
    """Validate answer payload against the strict JSON schema."""
    if not isinstance(value, dict):
        return None

    expected_keys = {"title", "topic", "summary", "markdown"}
    actual_keys = set(value.keys())
    if actual_keys != expected_keys:
        return None

    normalized: dict[str, str] = {}
    for key in ("title", "topic", "summary", "markdown"):
        field_value = value.get(key)
        if not isinstance(field_value, str):
            return None
        text = field_value.strip()
        if not text:
            return None
        normalized[key] = text

    return normalized


def _build_context_from_markdown(
    snapshot_outputs: dict[str, Any],
    selected_section_ids: list[str],
) -> str:
    """Build context from markdown JSON artifacts when available."""
    if not selected_section_ids:
        return ""

    main_skills_md = snapshot_outputs.get(MAIN_SKILLS_MD_KEY)
    sub_skills_md = snapshot_outputs.get(SUB_SKILLS_MD_KEY)
    if not isinstance(main_skills_md, list) or not isinstance(sub_skills_md, list):
        return ""

    sections: list[str] = []
    for selected_section_id in selected_section_ids:
        selected_main_item: dict[str, Any] | None = None
        for item in main_skills_md:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != selected_section_id:
                continue
            markdown = item.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                selected_main_item = item
                break

        if selected_main_item is None:
            continue

        selected_sub_items: list[dict[str, Any]] = []
        for item in sub_skills_md:
            if not isinstance(item, dict):
                continue
            if str(item.get("section_id", "")).strip() != selected_section_id:
                continue
            markdown = item.get("markdown")
            if not isinstance(markdown, str) or not markdown.strip():
                continue
            selected_sub_items.append(item)

        lines: list[str] = ["=== Main Skill Markdown ==="]
        main_file_name = selected_main_item.get("file_name")
        if isinstance(main_file_name, str) and main_file_name:
            lines.append(f"file: {main_file_name}")
        lines.append(selected_main_item["markdown"])

        if selected_sub_items:
            lines.append("\n=== Sub Skills Markdown ===")
            for item in selected_sub_items:
                sub_name = _read_sub_skill_name(item)
                file_name = item.get("file_name", "")
                lines.append(f"\n--- {sub_name} ({file_name}) ---")
                lines.append(item["markdown"])

        sections.append("\n".join(lines).strip())

    return "\n\n".join(sections).strip()


def _build_context_from_json(
    snapshot_outputs: dict[str, Any],
    selected_section_ids: list[str],
) -> str:
    """Build fallback context from main/sub skill JSON artifacts."""
    if not selected_section_ids:
        return ""

    main_skills = snapshot_outputs.get("main_skill_json", {}).get("main_skills", [])
    sub_skills = snapshot_outputs.get("sub_skill_json", {}).get("sub_skills", [])
    sections: list[str] = []

    for selected_section_id in selected_section_ids:
        selected_main: dict[str, Any] | None = None
        if isinstance(main_skills, list):
            for skill in main_skills:
                if not isinstance(skill, dict):
                    continue
                if str(skill.get("section_id", "")).strip() == selected_section_id:
                    selected_main = skill
                    break

        selected_subs: list[dict[str, Any]] = []
        if isinstance(sub_skills, list):
            for item in sub_skills:
                if not isinstance(item, dict):
                    continue
                if str(item.get("section_id", "")).strip() != selected_section_id:
                    continue
                selected_subs.append(item)

        lines: list[str] = []
        if selected_main:
            pattern = selected_main.get("pattern_summary", {})
            if not isinstance(pattern, dict):
                pattern = {}
            lines.append("=== Main Skill ===")
            lines.append(f"name: {pattern.get('name', '')}")
            lines.append(f"description: {pattern.get('description', '')}")
            lines.append(f"applicability: {pattern.get('applicability', '')}")
            core_steps = pattern.get("core_steps", [])
            if isinstance(core_steps, list):
                lines.append("core_steps:")
                for step in core_steps:
                    lines.append(f"- {step}")

        if selected_subs:
            lines.append("\n=== Sub Skills ===")
            for item in selected_subs:
                lines.append(f"- {item.get('name', '')}: {item.get('description', '')}")

        if lines:
            sections.append("\n".join(lines).strip())

    return "\n\n".join(sections).strip()


def _build_context(
    snapshot_outputs: dict[str, Any],
    selected_section_ids: list[str],
) -> str:
    """Prefer markdown artifacts, fallback to JSON summary context."""
    markdown_context = _build_context_from_markdown(
        snapshot_outputs=snapshot_outputs,
        selected_section_ids=selected_section_ids,
    )
    if markdown_context:
        return markdown_context

    return _build_context_from_json(
        snapshot_outputs=snapshot_outputs,
        selected_section_ids=selected_section_ids,
    )


def _classify_query_kind(query: str) -> QueryKind:
    normalized = query.strip()
    lower = normalized.lower()
    paper_markers = len(_PAPER_MARKER_RE.findall(normalized))
    question_marks = normalized.count("?") + normalized.count("？")
    numbered_items = len(_NUMBERED_ITEM_RE.findall(normalized))
    line_count = len([line for line in normalized.splitlines() if line.strip()])

    if numbered_items >= 2 or question_marks >= 2:
        return "question_list"
    if "abstract" in lower and paper_markers >= 1:
        return "paper_text"
    if (
        len(normalized) >= 1800
        or (paper_markers >= 2 and len(normalized) >= 260)
        or ("abstract" in lower and len(normalized) >= 120)
        or (line_count >= 12 and paper_markers >= 1)
    ):
        return "paper_text"
    return "single_question"


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _collapse_linebreaks(text: str) -> str:
    collapsed = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    collapsed = re.sub(r"[ \t]{2,}", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def _clean_paper_paragraph(paragraph: str) -> str:
    text = paragraph.strip()
    text = re.sub(r"\b\S+@\S+\b", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -")


def _is_skippable_paper_paragraph(paragraph: str) -> bool:
    if not paragraph:
        return True
    lower = paragraph.lower()
    if re.fullmatch(r"\d+", paragraph):
        return True
    if lower.startswith("keywords:") or lower.startswith("jel"):
        return True
    if paragraph.startswith("∗") or "email:" in lower:
        return True
    if lower.startswith("figure ") or lower.startswith("table ") or lower.startswith("note:"):
        return True
    if paragraph.startswith("(") and paragraph.endswith(")"):
        return True
    return False


def _normalize_paper_query(query: str) -> str:
    text = _normalize_whitespace(query)
    paragraphs = [_clean_paper_paragraph(part) for part in re.split(r"\n\s*\n", text)]
    paragraphs = [part for part in paragraphs if not _is_skippable_paper_paragraph(part)]

    selected: list[str] = []
    abstract_index: int | None = None
    for index, paragraph in enumerate(paragraphs):
        if paragraph.lower().startswith("abstract"):
            abstract_index = index
            break
    if abstract_index is None:
        abstract_index = 0

    for paragraph in paragraphs[abstract_index:]:
        if _LATE_SECTION_RE.match(paragraph) and selected:
            break
        if _SECTION_HEADING_RE.match(paragraph):
            if paragraph.lower().startswith("abstract"):
                paragraph = re.sub(r"^abstract[:\s-]*", "", paragraph, flags=re.IGNORECASE).strip()
                if paragraph:
                    selected.append(paragraph)
            continue
        selected.append(paragraph)
        if len(selected) >= 6:
            break

    if not selected:
        selected = paragraphs[:4]

    normalized = "\n\n".join(selected).strip()
    if len(normalized) > 3500:
        normalized = normalized[:3500].rsplit(" ", 1)[0].strip() + " ..."
    return normalized


def _build_source_preview(text: str, *, limit: int = 260) -> str:
    preview = re.sub(r"\s+", " ", text).strip()
    if len(preview) <= limit:
        return preview
    return preview[:limit].rsplit(" ", 1)[0].strip() + " ..."


def _normalize_query_for_answering(query: str, query_kind: QueryKind) -> tuple[str, str]:
    if query_kind == "paper_text":
        normalized = _normalize_paper_query(query)
    else:
        normalized = _collapse_linebreaks(_normalize_whitespace(query))
    return normalized, _build_source_preview(normalized)


def _build_prompt_filename(query_kind: QueryKind) -> str:
    if query_kind == "paper_text":
        return DEFAULT_PAPER_PROMPT
    return DEFAULT_QUESTION_PROMPT


def _build_repair_prompt(raw_output: str, *, language: str) -> str:
    normalized_language = normalize_author_language(language)
    if normalized_language == "chinese":
        return (
            "请把下面的模型输出改写成一个合法 JSON 对象。\n"
            "必须且只能包含四个字符串字段：title、topic、summary、markdown。\n"
            "不要输出解释、不要输出代码块、不要增加额外字段。\n"
            "如果原文包含列表或段落，可保留到 markdown 字段里。\n\n"
            "原始输出：\n"
            f"{raw_output}"
        )
    return (
        "Rewrite the following model output as a valid JSON object.\n"
        "The object must contain exactly four string fields: title, topic, summary, markdown.\n"
        "Do not include explanations, markdown fences, or extra keys.\n"
        "Preserve the answer content inside the markdown field when possible.\n\n"
        "Raw output:\n"
        f"{raw_output}"
    )


def _try_validate_raw_output(raw_output: str) -> dict[str, str] | None:
    if not raw_output.strip():
        return None
    try:
        candidate = parse_json_with_recovery(raw_output)
    except Exception:
        return None
    return _validate_answer_schema(candidate)


def _repair_answer_payload(raw_output: str, *, language: str) -> dict[str, str] | None:
    llm = build_optional_llm()
    if llm is None:
        return None
    repair_prompt = _build_repair_prompt(raw_output, language=language)
    try:
        response = llm.invoke(repair_prompt)
    except Exception:
        return None
    repaired = normalize_message_content(response.content).strip()
    return _try_validate_raw_output(repaired)


def _invoke_llm_answer(
    prompt: str,
    *,
    language: str,
) -> tuple[dict[str, str] | None, AnswerSource | None, str | None, str | None]:
    llm = build_optional_llm()
    if llm is None:
        return None, None, "LLM unavailable; returning deterministic fallback.", "llm_unavailable"

    try:
        response = llm.invoke(prompt)
    except Exception as exc:
        return (
            None,
            None,
            f"LLM invocation failed ({exc.__class__.__name__}); returning fallback.",
            "llm_invoke_failed",
        )

    normalized = normalize_message_content(response.content).strip()
    validated = _try_validate_raw_output(normalized)
    if validated is not None:
        return validated, "llm", None, None

    repaired = _repair_answer_payload(normalized, language=language)
    if repaired is not None:
        return (
            repaired,
            "llm_repaired",
            "Answer JSON was repaired after validation failure.",
            None,
        )

    return (
        None,
        None,
        "LLM returned invalid JSON; using structured fallback.",
        "invalid_answer_json",
    )


def _fallback_answer(
    query: str,
    context: str,
    *,
    language: str,
    query_kind: QueryKind,
    source_preview: str,
) -> dict[str, str]:
    """Return deterministic JSON answer when LLM is unavailable or invalid."""
    summary = context.splitlines()[:6]
    summary_text = " ".join(summary).strip()
    if len(summary_text) > 180:
        summary_text = summary_text[:180].rsplit(" ", 1)[0].strip() + " ..."
    normalized_language = normalize_author_language(language)

    if normalized_language == "chinese":
        if query_kind == "paper_text":
            return {
                "title": "结构化审稿要点暂不可用",
                "topic": "论文审稿",
                "summary": (
                    "本次生成已降级，未能成功产出结构化审稿要点。"
                    "下面仅保留简短材料预览与状态说明。"
                ),
                "markdown": (
                    "# 结构化审稿要点暂不可用\n\n"
                    "本次回答进入降级模式，因此没有返回完整的 referee points。\n\n"
                    f"材料预览：{source_preview}\n\n"
                    f"技能上下文摘要：{summary_text or '已加载技能上下文。'}"
                ),
            }
        return {
            "title": "结构化回应暂不可用",
            "topic": "经济问题分析",
            "summary": "本次生成已降级，未能成功产出标准化回答。下面仅保留简短问题预览与状态说明。",
            "markdown": (
                "# 结构化回应暂不可用\n\n"
                "本次回答进入降级模式，因此没有返回完整的 rebuttal note。\n\n"
                f"问题预览：{source_preview}\n\n"
                f"技能上下文摘要：{summary_text or '已加载技能上下文。'}"
            ),
        }

    if query_kind == "paper_text":
        return {
            "title": "Structured referee points unavailable",
            "topic": "paper review",
            "summary": (
                "Generation degraded before structured referee points could be produced. "
                "This fallback keeps only a short source preview and a brief context note."
            ),
            "markdown": (
                "# Structured Review Unavailable\n\n"
                "This answer fell back before a full set of numbered referee points "
                "could be generated.\n\n"
                f"Source preview: {source_preview}\n\n"
                f"Skill context note: {summary_text or 'Selected skill context was loaded.'}"
            ),
        }

    return {
        "title": "Structured rebuttal unavailable",
        "topic": "economics response",
        "summary": (
            "Generation degraded before a full rebuttal response could be produced. "
            "This fallback keeps only a short question preview and a brief context note."
        ),
        "markdown": (
            "# Structured Rebuttal Unavailable\n\n"
            "This answer fell back before a full rebuttal note could be generated.\n\n"
            f"Question preview: {source_preview}\n\n"
            f"Skill context note: {summary_text or 'Selected skill context was loaded.'}"
        ),
    }


def run_answer_with_skills(
    query: str,
    selected: dict[str, Any],
    snapshot_outputs: dict[str, Any],
    *,
    language: str = "english",
    author_name: str = "",
) -> dict[str, Any]:
    """Generate answer_json using selected skills and snapshot outputs."""
    normalized_language = normalize_author_language(language)

    selected_skill_indices = _normalize_selected_skill_indices(
        selected.get("selected_skill_indices")
    )
    if not selected_skill_indices:
        selected_skill_index = _normalize_selected_skill_index(selected.get("selected_skill_index"))
        if selected_skill_index is not None:
            selected_skill_indices = [selected_skill_index]

    selected_section_ids = _normalize_selected_section_ids(selected.get("selected_section_ids"))
    if not selected_section_ids:
        selected_section_id = _normalize_selected_section_id(selected.get("selected_section_id"))
        if selected_section_id is not None:
            selected_section_ids = [selected_section_id]

    selection_mode = _normalize_selection_mode(selected.get("selection_mode"))
    selection_warning = _normalize_selection_warning(selected.get("selection_warning"))
    selected_main_skill_names, selected_sub_skill_names = _resolve_selected_skill_names(
        snapshot_outputs=snapshot_outputs,
        selected_section_ids=selected_section_ids,
    )

    context = _build_context(
        snapshot_outputs=snapshot_outputs,
        selected_section_ids=selected_section_ids,
    )
    query_kind = _classify_query_kind(query)
    normalized_query, source_preview = _normalize_query_for_answering(query, query_kind)

    answer_warning: str | None = None
    answer_fallback_reason: str | None = None
    answer_source: AnswerSource = "fallback"
    try:
        answer_payload = _fallback_answer(
            query=normalized_query,
            context=context,
            language=normalized_language,
            query_kind=query_kind,
            source_preview=source_preview,
        )
    except TypeError:
        answer_payload = _fallback_answer(
            query=normalized_query,
            context=context,
            language=normalized_language,
        )

    template = load_prompt_by_language(
        _build_prompt_filename(query_kind),
        language=normalized_language,
        required_placeholders=[AUTHOR_PLACEHOLDER, SKILLS_PLACEHOLDER, QUERY_PLACEHOLDER],
    )
    prompt = render_prompt(
        template,
        {
            AUTHOR_PLACEHOLDER: author_name.strip() or "Unknown Economist",
            SKILLS_PLACEHOLDER: context,
            QUERY_PLACEHOLDER: normalized_query,
        },
    )

    llm_payload, llm_source, llm_warning, llm_failure_reason = _invoke_llm_answer(
        prompt,
        language=normalized_language,
    )
    if llm_payload is not None and llm_source is not None:
        answer_payload = llm_payload
        answer_source = llm_source
        answer_warning = llm_warning
    else:
        answer_warning = llm_warning
        answer_fallback_reason = llm_failure_reason

    selected_skill_index = selected_skill_indices[0] if selected_skill_indices else None
    selected_section_id = selected_section_ids[0] if selected_section_ids else None
    selected_main_skill_name = (
        selected_main_skill_names[0] if selected_main_skill_names else None
    )

    return {
        "query": query,
        "query_kind": query_kind,
        "selected_skill_indices": selected_skill_indices,
        "selected_section_ids": selected_section_ids,
        "selected_skill_index": selected_skill_index,
        "selected_section_id": selected_section_id,
        "selected_main_skill_names": selected_main_skill_names,
        "selected_main_skill_name": selected_main_skill_name,
        "selected_sub_skill_names": selected_sub_skill_names,
        "selection_mode": selection_mode,
        "selection_warning": selection_warning,
        "answer_source": answer_source,
        "answer_warning": answer_warning,
        "answer_fallback_reason": answer_fallback_reason,
        "answer": answer_payload,
    }
