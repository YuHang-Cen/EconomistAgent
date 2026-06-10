"""Generate a baseline single-call article without skill context."""

from __future__ import annotations

from typing import Any

from app.domain.language import normalize_author_language
from app.services.llm_utils import (
    build_optional_llm,
    load_prompt_by_language,
    normalize_message_content,
    parse_json_with_recovery,
    render_prompt,
)

AUTHOR_PLACEHOLDER = "{{AUTHOR}}"
QUERY_PLACEHOLDER = "{{QUERY}}"


def _validate_direct_api_article(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None

    markdown = value.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        return None

    title = value.get("title")
    normalized_title = title.strip() if isinstance(title, str) else ""
    normalized_markdown = markdown.strip()
    return {
        "title": normalized_title,
        "markdown": normalized_markdown,
    }


def _fallback_direct_api_article(query: str, *, language: str) -> dict[str, str]:
    normalized_language = normalize_author_language(language)
    if normalized_language == "chinese":
        return {
            "title": "单次 API 生成结果",
            "markdown": (
                f"{query} 这个问题如果只做一次直接生成，通常会先给出一个总体判断，再补充几条支撑理由，"
                "但论证更容易停留在常见叙述层面。它会强调市场、政策、预期或产业趋势之间的关系，"
                "却未必能够稳定地区分短期波动和长期结构，也未必会把不同主体的激励约束展开到足够细。"
                "结果往往可读，但深度和可追溯性会比较有限。"
            ),
        }
    return {
        "title": "Single API Output",
        "markdown": (
            "A direct one-shot generation usually produces a readable judgment quickly, "
            "but it often stays at the level of familiar narrative. It can mention policy, "
            "market sentiment, and industrial trends, yet it is less reliable at separating "
            "short-term movement from long-term structure or tracing the incentive logic in depth."
        ),
    }


def run_direct_api_article(
    query: str,
    *,
    language: str = "english",
    author_name: str = "",
) -> dict[str, str]:
    normalized_language = normalize_author_language(language)
    article_payload = _fallback_direct_api_article(query=query, language=normalized_language)

    template = load_prompt_by_language(
        "direct_api_article_prompt.md",
        language=normalized_language,
        required_placeholders=[AUTHOR_PLACEHOLDER, QUERY_PLACEHOLDER],
    )
    prompt = render_prompt(
        template,
        {
            AUTHOR_PLACEHOLDER: author_name.strip() or "Unknown Economist",
            QUERY_PLACEHOLDER: query,
        },
    )

    llm = build_optional_llm()
    if llm is not None:
        try:
            response = llm.invoke(prompt)
            normalized = normalize_message_content(response.content).strip()
            candidate = parse_json_with_recovery(normalized)
            validated = _validate_direct_api_article(candidate)
            if validated is not None:
                article_payload = validated
        except Exception:
            pass

    return article_payload
