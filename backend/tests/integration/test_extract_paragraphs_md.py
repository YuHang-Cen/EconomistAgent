"""Focused extraction tests for Markdown parsing."""

from __future__ import annotations

from collections.abc import Callable

from app.services.extract_paragraphs import run_extract_paragraphs


def test_run_extract_paragraphs_extracts_single_markdown_section(
    create_test_markdown: Callable[[str, str | None], str],
) -> None:
    """Markdown extraction should keep one section and preserve paragraph ordering."""
    markdown_uri = create_test_markdown("extract-single-section.md")

    extracted = run_extract_paragraphs(book_title="Fallback Book Title", pdf_uri=markdown_uri)

    assert extracted
    assert all(set(item) == {"section_title", "chunk_id", "content", "order_index"} for item in extracted)
    assert {str(item["section_title"]) for item in extracted} == {"Markdown Import Title"}
    assert extracted[0]["chunk_id"] == "001-0001"
    assert [item["order_index"] for item in extracted] == list(range(len(extracted)))
    assert any("Section Context" in str(item["content"]) for item in extracted)
    assert any("Detail Notes" in str(item["content"]) for item in extracted)
    assert len({str(item["section_title"]) for item in extracted}) == 1
