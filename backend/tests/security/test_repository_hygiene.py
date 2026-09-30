"""Repository hygiene: secrets and personal data can never be committed by accident."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(GIT is None, reason="git is not installed")

MUST_BE_IGNORED = [
    ".env",
    ".env.local",
    ".env.production",
    "backend/.env",
    "secrets/smtp.txt",
    "data/prospects.json",
    "exports/campaign.xlsx",
    "leads.csv",
    "backend/leads.csv",
    "evals/runs/run-1.json",
    "server.pem",
    "private.key",
    "local.sqlite",
    "app.db",
    "api.log",
    "web/node_modules/react/index.js",
    "web/.next/build-manifest.json",
    ".venv/pyvenv.cfg",
    "backend/app/__pycache__/main.cpython-312.pyc",
    ".DS_Store",
]

MUST_BE_TRACKABLE = [
    ".env.example",
    "backend/tests/fixtures/companies.csv",
    "docs/PLAN.md",
    "backend/app/main.py",
]


def _is_ignored(path: str) -> bool:
    # --no-index: answer from the ignore rules only, even for files already tracked.
    result = subprocess.run(
        [GIT, "check-ignore", "--no-index", "--quiet", path],  # type: ignore[list-item]
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_sensitive_paths_are_git_ignored(path: str) -> None:
    assert _is_ignored(path), f"{path} must be git-ignored"


@pytest.mark.parametrize("path", MUST_BE_TRACKABLE)
def test_safe_paths_are_not_git_ignored(path: str) -> None:
    assert not _is_ignored(path), f"{path} must stay committable"


def test_no_environment_file_is_tracked() -> None:
    result = subprocess.run(
        [GIT, "ls-files"],  # type: ignore[list-item]
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = result.stdout.splitlines()
    offenders = [f for f in tracked if re.search(r"(^|/)\.env($|\.(?!example$))", f)]
    assert offenders == []


def _env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def test_env_example_documents_every_setting() -> None:
    documented = set(_env_example())
    expected = {name.upper() for name in Settings.model_fields}
    assert expected - documented == set(), "add the missing variables to .env.example"


def test_env_example_contains_only_placeholder_secrets() -> None:
    secret_like = re.compile(r"(API_KEY|SECRET|TOKEN|FERNET_KEY)$")
    for key, value in _env_example().items():
        if secret_like.search(key):
            assert value == "" or "xxxxxxxx" in value, f"{key} must be a fake placeholder"
