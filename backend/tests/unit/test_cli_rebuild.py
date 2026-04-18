from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from app.cli import rebuild_db
from app.scripts.rebuild_db_from_storage import RebuildSummary


def test_rebuild_db_command_remains_available(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    expected_storage_root = Path("storage") / "test_tmp" / f"rebuild-command-{uuid4()}"
    expected_storage_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("app.cli.run_alembic_migrations", lambda: 0)

    import app.infra.storage as storage_module
    import app.scripts.rebuild_db_from_storage as rebuild_module

    monkeypatch.setattr(storage_module, "ensure_storage_root", lambda: expected_storage_root)

    def fake_rebuild(*, storage_root: Path) -> RebuildSummary:
        received_storage_root = storage_root
        assert received_storage_root == expected_storage_root
        return RebuildSummary(
            authors=1,
            documents=2,
            chapters=3,
            segments=4,
            snapshots=5,
            warnings=[],
        )

    monkeypatch.setattr(rebuild_module, "rebuild_from_storage", fake_rebuild)

    try:
        with pytest.raises(SystemExit) as exc:
            rebuild_db()

        assert exc.value.code == 0
        output = capsys.readouterr().out
        assert "'authors': 1" in output
    finally:
        shutil.rmtree(expected_storage_root, ignore_errors=True)
