"""The repo's git hooks: main only changes through pull requests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".githooks"

# Ignore the developer's own git config (signing, global hooks, templates).
GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check, env=GIT_ENV
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(tmp_path, "init", "-q", "-b", "main", str(work))
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.com")
    git(work, "commit", "-q", "--allow-empty", "-m", "initial")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "-q", "origin", "main")  # before the hooks exist, like a fresh repo
    git(work, "config", "core.hooksPath", str(HOOKS))
    return work


def test_commit_on_main_is_refused(repo):
    result = git(repo, "commit", "--allow-empty", "-m", "direct", check=False)
    assert result.returncode != 0
    assert "refusing to commit directly to main" in result.stderr
    assert git(repo, "rev-list", "--count", "main").stdout.strip() == "1"


def test_commit_on_a_branch_is_allowed(repo):
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "commit", "-q", "--allow-empty", "-m", "work")
    assert git(repo, "rev-list", "--count", "feature").stdout.strip() == "2"


def test_push_of_a_branch_is_allowed(repo):
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "commit", "-q", "--allow-empty", "-m", "work")
    git(repo, "push", "-q", "origin", "feature")


def test_push_to_main_is_refused(repo):
    # e.g. a commit made with --no-verify, or a local merge into main
    git(repo, "commit", "-q", "--no-verify", "--allow-empty", "-m", "sneaky")
    result = git(repo, "push", "origin", "main", check=False)
    assert result.returncode != 0
    assert "refusing to push to main" in result.stderr


def test_push_of_a_branch_onto_main_is_refused(repo):
    git(repo, "switch", "-q", "-c", "feature")
    git(repo, "commit", "-q", "--allow-empty", "-m", "work")
    result = git(repo, "push", "origin", "feature:main", check=False)
    assert result.returncode != 0
    assert "refusing to push to main" in result.stderr
