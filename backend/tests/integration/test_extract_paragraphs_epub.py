"""Focused extraction tests for EPUB parsing."""

from __future__ import annotations

from collections.abc import Callable

from app.services.extract_paragraphs import run_extract_paragraphs


CHAPTER_ONE_TITLE = "\u7b2c\u4e00\u7ae0 \u57ce\u5e02\u4e0e\u56fd\u5bb6"
CHAPTER_TWO_TITLE = "\u7b2c\u4e8c\u7ae0 \u7a7a\u95f4\u4e0e\u53d1\u5c55"


def test_run_extract_paragraphs_extracts_main_chapters_from_epub(
    create_test_epub: Callable[[str], str],
) -> None:
    """EPUB extraction should keep only main chapters and preserve output ordering."""
    epub_uri = create_test_epub("extract-main-chapters.epub")

    extracted = run_extract_paragraphs(book_title="Big Country Big City", pdf_uri=epub_uri)

    assert extracted
    assert all(set(item) == {"section_title", "chunk_id", "content", "order_index"} for item in extracted)

    section_titles: list[str] = []
    for item in extracted:
        if item["section_title"] not in section_titles:
            section_titles.append(str(item["section_title"]))

    assert section_titles == [CHAPTER_ONE_TITLE, CHAPTER_TWO_TITLE]
    assert extracted[0]["chunk_id"] == "001-0001"
    assert [item["order_index"] for item in extracted] == list(range(len(extracted)))
    assert all("\u4e0a\u7bc7" not in str(item["section_title"]) for item in extracted)
    assert all("\u81f4\u8c22" not in str(item["content"]) for item in extracted)
    assert all("\u6ce8\u91ca" not in str(item["content"]) for item in extracted)


def test_run_extract_paragraphs_keeps_epub_as_single_section_for_paper(
    create_test_epub: Callable[[str], str],
) -> None:
    epub_uri = create_test_epub("extract-paper.epub")

    extracted = run_extract_paragraphs(
        book_title="Paper Title",
        pdf_uri=epub_uri,
        document_kind="paper",
    )

    assert extracted
    assert {str(item["section_title"]) for item in extracted} == {"Paper Title"}
    merged_content = "\n".join(str(item["content"]) for item in extracted)
    assert CHAPTER_ONE_TITLE in merged_content
    assert CHAPTER_TWO_TITLE in merged_content
