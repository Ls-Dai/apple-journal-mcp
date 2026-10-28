from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

from apple_journal_mcp import server

# A stand-in for journal-cli: logs its argv, then replies with whatever the
# test configured through FAKE_* env vars (inherited by the subprocess).
FAKE_CLI = """\
#!{python}
import json, os, sys
with open({log!r}, "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
sys.stdout.write(os.environ.get("FAKE_STDOUT", ""))
sys.stderr.write(os.environ.get("FAKE_STDERR", ""))
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
"""


class FakeCli:
    def __init__(self, path: Path, log: Path, monkeypatch: pytest.MonkeyPatch):
        self.path = path
        self.log = log
        self._monkeypatch = monkeypatch

    def respond(self, stdout: str = "", stderr: str = "", exit_code: int = 0) -> None:
        self._monkeypatch.setenv("FAKE_STDOUT", stdout)
        self._monkeypatch.setenv("FAKE_STDERR", stderr)
        self._monkeypatch.setenv("FAKE_EXIT", str(exit_code))

    @property
    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]


@pytest.fixture
def fake_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeCli:
    log = tmp_path / "calls.jsonl"
    path = tmp_path / "journal-cli"
    path.write_text(FAKE_CLI.format(python=sys.executable, log=str(log)))
    path.chmod(0o755)
    monkeypatch.setenv("JOURNAL_CLI", str(path))
    # Never let a test fall through to a real journal-cli on this machine.
    monkeypatch.setattr(server, "_candidates", lambda: [str(path)])
    fake = FakeCli(path, log, monkeypatch)
    fake.respond(stdout="[]")
    return fake


class FixedDate(date):
    @classmethod
    def today(cls) -> FixedDate:
        return cls(2026, 10, 28)


@pytest.fixture
def frozen_today(monkeypatch: pytest.MonkeyPatch) -> date:
    monkeypatch.setattr(server, "date", FixedDate)
    return FixedDate.today()
