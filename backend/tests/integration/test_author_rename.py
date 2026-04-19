"""Integration tests for PATCH /api/authors/{author_id}."""

from __future__ import annotations

import json

from app.infra import storage
from fastapi.testclient import TestClient


def _create_author(client: TestClient, name: str = "Rename Source") -> str:
    response = client.post(
        "/api/authors",
        json={"authorName": name, "school": "Test", "avatarUrl": ""},
    )
    return response.json()["data"]["authorId"]


def test_patch_author_renames_and_updates_manifest(client: TestClient) -> None:
    author_id = _create_author(client, name="Old Name")
    author_meta_path = storage.author_root(author_id=author_id) / "author_meta.json"
    before_meta = json.loads(author_meta_path.read_text(encoding="utf-8"))

    response = client.patch(
        f"/api/authors/{author_id}",
        json={"authorName": "  New Name  "},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["authorName"] == "New Name"

    list_payload = client.get("/api/authors").json()["data"]
    matched = next(item for item in list_payload if item["authorId"] == author_id)
    assert matched["authorName"] == "New Name"

    after_meta = json.loads(author_meta_path.read_text(encoding="utf-8"))
    assert after_meta["author_name"] == "New Name"
    assert after_meta["updated_at"] != before_meta["updated_at"]


def test_patch_author_rejects_blank_name(client: TestClient) -> None:
    author_id = _create_author(client, name="Blank Name")
    response = client.patch(
        f"/api/authors/{author_id}",
        json={"authorName": "   "},
    )
    payload = response.json()
    assert response.status_code == 422
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert "must not be empty" in payload["error"]["message"]


def test_patch_author_returns_404_when_author_missing(client: TestClient) -> None:
    response = client.patch(
        "/api/authors/not-found-author",
        json={"authorName": "Any Name"},
    )
    payload = response.json()
    assert response.status_code == 404
    assert payload["error"]["code"] == "NOT_FOUND"
    assert payload["error"]["message"] == "author not found"
