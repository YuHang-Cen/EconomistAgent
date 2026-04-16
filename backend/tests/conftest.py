"""提供测试公共夹具，包括数据库重置与鉴权请求头。"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from app.infra.db import Base, engine
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    """每个测试用例前重建数据库表结构。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """提供带默认 API Key 的测试客户端。"""
    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": "replace_with_service_api_key"})
        yield test_client
