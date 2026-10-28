"""The real journal-cli against a synthetic, throwaway store.

Opt-in: point JOURNAL_CLI_SRC at an apple-journal-cli checkout, whose
tests/make-fixture.sh builds a schema-only store with no personal data:

    JOURNAL_CLI_SRC=~/Development/apple-journal-cli uv run pytest -m integration

Seeding writes go through journal-cli with JOURNAL_DB pinned to the fixture
and no --live, so the real Journal store is out of reach twice over.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import date, timedelta
from pathlib import Path

import pytest

from apple_journal_mcp import server

pytestmark = pytest.mark.integration

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)

ENTRIES = [
    ("Mid month", "Planning the Tokyo trip", "2025-01-15 12:00"),
    ("Morning", "Coffee before work", "2025-01-31 08:30"),
    ("Evening", "Late dinner", "2025-01-31 20:15"),
    ("Next month", "February already", "2025-02-01 09:00"),
    ("Last night", "Written just before midnight", f"{YESTERDAY} 23:59"),
    ("Today", "Written just after midnight", f"{TODAY} 00:01"),
]


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> str:
    src = os.environ.get("JOURNAL_CLI_SRC")
    if not src:
        pytest.skip("set JOURNAL_CLI_SRC to an apple-journal-cli checkout")
    make_fixture = Path(src).expanduser() / "tests" / "make-fixture.sh"
    if not make_fixture.is_file():
        pytest.skip(f"{make_fixture} not found")
    try:
        cli = server._cli_path()
    except FileNotFoundError:
        pytest.skip("journal-cli not installed")

    root = tmp_path_factory.mktemp("store")
    out = subprocess.run(
        [str(make_fixture), str(root)], capture_output=True, text=True, check=True
    ).stdout
    db = out.strip().splitlines()[-1]
    assert Path(db).parent == root, f"fixture landed outside the temp dir: {db}"

    env = {**os.environ, "JOURNAL_DB": db}
    for title, body, when in ENTRIES:
        subprocess.run(
            [cli, "write", "--title", title, "--body", body, "--date", when],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
    return db


@pytest.fixture(autouse=True)
def use_store(store, monkeypatch):
    monkeypatch.setenv("JOURNAL_DB", store)


def titles(result: str) -> list[str]:
    return [e["title"] for e in json.loads(result)]


def test_until_includes_the_whole_end_day():
    got = titles(server.list_entries("2025-01-01", "2025-01-31"))
    assert sorted(got) == ["Evening", "Mid month", "Morning"]


def test_single_day_range():
    assert sorted(titles(server.list_entries("2025-01-31", "2025-01-31"))) == [
        "Evening",
        "Morning",
    ]


def test_recent_entries_one_day_is_today_only():
    assert titles(server.recent_entries(days=1)) == ["Today"]


def test_recent_entries_two_days_reaches_yesterday():
    assert titles(server.recent_entries(days=2)) == ["Today", "Last night"]


def test_limit_caps_results():
    assert len(json.loads(server.list_entries("2025-01-01", limit=2))) == 2


def test_search_is_case_insensitive():
    assert titles(server.search_entries("tokyo")) == ["Mid month"]


def test_show_entry_includes_assets():
    entry_id = json.loads(server.search_entries("Tokyo"))[0]["id"]
    entry = json.loads(server.show_entry(entry_id))
    assert entry["text"] == "Planning the Tokyo trip"
    assert entry["assets"] == []


def test_show_missing_entry_is_an_error():
    assert "no entry with id" in json.loads(server.show_entry(999_999))["error"]


def test_list_journals_counts_entries_in_default_journal():
    journals = json.loads(server.list_journals())
    default = next(j for j in journals if j["default"])
    assert default["entries"] == len(ENTRIES)


def test_stats_and_doctor_are_plain_text():
    assert "entries" in server.journal_stats()
    assert "All good" in server.doctor()
