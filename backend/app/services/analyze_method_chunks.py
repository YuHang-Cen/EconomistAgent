"""执行方法分析阶段，基于段落生成最小 method_analysis 结构。"""

from __future__ import annotations

from typing import Any


def run_analyze_method_chunks(segments: list[dict[str, Any]]) -> dict[str, Any]:
    """将段落样本转换为最小 method_analysis 结果。"""
    chunks: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        content = str(segment["content"])
        chapter_id = str(segment["chapter_id"])
        chunk_id = int(index + 1)
        first_words = " ".join(content.split()[:8]) if content else "economic reasoning"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "chapter_id": chapter_id,
                "content": content,
                "analysis": {
                    "methodPatterns": {
                        "raw_pattern": f"Start from evidence in {first_words}.",
                        "normalized_pattern": "causal-diagnosis",
                        "actions": [
                            "identify assumptions",
                            "trace causal mechanism",
                            "evaluate implications",
                        ],
                        "method_program": (
                            "Identify assumptions, trace mechanism, evaluate outcomes."
                        ),
                    },
                    "methodSignals": {
                        "perspective": "institutional",
                        "nature": "analytical",
                        "time_orientation": "dynamic",
                        "system_scope": "macro",
                        "equilibrium_view": "non-equilibrium",
                        "logic": ["causal", "comparative"],
                    },
                },
            }
        )
    return {"chunks": chunks}
