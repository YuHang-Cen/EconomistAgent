"""
作用：按段落词数切分文本块，调用 LLM 进行方法分析，并输出 method_analysis JSON。
输入：切分后的段落 JSON 文件
输出：{
  "chunks": [
    {
      "chunk_id": 1,
      "paragraph_indexes": [1, 2, 3],
      "word_count": 750,
      "analysis": {
        "methodPatterns": {
          "raw_pattern": "...",
          "normalized_pattern": "...",
          "actions": ["..."],
          "method_program": "..."
        },
        "methodSignals": {
          "perspective": "...",
          "nature": "...",
          "time_orientation": "...",
          "system_scope": "...",
          "equilibrium_view": "...",
          "logic": ["..."]
        }
      }
    }
  ],
   "errors": []
}
处理流程：
1. 分块策略:按 max_words 合并段落、超长段落独立成块、记录原始段落索引
2. LLM 调用：使用 LangChain ChatOpenAI、提示词模板占位符：{{CHUNK_TEXT}}、支持 Markdown 代码块/括号平衡 JSON 解析
3. 错误处理：解析失败记录到 errors 数组、不中断后续处理
"""

from __future__ import annotations


import argparse
import json
import os
import re
import sys
from dotenv import load_dotenv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


from langchain_openai import ChatOpenAI

DEFAULT_INPUT = Path(__file__).resolve().parent / "The-Road-To-Serfdom-Chapter1.paragraphs.json"
DEFAULT_PROMPT_FILE = Path(__file__).resolve().parent / "prompts/method_analysis_prompt_v2_en.md"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "analysis_outputs"
DEFAULT_OUTPUT_FILE = "method_analysis.json"
PROMPT_PLACEHOLDER = "{{CHUNK_TEXT}}"


@dataclass
class ParagraphRecord:
    """保存单个段落的基础信息。"""

    index: int
    context: str


@dataclass
class ChunkRecord:
    """保存分块后的文本与索引信息。"""

    chunk_id: int
    paragraph_indexes: list[int]
    text: str
    word_count: int


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="按段落分块并调用 DeepSeek 生成方法分析 JSON。")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="段落 JSON 输入文件路径。")
    parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE, help="Markdown 提示词路径。")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="输出目录路径。")
    parser.add_argument("--output-file", type=str, default=DEFAULT_OUTPUT_FILE, help="输出 JSON 文件名。")
    parser.add_argument("--max-words", type=int, default=800, help="每个 chunk 的最大词数。")
    parser.add_argument("--provider", type=str, default="deepseek", help="模型提供商名称。")
    parser.add_argument("--model-name", type=str, default="deepseek-chat", help="模型名称。")
    parser.add_argument("--api-base", type=str, default="https://api.deepseek.com/v1", help="API Base URL。")
    return parser.parse_args()


def load_paragraphs(input_path: Path) -> list[ParagraphRecord]:
    """读取并校验段落 JSON。"""
    if not input_path.exists():
        raise FileNotFoundError(f"未找到输入文件: {input_path}")

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("输入 JSON 必须是数组结构。")

    paragraphs: list[ParagraphRecord] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        context = item.get("context")
        if not isinstance(index, int) or not isinstance(context, str):
            continue
        text = context.strip()
        if not text:
            continue
        paragraphs.append(ParagraphRecord(index=index, context=text))

    if not paragraphs:
        raise ValueError("输入 JSON 中没有可用段落。")
    return paragraphs


def count_words(text: str) -> int:
    """统计文本词数，用于分块边界判断。"""
    return len(re.findall(r"\b[\w'-]+\b", text))


def create_chunks(paragraphs: list[ParagraphRecord], max_words: int) -> list[ChunkRecord]:
    """按最大词数把段落合并成多个 chunk。"""
    if max_words <= 0:
        raise ValueError("max_words 必须大于 0。")

    chunks: list[ChunkRecord] = []
    current_indexes: list[int] = []
    current_texts: list[str] = []
    current_word_count = 0

    def flush_current() -> None:
        """把当前累积内容写入一个 chunk。"""
        nonlocal current_indexes, current_texts, current_word_count
        if not current_indexes:
            return
        chunks.append(
            ChunkRecord(
                chunk_id=len(chunks) + 1,
                paragraph_indexes=current_indexes,
                text="\n\n".join(current_texts),
                word_count=current_word_count,
            )
        )
        current_indexes = []
        current_texts = []
        current_word_count = 0

    for paragraph in paragraphs:
        paragraph_words = count_words(paragraph.context)

        # 超长单段独立成块，不做截断。
        if paragraph_words > max_words:
            flush_current()
            chunks.append(
                ChunkRecord(
                    chunk_id=len(chunks) + 1,
                    paragraph_indexes=[paragraph.index],
                    text=paragraph.context,
                    word_count=paragraph_words,
                )
            )
            continue

        next_word_count = current_word_count + paragraph_words
        if current_indexes and next_word_count > max_words:
            flush_current()

        current_indexes.append(paragraph.index)
        current_texts.append(paragraph.context)
        current_word_count += paragraph_words

    flush_current()
    return chunks


def load_prompt_template(prompt_path: Path) -> str:
    """读取提示词模板并检查占位符。"""
    if not prompt_path.exists():
        raise FileNotFoundError(f"未找到提示词文件: {prompt_path}")
    template = prompt_path.read_text(encoding="utf-8")
    if PROMPT_PLACEHOLDER not in template:
        raise ValueError(f"提示词模板缺少占位符: {PROMPT_PLACEHOLDER}")
    return template


def render_prompt(template: str, chunk_text: str) -> str:
    """将 chunk 文本注入提示词模板。"""
    return template.replace(PROMPT_PLACEHOLDER, chunk_text)


def build_llm(model_name: str, api_base: str) -> ChatOpenAI:
    """初始化 LangChain ChatOpenAI 客户端。"""
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少环境变量 DEEPSEEK_API_KEY，无法调用 DeepSeek。")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=api_base,
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


def extract_fenced_json(text: str) -> str | None:
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


def extract_balanced_json_object(text: str) -> str | None:
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


def parse_json_with_recovery(raw_text: str) -> dict[str, Any]:
    """按“直接解析->代码块->括号平衡”顺序恢复 JSON。"""
    candidates: list[str] = [raw_text.strip()]

    fenced = extract_fenced_json(raw_text)
    if fenced:
        candidates.append(fenced)

    balanced = extract_balanced_json_object(raw_text)
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

    raise ValueError("模型返回内容无法解析为 JSON 对象。")


def normalize_analysis_shape(data: dict[str, Any]) -> dict[str, Any]:
    """将模型输出归一为目标 JSON 结构。"""
    method_patterns = data.get("methodPatterns")
    if not isinstance(method_patterns, dict):
        print("警告: methodPatterns 字段缺失或格式不正确，使用默认空值。")
        method_patterns = {}

    normalized_pattern = method_patterns.get("normalized_pattern")
    raw_pattern = method_patterns.get("raw_pattern")
    actions = method_patterns.get("actions")
    method_program = method_patterns.get("method_program")

    if not isinstance(normalized_pattern, str):
        normalized_pattern = ""

    if not isinstance(raw_pattern, str):
        raw_pattern = ""

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


def analyze_chunks(
    chunks: list[ChunkRecord],
    llm: ChatOpenAI,
    prompt_template: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """逐个 chunk 调用模型并收集成功结果与错误。"""
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for chunk in chunks:
        prompt = render_prompt(prompt_template, chunk.text)
        try:
            response = llm.invoke(prompt)
            raw_text = normalize_message_content(response.content)
            parsed = parse_json_with_recovery(raw_text)
            analysis = normalize_analysis_shape(parsed)
            results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "paragraph_indexes": chunk.paragraph_indexes,
                    "word_count": chunk.word_count,
                    "analysis": analysis,
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "paragraph_indexes": chunk.paragraph_indexes,
                    "word_count": chunk.word_count,
                    "error": str(exc),
                }
            )

    return results, errors


def save_output(
    output_dir: Path,
    output_file: str,
    source_file: Path,
    max_words: int,
    provider: str,
    model_name: str,
    api_base: str,
    chunks: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> Path:
    """保存汇总 JSON 到单独目录。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_file

    payload = {
        "source_file": str(source_file.name),
        "max_words": max_words,
        "model": {
            "provider": provider,
            "model_name": model_name,
            "api_base": api_base,
        },
        "chunks": chunks,
        "errors": errors,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    """程序入口：分块、调用 LLM、写出结果。"""
    args = parse_args()
    paragraphs = load_paragraphs(args.input)
    chunks = create_chunks(paragraphs, args.max_words)
    prompt_template = load_prompt_template(args.prompt_file)
    llm = build_llm(model_name=args.model_name, api_base=args.api_base)
    result_chunks, errors = analyze_chunks(chunks=chunks, llm=llm, prompt_template=prompt_template)

    output_path = save_output(
        output_dir=args.output_dir,
        output_file=args.output_file,
        source_file=args.input,
        max_words=args.max_words,
        provider=args.provider,
        model_name=args.model_name,
        api_base=args.api_base,
        chunks=result_chunks,
        errors=errors,
    )
    print(f"处理完成: 共 {len(chunks)} 个 chunk，成功 {len(result_chunks)}，失败 {len(errors)}")
    print(f"输出文件: {output_path}")


if __name__ == "__main__":
    
    try:
        load_dotenv()  # 加载 .env 文件中的环境变量
        main()
    except Exception as exc:  # pragma: no cover
        print(f"执行失败: {exc}", file=sys.stderr)
        sys.exit(1)
