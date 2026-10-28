"""Each MCP tool: the journal-cli argv it builds and the inputs it refuses."""

from __future__ import annotations

import json

import pytest

from apple_journal_mcp import server


def error_of(result: str) -> str:
    return json.loads(result)["error"]


class TestRecentEntries:
    def test_default_is_seven_days_including_today(self, fake_cli, frozen_today):
        server.recent_entries()
        assert fake_cli.calls == [
            ["list", "--since", "2026-10-22", "--full", "--limit", "200", "--json"]
        ]

    def test_one_day_is_today_only(self, fake_cli, frozen_today):
        server.recent_entries(days=1, limit=5)
        assert fake_cli.calls == [
            ["list", "--since", "2026-10-28", "--full", "--limit", "5", "--json"]
        ]

    def test_crosses_month_and_year_boundaries(self, fake_cli, frozen_today):
        server.recent_entries(days=300)
        assert fake_cli.calls[0][2] == "2026-01-02"

    @pytest.mark.parametrize("days", [0, -3])
    def test_rejects_non_positive_days(self, fake_cli, days):
        assert error_of(server.recent_entries(days=days)) == "days must be at least 1"
        assert fake_cli.calls == []

    @pytest.mark.parametrize("limit", [0, -1])
    def test_rejects_non_positive_limit(self, fake_cli, limit):
        # journal-cli traps on a negative --limit, so it must never see one.
        assert error_of(server.recent_entries(limit=limit)) == "limit must be at least 1"
        assert fake_cli.calls == []


class TestListEntries:
    def test_since_only(self, fake_cli):
        server.list_entries("2025-01-01")
        assert fake_cli.calls == [
            ["list", "--since", "2025-01-01", "--full", "--limit", "200", "--json"]
        ]

    def test_until_is_extended_to_end_of_day(self, fake_cli):
        server.list_entries("2025-01-01", "2025-01-31", limit=10)
        assert fake_cli.calls == [
            [
                "list",
                "--since",
                "2025-01-01",
                "--full",
                "--limit",
                "10",
                "--until",
                "2025-01-31 23:59:59",
                "--json",
            ]
        ]

    def test_single_day_range_is_allowed(self, fake_cli):
        server.list_entries("2025-01-31", "2025-01-31")
        assert len(fake_cli.calls) == 1

    @pytest.mark.parametrize(
        "since",
        [
            "",
            "2025-1-5",
            "2025/01/05",
            "20250105",
            "2025-02-30",
            "yesterday",
            "--live",
            "--db",
            "2025-01-05 10:00",
            "２０２５-01-05",
        ],
    )
    def test_rejects_malformed_since(self, fake_cli, since):
        assert error_of(server.list_entries(since)).startswith("since must be a YYYY-MM-DD date")
        assert fake_cli.calls == []

    @pytest.mark.parametrize("until", ["2025-13-01", "--json", "next week"])
    def test_rejects_malformed_until(self, fake_cli, until):
        assert error_of(server.list_entries("2025-01-01", until)).startswith(
            "until must be a YYYY-MM-DD date"
        )
        assert fake_cli.calls == []

    def test_rejects_reversed_range(self, fake_cli):
        assert error_of(server.list_entries("2025-02-01", "2025-01-31")) == (
            "since must be on or before until"
        )
        assert fake_cli.calls == []

    def test_rejects_non_positive_limit(self, fake_cli):
        assert error_of(server.list_entries("2025-01-01", limit=0)) == "limit must be at least 1"
        assert fake_cli.calls == []


class TestShowEntry:
    def test_builds_show_command(self, fake_cli):
        fake_cli.respond(stdout='{"id": 42, "assets": []}')
        assert json.loads(server.show_entry(42)) == {"id": 42, "assets": []}
        assert fake_cli.calls == [["show", "42", "--json"]]


class TestSearchEntries:
    def test_builds_search_command(self, fake_cli):
        server.search_entries("tokyo")
        assert fake_cli.calls == [["search", "tokyo", "--full", "--limit", "50", "--json"]]

    def test_multi_word_query_stays_one_argument(self, fake_cli):
        server.search_entries("  golden gate  ", limit=3)
        assert fake_cli.calls == [["search", "golden gate", "--full", "--limit", "3", "--json"]]

    def test_single_dash_query_is_allowed(self, fake_cli):
        server.search_entries("-ish")
        assert fake_cli.calls[0][1] == "-ish"

    @pytest.mark.parametrize("query", ["", "   "])
    def test_rejects_empty_query(self, fake_cli, query):
        assert error_of(server.search_entries(query)) == "query must not be empty"
        assert fake_cli.calls == []

    @pytest.mark.parametrize("query", ["--db", "--live", "--foo bar"])
    def test_rejects_option_like_query(self, fake_cli, query):
        assert "must not start with '--'" in error_of(server.search_entries(query))
        assert fake_cli.calls == []

    def test_rejects_non_positive_limit(self, fake_cli):
        assert error_of(server.search_entries("x", limit=-5)) == "limit must be at least 1"
        assert fake_cli.calls == []


class TestPassThroughTools:
    def test_list_journals_requests_json(self, fake_cli):
        server.list_journals()
        assert fake_cli.calls == [["journals", "--json"]]

    def test_journal_stats_is_plain_text(self, fake_cli):
        fake_cli.respond(stdout="entries      3 with text\n")
        assert server.journal_stats() == "entries      3 with text\n"
        assert fake_cli.calls == [["stats"]]

    def test_doctor_is_plain_text(self, fake_cli):
        fake_cli.respond(stdout="Read 3 entries. All good.\n")
        assert "All good" in server.doctor()
        assert fake_cli.calls == [["doctor"]]
