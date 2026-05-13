"""Focused extraction tests for PDF parsing."""

from __future__ import annotations

from collections.abc import Callable

from app.services.extract_paragraphs import run_extract_paragraphs


def test_run_extract_paragraphs_preserves_numeric_content_in_pdf(
    create_test_pdf: Callable[[str, list[str] | None], str],
) -> None:
    pdf_uri = create_test_pdf(
        "extract-numeric-content.pdf",
        blocks=[
            (
                "Polity2 ranges from -10 to +10, and a regime is coded democratic when it is greater than 0. "
                "The authoritarian sample is 4224 out of 11844, covering 1950 to 2008 with a share of 35.7%."
            )
        ],
    )

    extracted = run_extract_paragraphs(book_title="Numeric PDF", pdf_uri=pdf_uri)

    assert extracted
    merged_content = "\n".join(str(item["content"]) for item in extracted)
    assert "-10" in merged_content
    assert "+10" in merged_content
    assert "greater than 0" in merged_content
    assert "4224" in merged_content
    assert "11844" in merged_content
    assert "1950" in merged_content
    assert "2008" in merged_content
    assert "35.7%" in merged_content
