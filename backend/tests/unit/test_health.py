"""验证健康检查接口可用。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    """健康检查接口应返回统一成功包裹。"""
    response = client.get("/health")
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["status"] == "ok"
    assert payload["error"] is None
    assert "requestId" in payload
    assert "timestamp" in payload
