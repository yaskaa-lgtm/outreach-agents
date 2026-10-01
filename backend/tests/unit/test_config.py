from __future__ import annotations

from collections.abc import Callable

import pytest

from app.core.config import RunMode, Settings


def test_defaults_are_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    settings = Settings(_env_file=None)
    assert settings.demo_mode is True
    assert settings.dry_run is True
    assert settings.mode is RunMode.DEMO


@pytest.mark.parametrize(
    ("demo_mode", "dry_run", "expected"),
    [
        (True, True, RunMode.DEMO),
        (True, False, RunMode.DEMO),  # demo mode can never send for real
        (False, True, RunMode.DRY_RUN),
        (False, False, RunMode.LIVE),
    ],
)
def test_mode(
    make_settings: Callable[..., Settings], demo_mode: bool, dry_run: bool, expected: RunMode
) -> None:
    assert make_settings(demo_mode=demo_mode, dry_run=dry_run).mode is expected


def test_mode_comes_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("DRY_RUN", "false")
    assert Settings(_env_file=None).mode is RunMode.LIVE


def test_secrets_are_hidden_in_repr(make_settings: Callable[..., Settings]) -> None:
    fake_secret = "not-a-real-secret-value-for-tests"
    settings = make_settings(anthropic_api_key=fake_secret, hunter_api_key=fake_secret)
    assert fake_secret not in repr(settings)
    assert fake_secret not in str(settings.model_dump())
    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == fake_secret


def test_empty_hunter_key_means_no_hunter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUNTER_API_KEY", "")
    assert Settings(_env_file=None).hunter_api_key is None


def test_model_names_are_not_hard_coded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_MODEL_REASONING", raising=False)
    monkeypatch.delenv("LLM_MODEL_FAST", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_model_reasoning is None
    assert settings.llm_model_fast is None
