from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.core.security import hash_token

pytestmark = pytest.mark.integration

Execute = Callable[..., list[tuple[Any, ...]]]


async def test_demo_login_sets_a_hardened_session_cookie(
    demo_client: httpx.AsyncClient, db_execute: Execute, log_in: Any
) -> None:
    response = await log_in(demo_client)

    assert response.status_code == 200
    assert response.json() == {"email": "demo@example.com", "role": "owner", "is_demo": True}
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header
    assert response.headers["cache-control"] == "no-store"

    me = await demo_client.get("/auth/me")
    assert me.status_code == 200

    token = response.cookies["oa_session"]
    stored = db_execute("SELECT token_hash FROM user_sessions")
    assert stored == [(hash_token(token),)]  # only the hash is stored
    assert db_execute("SELECT action FROM audit_log") == [("auth.login",)]


async def test_secure_flag_is_set_when_enabled(
    app_settings: Callable[..., Settings], run_app: Any, log_in: Any
) -> None:
    async with run_app(app_settings(session_cookie_secure=True)) as (_app, client):
        response = await log_in(client)
    assert "secure" in response.headers["set-cookie"].lower()


async def test_wrong_credentials_are_rejected(demo_client: httpx.AsyncClient, log_in: Any) -> None:
    wrong_password = await log_in(demo_client, password="not-the-password")
    unknown_user = await log_in(demo_client, email="nobody@example.com")
    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    assert wrong_password.json()["code"] == "not_authenticated"
    assert wrong_password.json()["message"] == unknown_user.json()["message"]


async def test_account_is_locked_after_repeated_failures(
    demo_client: httpx.AsyncClient, log_in: Any
) -> None:
    for _ in range(5):
        assert (await log_in(demo_client, password="wrong-password")).status_code == 401
    locked = await log_in(demo_client)  # even the right password is refused for a while
    assert locked.status_code == 429
    assert locked.json()["code"] == "too_many_attempts"
    assert int(locked.headers["retry-after"]) > 0


async def test_protected_routes_need_a_session(demo_client: httpx.AsyncClient) -> None:
    for method, path in [
        ("GET", "/auth/me"),
        ("GET", "/offer-profiles/current"),
        ("POST", "/offer-profiles/analyze"),
        ("GET", "/budget"),
    ]:
        response = await demo_client.request(method, path, json={})
        assert response.status_code == 401, path


async def test_logout_revokes_the_session(demo_client: httpx.AsyncClient, log_in: Any) -> None:
    token = (await log_in(demo_client)).cookies["oa_session"]
    assert (await demo_client.post("/auth/logout")).status_code == 204
    demo_client.cookies.set("oa_session", token)  # replaying the old cookie does not work
    assert (await demo_client.get("/auth/me")).status_code == 401


async def test_demo_account_is_refused_outside_demo_mode(
    app_settings: Callable[..., Settings], run_app: Any, log_in: Any
) -> None:
    async with run_app(app_settings(demo_mode=True)) as (_app, client):
        token = (await log_in(client)).cookies["oa_session"]
    async with run_app(app_settings(demo_mode=False)) as (_app, client):
        assert (await log_in(client)).status_code == 401
        client.cookies.set("oa_session", token)
        assert (await client.get("/auth/me")).status_code == 401


async def test_admin_account_comes_from_the_configuration(
    app_settings: Callable[..., Settings], run_app: Any, log_in: Any
) -> None:
    settings = app_settings(
        demo_mode=False, admin_email="Owner@Example.com", admin_password="a-long-test-password"
    )
    async with run_app(settings) as (_app, client):
        response = await log_in(client, "owner@example.com", "a-long-test-password")
    assert response.status_code == 200
    assert response.json()["is_demo"] is False


async def test_short_admin_password_is_refused(
    app_settings: Callable[..., Settings], run_app: Any, log_in: Any
) -> None:
    settings = app_settings(
        demo_mode=False, admin_email="owner@example.com", admin_password="short"
    )
    async with run_app(settings) as (_app, client):
        assert (await log_in(client, "owner@example.com", "short")).status_code == 401
