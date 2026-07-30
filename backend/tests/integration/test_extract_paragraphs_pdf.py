"""Focused extraction tests for PDF parsing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from app.services.extract_paragraphs import run_extract_paragraphs


def _create_multi_section_pdf() -> str:
    import fitz

    input_root = Path("storage") / "test_tmp" / "test_inputs"
    input_root.mkdir(parents=True, exist_ok=True)
    path = input_root / f"{uuid4()}-multi-section.pdf"

    document = fitz.open()
    first_page = document.new_page()
    first_page.insert_textbox(
        fitz.Rect(72, 72, 540, 780),
        "Chapter 1 Foundations\n\nFirst chapter paragraph about institutional baselines.",
        fontsize=11,
    )
    second_page = document.new_page()
    second_page.insert_textbox(
        fitz.Rect(72, 72, 540, 780),
        "Chapter 2 Dynamics\n\nSecond chapter paragraph about policy propagation.",
        fontsize=11,
    )
    document.save(path)
    document.close()
    return str(path)


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


def test_run_extract_paragraphs_keeps_pdf_as_single_section_for_paper() -> None:
    pdf_uri = _create_multi_section_pdf()

    extracted = run_extract_paragraphs(
        book_title="Paper Title",
        pdf_uri=pdf_uri,
        document_kind="paper",
    )

    assert extracted
    assert {str(item["section_title"]) for item in extracted} == {"Paper Title"}
    assert all(str(item["chunk_id"]).startswith("001-") for item in extracted)
    merged_content = "\n".join(str(item["content"]) for item in extracted)
    assert "First chapter paragraph" in merged_content
    assert "Second chapter paragraph" in merged_content
