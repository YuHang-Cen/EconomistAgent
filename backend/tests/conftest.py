"""Shared test fixtures: isolated DB, API client, and document factories."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

# Force tests to use isolated DB/storage and never touch dev runtime data.
os.environ["DATABASE_URL"] = "sqlite:///./storage/test_tmp/test_app.db"
os.environ["STORAGE_ROOT"] = "storage/test_tmp"
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("CELERY_TASK_EAGER_PROPAGATES", "true")
os.environ.setdefault("API_KEY", "replace_with_service_api_key")

from app.infra.db import Base, engine
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    """Recreate schema for each test case."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """Provide a TestClient preloaded with API key."""
    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": "replace_with_service_api_key"})
        yield test_client


@pytest.fixture()
def create_test_pdf() -> Callable[[str, list[str] | None], str]:
    """Create a temporary local PDF and return its absolute path."""
    input_root = Path(os.environ["STORAGE_ROOT"]) / "test_inputs"
    input_root.mkdir(parents=True, exist_ok=True)

    def _create(filename: str = "sample.pdf", blocks: list[str] | None = None) -> str:
        import fitz

        path = input_root / f"{uuid4()}-{filename}"
        document = fitz.open()
        page = document.new_page()

        if blocks is None:
            blocks = [
                "Institutions set baseline incentives and shape individual responses over time.",
                (
                    "Policy changes propagate through linked markets and alter aggregate "
                    "outcomes under constraints."
                ),
            ]

        if blocks:
            text = "\n\n".join(blocks)
            page.insert_textbox(fitz.Rect(72, 72, 540, 780), text, fontsize=11)

        document.save(path)
        document.close()
        return str(path)

    return _create


@pytest.fixture()
def create_test_epub() -> Callable[[str], str]:
    """Create a temporary local EPUB and return its absolute path."""
    input_root = Path(os.environ["STORAGE_ROOT"]) / "test_inputs"
    input_root.mkdir(parents=True, exist_ok=True)

    chapter_one_title = "\u7b2c\u4e00\u7ae0 \u57ce\u5e02\u4e0e\u56fd\u5bb6"
    chapter_two_title = "\u7b2c\u4e8c\u7ae0 \u7a7a\u95f4\u4e0e\u53d1\u5c55"

    def _html_doc(title: str, body: str) -> str:
        return (
            "<?xml version='1.0' encoding='utf-8'?>"
            "<html xmlns='http://www.w3.org/1999/xhtml'>"
            "<head>"
            f"<title>{title}</title>"
            "<meta http-equiv='Content-Type' content='text/html; charset=utf-8' />"
            "</head>"
            f"<body>{body}</body>"
            "</html>"
        )

    def _create(filename: str = "sample.epub") -> str:
        path = input_root / f"{uuid4()}-{filename}"

        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

        toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="bookid"/>
  </head>
  <docTitle><text>Test EPUB</text></docTitle>
  <navMap>
    <navPoint id="part-1" playOrder="1">
      <navLabel><text>\u4e0a\u7bc7 \u5927\u56fd\u96be\u9898</text></navLabel>
      <content src="text00002.xhtml"/>
      <navPoint id="chapter-1" playOrder="2">
        <navLabel><text>{chapter_one_title}</text></navLabel>
        <content src="text00002.xhtml"/>
      </navPoint>
    </navPoint>
    <navPoint id="chapter-2" playOrder="3">
      <navLabel><text>{chapter_two_title}</text></navLabel>
      <content src="text00003.xhtml"/>
    </navPoint>
    <navPoint id="thanks" playOrder="4">
      <navLabel><text>\u81f4\u8c22</text></navLabel>
      <content src="text00004.xhtml"/>
    </navPoint>
    <navPoint id="notes" playOrder="5">
      <navLabel><text>\u6ce8\u91ca</text></navLabel>
      <content src="text00005.xhtml"/>
    </navPoint>
  </navMap>
</ncx>
"""

        content_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Test EPUB</dc:title>
    <dc:language>zh</dc:language>
    <dc:identifier id="bookid">urn:uuid:test-epub</dc:identifier>
  </metadata>
  <manifest>
    <item id="front" href="text00000.xhtml" media-type="application/xhtml+xml"/>
    <item id="toc" href="text00001.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch1" href="text00002.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="text00003.xhtml" media-type="application/xhtml+xml"/>
    <item id="thanks" href="text00004.xhtml" media-type="application/xhtml+xml"/>
    <item id="notes" href="text00005.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="front"/>
    <itemref idref="toc"/>
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
    <itemref idref="thanks"/>
    <itemref idref="notes"/>
  </spine>
</package>
"""

        front_doc = _html_doc(
            "front",
            "<p>CIP data page should be ignored.</p><p>\u7248\u6743\u9875 should be ignored.</p>",
        )
        toc_doc = _html_doc(
            "toc",
            (
                "<div class='sgc-toc-title'>\u76ee\u5f55</div>"
                f"<p>{chapter_one_title}</p>"
                f"<p>{chapter_two_title}</p>"
            ),
        )
        chapter_one = _html_doc(
            "chapter1",
            (
                f"<h2>{chapter_one_title}</h2>"
                "<p>\u57ce\u5e02\u96c6\u805a\u5851\u9020\u4e86\u957f\u671f\u589e\u957f\u8def\u5f84\u3002</p>"
                "<p>\u5236\u5ea6\u5b89\u6392\u5f71\u54cd\u8d44\u6e90\u6d41\u52a8"
                "<span class='math-super'><a href='text00005.xhtml#bz1' id='z1'>1</a></span>\u3002</p>"
            ),
        )
        chapter_two = _html_doc(
            "chapter2",
            (
                f"<h2>{chapter_two_title}</h2>"
                "<p>\u7a7a\u95f4\u5931\u8861\u4f1a\u6539\u53d8\u52b3\u52a8\u4e0e\u8d44\u672c\u7684\u914d\u7f6e\u65b9\u5f0f\u3002</p>"
                "<p>\u516c\u5171\u653f\u7b56\u9700\u8981\u56de\u5e94\u771f\u5b9e\u7684\u4eba\u53e3\u6d41\u52a8\u3002</p>"
            ),
        )
        thanks_doc = _html_doc(
            "thanks",
            "<h2>\u81f4\u8c22</h2><p>\u8fd9\u6bb5\u5185\u5bb9\u4e0d\u5e94\u88ab\u5bfc\u5165\u3002</p>",
        )
        notes_doc = _html_doc(
            "notes",
            "<p class='zhusi'><a href='text00002.xhtml#z1' id='bz1'>[1]</a> \u8fd9\u662f\u4e00\u6761\u6ce8\u91ca\u3002</p>",
        )

        with ZipFile(path, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
            archive.writestr("META-INF/container.xml", container_xml, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/content.opf", content_opf, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/toc.ncx", toc_ncx, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/text00000.xhtml", front_doc, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/text00001.xhtml", toc_doc, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/text00002.xhtml", chapter_one, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/text00003.xhtml", chapter_two, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/text00004.xhtml", thanks_doc, compress_type=ZIP_DEFLATED)
            archive.writestr("OEBPS/text00005.xhtml", notes_doc, compress_type=ZIP_DEFLATED)

        return str(path)

    return _create
