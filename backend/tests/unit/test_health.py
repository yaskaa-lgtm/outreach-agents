from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.api import health as health_module
from app.core.config import Settings
from app.main import create_app

# Unreachable on purpose: these tests stub the database ping.
NO_DATABASE = "postgresql+psycopg://nobody:nothing@127.0.0.1:9/none"


def _stub_ping(result: bool) -> Callable[..., object]:
    async def _ping(*_args: object, **_kwargs: object) -> bool:
        return result

    return _ping


def test_health_ok_in_demo_mode(
    monkeypatch: pytest.MonkeyPatch, make_settings: Callable[..., Settings]
) -> None:
    monkeypatch.setattr(health_module, "ping_database", _stub_ping(True))
    app = create_app(make_settings(demo_mode=True, database_url=NO_DATABASE))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "DEMO",
        "database": "ok",
        "version": __version__,
    }


def test_health_degraded_when_database_is_down(
    monkeypatch: pytest.MonkeyPatch, make_settings: Callable[..., Settings]
) -> None:
    monkeypatch.setattr(health_module, "ping_database", _stub_ping(False))
    app = create_app(make_settings(demo_mode=False, dry_run=True, database_url=NO_DATABASE))

    with TestClient(app) as client:
        body = client.get("/health").json()

    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    assert body["mode"] == "DRY_RUN"


def test_cors_only_allows_configured_origins(
    monkeypatch: pytest.MonkeyPatch, make_settings: Callable[..., Settings]
) -> None:
    monkeypatch.setattr(health_module, "ping_database", _stub_ping(True))
    app = create_app(
        make_settings(cors_allow_origins=["http://localhost:3000"], database_url=NO_DATABASE)
    )

    with TestClient(app) as client:
        allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
        refused = client.get("/health", headers={"Origin": "https://evil.example.com"})

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in refused.headers
