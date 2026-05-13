from __future__ import annotations

from app.services.extract_paragraphs_common import _clean_inline_footnotes


def test_clean_inline_footnotes_preserves_real_numeric_content() -> None:
    text = (
        "Polity2 的范围介于 -10 和 +10 之间，当它大于 0 时为民主。"
        "样本数量为 (4224)，总样本为 (11844)，从 1950 年至 2008 年占比 35.7%。"
    )

    cleaned = _clean_inline_footnotes(text)

    assert "-10" in cleaned
    assert "+10" in cleaned
    assert " 0 " in cleaned
    assert "(4224)" in cleaned
    assert "(11844)" in cleaned
    assert "1950" in cleaned
    assert "2008" in cleaned
    assert "35.7%" in cleaned


def test_clean_inline_footnotes_removes_footnote_markers() -> None:
    text = "这是一条带脚注的句子。12 另一句后面也有脚注,3 以及方括号脚注[4]"

    cleaned = _clean_inline_footnotes(text)

    assert "句子。12" not in cleaned
    assert "脚注,3" not in cleaned
    assert "[4]" not in cleaned
