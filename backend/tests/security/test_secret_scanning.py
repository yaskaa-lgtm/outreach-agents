"""Proof that the pre-commit gitleaks hook blocks a commit containing a secret.

The test creates a throw-away Git repository, installs *this project's* pre-commit
configuration in it, then tries to commit a fake Anthropic key and a fake Fernet key.

The fake secrets are generated at runtime so that this file itself contains nothing
that looks like a secret (otherwise gitleaks would, rightly, refuse to commit it).
The gitleaks hook runs in Docker: these tests are skipped when Docker is not running,
unless REQUIRE_DOCKER=1 (set in CI), where a missing Docker is a failure.
"""

from __future__ import annotations

import base64
import os
import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GIT = shutil.which("git")
DOCKER = shutil.which("docker")


def _docker_is_running() -> bool:
    if DOCKER is None:
        return False
    info = subprocess.run([DOCKER, "info"], capture_output=True, check=False)
    return info.returncode == 0


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(GIT is None, reason="git is not installed"),
    pytest.mark.skipif(
        not os.environ.get("REQUIRE_DOCKER") and not _docker_is_running(),
        reason="Docker is not running (the gitleaks hook runs in Docker)",
    ),
]


def _fake_anthropic_key() -> str:
    alphabet = string.ascii_letters + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(93))
    return "sk-ant-" + "api03-" + body + "AA"


def _fake_fernet_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode()


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A fresh Git repository using this project's pre-commit and gitleaks configuration."""
    assert GIT is not None
    _run([GIT, "init", "--quiet", "-b", "main"], tmp_path)
    _run([GIT, "config", "user.name", "Test Runner"], tmp_path)
    _run([GIT, "config", "user.email", "test-runner@example.com"], tmp_path)
    _run([GIT, "config", "commit.gpgsign", "false"], tmp_path)
    for name in (".pre-commit-config.yaml", ".gitleaks.toml"):
        shutil.copy(REPO_ROOT / name, tmp_path / name)
    _run([GIT, "add", ".pre-commit-config.yaml", ".gitleaks.toml"], tmp_path)

    installed = _run([sys.executable, "-m", "pre_commit", "install"], tmp_path)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    return tmp_path


def _commit(repo: Path, filename: str, content: str) -> subprocess.CompletedProcess[str]:
    assert GIT is not None
    (repo / filename).write_text(content, encoding="utf-8", newline="\n")
    _run([GIT, "add", filename], repo)
    return _run([GIT, "commit", "-m", "test commit"], repo)


@pytest.mark.parametrize(
    ("filename", "content_factory"),
    [
        ("llm.cfg", lambda: f'ANTHROPIC_API_KEY = "{_fake_anthropic_key()}"\n'),
        ("crypto.cfg", lambda: f"FERNET_KEY={_fake_fernet_key()}\n"),
    ],
    ids=["anthropic-key", "fernet-key"],
)
def test_commit_with_a_secret_is_blocked(
    scratch_repo: Path, filename: str, content_factory: object
) -> None:
    assert callable(content_factory)
    result = _commit(scratch_repo, filename, content_factory())
    output = result.stdout + result.stderr

    assert result.returncode != 0, f"the commit should have been blocked:\n{output}"
    # Blocked *by gitleaks finding the secret*, not by a broken hook installation.
    assert "An unexpected error has occurred" not in output
    assert "leaks found" in output, output
    assert _run([GIT or "git", "rev-parse", "--verify", "HEAD"], scratch_repo).returncode != 0


def test_commit_of_an_env_file_is_blocked(scratch_repo: Path) -> None:
    (scratch_repo / ".env").write_text("DEMO_MODE=true\n", encoding="utf-8")
    _run([GIT or "git", "add", "--force", ".env"], scratch_repo)
    result = _run([GIT or "git", "commit", "-m", "test commit"], scratch_repo)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "An unexpected error has occurred" not in output
    assert "Forbid .env files" in output


def test_clean_commit_is_accepted(scratch_repo: Path) -> None:
    result = _commit(scratch_repo, "notes.txt", "Nothing secret here.\n")
    assert result.returncode == 0, result.stdout + result.stderr
