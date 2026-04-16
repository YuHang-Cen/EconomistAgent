"""提供测试会话公共 fixture。"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """提供 FastAPI 测试客户端。"""
    with TestClient(app) as test_client:
        yield test_client
