from __future__ import annotations

import pytest
from app.cli import serve
from app.infra.db_recovery import StartupDatabaseBootstrapError


def test_serve_uses_configurable_bind_address(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    monkeypatch.setenv("BACKEND_HOST", "127.0.0.2")
    monkeypatch.setenv("BACKEND_PORT", "8123")
    monkeypatch.setattr("app.cli._bootstrap_storage_from_demo", lambda: events.append("storage"))
    monkeypatch.setattr("app.cli.bootstrap_database_on_startup", lambda: events.append("bootstrap"))

    def fake_run(command: list[str]) -> int:
        events.append("run")
        assert command == [
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.2",
            "--port",
            "8123",
        ]
        return 0

    monkeypatch.setattr("app.cli._run", fake_run)

    with pytest.raises(SystemExit) as exc:
        serve()

    assert exc.value.code == 0
    assert events == ["storage", "bootstrap", "run"]


def test_serve_exits_when_bootstrap_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_bootstrap() -> None:
        raise StartupDatabaseBootstrapError("bootstrap failed")

    monkeypatch.setattr("app.cli._bootstrap_storage_from_demo", lambda: None)
    monkeypatch.setattr("app.cli.bootstrap_database_on_startup", fail_bootstrap)

    with pytest.raises(SystemExit) as exc:
        serve()

    assert exc.value.code == 1
