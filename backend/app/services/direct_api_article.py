"""Generate a baseline single-call article without skill context."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.domain.language import normalize_author_language
from app.services.llm_utils import (
    build_optional_llm,
    get_effective_model_config,
    load_prompt_by_language,
    normalize_message_content,
    parse_json_with_recovery,
    render_prompt,
)

AUTHOR_PLACEHOLDER = "{{AUTHOR}}"
QUERY_PLACEHOLDER = "{{QUERY}}"
JSON_RESPONSE_FORMAT = {"type": "json_object"}
DIRECT_ARTICLE_FORMAT_RETRY_SUFFIX = """

## Output Correction

Return only one valid JSON object with a non-empty markdown string and an optional
title string. Escape newlines inside JSON strings. Do not add commentary or fences.
"""
logger = logging.getLogger(__name__)


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


def _fallback_direct_api_article(
    query: str,
    *,
    language: str,
    error_code: str,
) -> dict[str, Any]:
    normalized_language = normalize_author_language(language)
    if normalized_language == "chinese":
        return {
            "status": "fallback",
            "error_code": error_code,
            "title": "单次 API 生成结果",
            "markdown": (
                f"{query} 这个问题如果只做一次直接生成，通常会先给出一个总体判断，"
                "再补充几条支撑理由，"
                "但论证更容易停留在常见叙述层面。它会强调市场、政策、预期或产业趋势之间的关系，"
                "却未必能够稳定地区分短期波动和长期结构，也未必会把不同主体的激励约束展开到足够细。"
                "结果往往可读，但深度和可追溯性会比较有限。"
            ),
        }
    return {
        "status": "fallback",
        "error_code": error_code,
        "title": "Single API Output",
        "markdown": (
            "A direct one-shot generation usually produces a readable judgment quickly, "
            "but it often stays at the level of familiar narrative. It can mention policy, "
            "market sentiment, and industrial trends, yet it is less reliable at separating "
            "short-term movement from long-term structure or tracing the incentive logic in depth."
        ),
    }


def _text_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _exception_status_code(exc: Exception) -> int | str | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, (int, str)):
        return status_code
    response = getattr(exc, "response", None)
    response_status_code = getattr(response, "status_code", None)
    return response_status_code if isinstance(response_status_code, (int, str)) else None


def _log_fallback(
    error_code: str,
    *,
    query: str,
    language: str,
    model_name: str,
    api_base: str,
    response_text: str = "",
    exc: Exception | None = None,
    retrying: bool = False,
) -> None:
    logger.warning(
        "direct_api_article generation_issue error_code=%s retrying=%s "
        "model_name=%s api_base=%s "
        "language=%s query_hash=%s response_length=%d response_hash=%s "
        "exception_type=%s status_code=%s request_id=%s",
        error_code,
        retrying,
        model_name,
        api_base,
        language,
        _text_fingerprint(query),
        len(response_text),
        _text_fingerprint(response_text) if response_text else "",
        type(exc).__name__ if exc is not None else "",
        _exception_status_code(exc) if exc is not None else None,
        getattr(exc, "request_id", None) if exc is not None else None,
    )


def _fallback_with_log(
    error_code: str,
    *,
    query: str,
    language: str,
    model_name: str,
    api_base: str,
    response_text: str = "",
    exc: Exception | None = None,
) -> dict[str, Any]:
    _log_fallback(
        error_code,
        query=query,
        language=language,
        model_name=model_name,
        api_base=api_base,
        response_text=response_text,
        exc=exc,
    )
    return _fallback_direct_api_article(
        query=query,
        language=language,
        error_code=error_code,
    )


def run_direct_api_article(
    query: str,
    *,
    language: str = "english",
    author_name: str = "",
) -> dict[str, Any]:
    normalized_language = normalize_author_language(language)
    effective_model_config = get_effective_model_config()
    model_name = effective_model_config["model_name"]
    api_base = effective_model_config["api_base"]

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

    try:
        llm = build_optional_llm()
    except Exception as exc:
        return _fallback_with_log(
            "llm_initialization_failed",
            query=query,
            language=normalized_language,
            model_name=model_name,
            api_base=api_base,
            exc=exc,
        )
    if llm is None:
        return _fallback_with_log(
            "llm_unavailable",
            query=query,
            language=normalized_language,
            model_name=model_name,
            api_base=api_base,
        )

    current_prompt = prompt
    for attempt in range(2):
        try:
            response = llm.invoke(
                current_prompt,
                response_format=JSON_RESPONSE_FORMAT,
            )
        except Exception as exc:
            return _fallback_with_log(
                "llm_invoke_failed",
                query=query,
                language=normalized_language,
                model_name=model_name,
                api_base=api_base,
                exc=exc,
            )

        normalized = ""
        error_code = "invalid_model_json"
        parse_exception: Exception | None = None
        try:
            normalized = normalize_message_content(response.content).strip()
            candidate = parse_json_with_recovery(normalized)
        except Exception as exc:
            parse_exception = exc
            validated = None
        else:
            validated = _validate_direct_api_article(candidate)
            if validated is None:
                error_code = "missing_markdown"

        if validated is not None:
            return {
                **validated,
                "status": "generated",
                "error_code": None,
            }

        if attempt == 0:
            _log_fallback(
                error_code,
                query=query,
                language=normalized_language,
                model_name=model_name,
                api_base=api_base,
                response_text=normalized,
                exc=parse_exception,
                retrying=True,
            )
            current_prompt = f"{prompt}{DIRECT_ARTICLE_FORMAT_RETRY_SUFFIX}"
            continue

        return _fallback_with_log(
            error_code,
            query=query,
            language=normalized_language,
            model_name=model_name,
            api_base=api_base,
            response_text=normalized,
            exc=parse_exception,
        )

    raise AssertionError("direct article generation loop exited unexpectedly")
