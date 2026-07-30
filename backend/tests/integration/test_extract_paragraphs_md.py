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


def test_run_extract_paragraphs_preserves_numeric_content_in_markdown(
    create_test_markdown: Callable[[str, str | None], str],
) -> None:
    markdown_uri = create_test_markdown(
        "extract-numeric-content.md",
        content=(
            "# Numeric Import\n\n"
            "回归结果显示 1年以后房价上涨了3.2%，人均GDP系数约为2倍。"
            "变量 $Treat \\times Post$ 的估计值为0.45。"
        ),
    )

    extracted = run_extract_paragraphs(book_title="Fallback Book Title", pdf_uri=markdown_uri)

    assert extracted
    merged_content = "\n".join(str(item["content"]) for item in extracted)
    assert "1年以后" in merged_content
    assert "3.2%" in merged_content
    assert "2倍" in merged_content
    assert "0.45" in merged_content


def test_run_extract_paragraphs_keeps_markdown_as_single_section_for_paper(
    create_test_markdown: Callable[[str, str | None], str],
) -> None:
    markdown_uri = create_test_markdown("extract-paper.md")

    extracted = run_extract_paragraphs(
        book_title="Paper Title",
        pdf_uri=markdown_uri,
        document_kind="paper",
    )

    assert extracted
    assert {str(item["section_title"]) for item in extracted} == {"Paper Title"}
    merged_content = "\n".join(str(item["content"]) for item in extracted)
    assert "Markdown Import Title" in merged_content
    assert "Section Context" in merged_content
    assert "Detail Notes" in merged_content
