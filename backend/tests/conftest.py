"""Shared test fixtures: isolated DB, API client, and PDF factory."""

from __future__ import annotations

import os
from collections.abc import Callable, Generator
from pathlib import Path
from uuid import uuid4

import pytest

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
    input_root = Path("storage") / "test_inputs"
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
