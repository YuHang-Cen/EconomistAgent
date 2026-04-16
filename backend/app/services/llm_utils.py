"""提供 Prompt 装配、可选 LLM 调用与 JSON 解析恢复工具。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.infra.settings import get_settings
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


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
    settings = get_settings()
    api_key = settings.deepseek_api_key.strip()
    if not api_key:
        return None
    api_base = settings.api_base.rstrip("/")
    if api_base.endswith("/v1"):
        base_url = api_base
    else:
        base_url = f"{api_base}/v1"
    return ChatOpenAI(
        model=settings.model_name,
        api_key=SecretStr(api_key),
        base_url=base_url,
        temperature=0,
    )


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
