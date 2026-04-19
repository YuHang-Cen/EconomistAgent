"""Integration tests for author avatar upload and public retrieval."""

from __future__ import annotations

import base64
import json

from app.infra import storage
from fastapi.testclient import TestClient

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+kvxkAAAAASUVORK5CYII="
)
GIF_BYTES = base64.b64decode("R0lGODdhAQABAIAAAP///////ywAAAAAAQABAAACAkQBADs=")


def _create_author(client: TestClient, name: str = "Avatar Author") -> str:
    response = client.post(
        "/api/authors",
        json={"authorName": name, "school": "Test", "avatarUrl": ""},
    )
    return response.json()["data"]["authorId"]


def test_upload_author_avatar_success_and_public_access(client: TestClient) -> None:
    author_id = _create_author(client)

    upload_response = client.post(
        f"/api/authors/{author_id}/avatar/upload",
        files={"file": ("avatar.png", PNG_BYTES, "image/png")},
    )
    payload = upload_response.json()

    assert upload_response.status_code == 200
    assert payload["success"] is True
    avatar_url = payload["data"]["avatarUrl"]
    assert avatar_url.startswith(f"/api/public/authors/{author_id}/avatar?v=")

    list_response = client.get("/api/authors")
    listed = next(item for item in list_response.json()["data"] if item["authorId"] == author_id)
    assert listed["avatarUrl"] == avatar_url

    public_response = client.get(avatar_url)
    assert public_response.status_code == 200
    assert public_response.headers["content-type"].startswith("image/png")
    assert public_response.content == PNG_BYTES

    manifest_path = storage.author_root(author_id=author_id) / "author_meta.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["avatar_url"] == avatar_url


def test_upload_author_avatar_overwrites_previous_file(client: TestClient) -> None:
    author_id = _create_author(client, name="Overwrite Author")

    first = client.post(
        f"/api/authors/{author_id}/avatar/upload",
        files={"file": ("avatar.png", PNG_BYTES, "image/png")},
    )
    second = client.post(
        f"/api/authors/{author_id}/avatar/upload",
        files={"file": ("avatar.gif", GIF_BYTES, "image/gif")},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    avatar_files = [item for item in storage.author_root(author_id=author_id).glob("avatar.*") if item.is_file()]
    assert len(avatar_files) == 1
    assert avatar_files[0].suffix.lower() == ".gif"
    assert avatar_files[0].read_bytes() == GIF_BYTES


def test_upload_author_avatar_rejects_invalid_type_and_oversize(client: TestClient) -> None:
    author_id = _create_author(client, name="Invalid Avatar")

    bad_type = client.post(
        f"/api/authors/{author_id}/avatar/upload",
        files={"file": ("avatar.txt", b"not-image", "text/plain")},
    )
    assert bad_type.status_code == 422
    assert "must be one of" in bad_type.json()["error"]["message"]

    oversize_bytes = b"x" * (5 * 1024 * 1024 + 1)
    oversize = client.post(
        f"/api/authors/{author_id}/avatar/upload",
        files={"file": ("avatar.png", oversize_bytes, "image/png")},
    )
    assert oversize.status_code == 422
    assert "<= 5MB" in oversize.json()["error"]["message"]
