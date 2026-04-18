"""提供 Prompt 装配、可选 LLM 调用与 JSON 解析恢复工具。"""

from __future__ import annotations

import contextlib
import json
import re
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from app.infra.settings import get_settings
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
_MODEL_CONFIG_OVERRIDE: ContextVar[dict[str, str] | None] = ContextVar(
    "model_config_override", default=None
)


def _normalize_model_config(raw: dict[str, Any] | None) -> dict[str, str]:
    """Normalize request-level model config into internal snake_case keys."""
    if not isinstance(raw, dict):
        return {}

    def _read_key(*names: str) -> str:
        for name in names:
            value = raw.get(name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    normalized = {
        "provider": _read_key("provider"),
        "model_name": _read_key("model_name", "modelName"),
        "api_base": _read_key("api_base", "apiBase"),
        "api_key": _read_key("api_key", "apiKey"),
    }
    return {key: value for key, value in normalized.items() if value}


@contextlib.contextmanager
def model_config_override_scope(model_config: dict[str, Any] | None):
    """Temporarily apply request-level model config for downstream LLM builders."""
    token = _MODEL_CONFIG_OVERRIDE.set(_normalize_model_config(model_config))
    try:
        yield
    finally:
        _MODEL_CONFIG_OVERRIDE.reset(token)


def get_effective_model_config() -> dict[str, str]:
    """Resolve effective model config: override first, fallback to settings."""
    settings = get_settings()
    override = _MODEL_CONFIG_OVERRIDE.get() or {}
    provider = (override.get("provider") or settings.provider or "deepseek").strip()
    model_name = (override.get("model_name") or settings.model_name or "deepseek-chat").strip()
    api_base = (override.get("api_base") or settings.api_base or "https://api.deepseek.com").strip()
    api_key = (override.get("api_key") or settings.deepseek_api_key or "").strip()
    return {
        "provider": provider,
        "model_name": model_name,
        "api_base": api_base,
        "api_key": api_key,
    }


def load_prompt(prompt_filename: str, required_placeholders: list[str] | None = None) -> str:
    """读取 Prompt 文件并校验占位符。"""
    prompt_path = PROMPT_DIR / prompt_filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"prompt file not found: {prompt_path}")
    template = prompt_path.read_text(encoding="utf-8")
    for placeholder in required_placeholders or []:
        if placeholder not in template:
            raise ValueError(f"prompt missing placeholder: {placeholder}")
    return template


def render_prompt(template: str, mapping: dict[str, str]) -> str:
    """按照占位符映射渲染 Prompt。"""
    rendered = template
    for key, value in mapping.items():
        rendered = rendered.replace(key, value)
    return rendered


def build_optional_llm() -> ChatOpenAI | None:
    """按配置构建 LLM 客户端，缺少密钥时返回 None。"""
    effective = get_effective_model_config()
    api_key = effective["api_key"]
    if not api_key:
        return None
    api_base = effective["api_base"].rstrip("/")
    if api_base.endswith("/v1"):
        base_url = api_base
    else:
        base_url = f"{api_base}/v1"
    return ChatOpenAI(
        model=effective["model_name"],
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=0,
    )


def build_required_llm() -> ChatOpenAI:
    """Build LLM client or raise when key is missing."""
    llm = build_optional_llm()
    if llm is None:
        raise RuntimeError("missing model api key for current request")
    return llm


def normalize_message_content(content: Any) -> str:
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
    """提取 markdown 代码块中的 JSON。"""
    pattern = re.compile(r"```json\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    fallback = re.compile(r"```\s*(.*?)\s*```", re.DOTALL)
    fallback_match = fallback.search(text)
    if fallback_match:
        return fallback_match.group(1).strip()
    return None


def _extract_balanced_json(text: str) -> str | None:
    """提取首个括号平衡的 JSON 对象。"""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
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
                return text[start : index + 1]
    return None


def parse_json_with_recovery(raw_text: str) -> dict[str, Any]:
    """按多种策略恢复并解析 JSON 对象。"""
    candidates: list[str] = [raw_text.strip()]
    fenced = _extract_fenced_json(raw_text)
    if fenced:
        candidates.append(fenced)
    balanced = _extract_balanced_json(raw_text)
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
    raise ValueError("model output is not valid JSON object")


def invoke_prompt_for_json(prompt: str) -> dict[str, Any] | None:
    """使用可选 LLM 调用 Prompt，成功时返回 JSON 对象。"""
    llm = build_optional_llm()
    if llm is None:
        return None
    try:
        response = llm.invoke(prompt)
    except Exception:
        return None
    text = normalize_message_content(response.content)
    try:
        return parse_json_with_recovery(text)
    except Exception:
        return None
