"""The journal-cli wrapper: binary discovery, the read-only guard, error mapping."""

from __future__ import annotations

import json
import subprocess

import pytest

from apple_journal_mcp import server


def error_of(result: str) -> str:
    return json.loads(result)["error"]


class TestCliPath:
    def test_journal_cli_env_is_checked_first(self, monkeypatch):
        monkeypatch.setenv("JOURNAL_CLI", "/custom/journal-cli")
        assert server._candidates()[0] == "/custom/journal-cli"

    def test_returns_first_executable_candidate(self, tmp_path, monkeypatch):
        not_exec = tmp_path / "plain-file"
        not_exec.write_text("")
        exe = tmp_path / "journal-cli"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(0o755)
        missing = tmp_path / "missing"
        candidates = ["", str(missing), str(not_exec), str(tmp_path), str(exe)]
        monkeypatch.setattr(server, "_candidates", lambda: candidates)
        assert server._cli_path() == str(exe)

    def test_raises_with_setup_hint_when_nothing_found(self, monkeypatch):
        monkeypatch.setattr(server, "_candidates", lambda: ["", "/nonexistent/journal-cli"])
        with pytest.raises(FileNotFoundError, match="JOURNAL_CLI"):
            server._cli_path()

    def test_run_reports_missing_binary_as_error(self, monkeypatch):
        monkeypatch.setattr(server, "_candidates", lambda: [])
        assert "journal-cli not found" in error_of(server._run("list"))


class TestReadOnlyGuard:
    @pytest.mark.parametrize(
        "command",
        [
            "write",
            "edit",
            "delete",
            "restore",
            "empty",
            "sandbox",
            "export",
            "repair-locations",
            "sync-journals",
            "render",
            "deleted",
        ],
    )
    def test_rejects_commands_outside_allowlist(self, fake_cli, command):
        assert "not allowed" in error_of(server._run(command))
        assert fake_cli.calls == []

    @pytest.mark.parametrize("flag", sorted(server._BLOCKED_FLAGS))
    def test_rejects_write_flags_even_on_read_commands(self, fake_cli, flag):
        assert error_of(server._run("list", flag)) == "write flags are not allowed"
        assert fake_cli.calls == []

    def test_allowlist_is_exactly_the_read_commands(self):
        assert server._READ_COMMANDS == {
            "list",
            "show",
            "search",
            "journals",
            "stats",
            "doctor",
        }


class TestRun:
    def test_appends_json_flag_by_default(self, fake_cli):
        server._run("journals")
        assert fake_cli.calls == [["journals", "--json"]]

    def test_omits_json_flag_for_plain_text_commands(self, fake_cli):
        server._run("stats", as_json=False)
        assert fake_cli.calls == [["stats"]]

    def test_returns_stdout_unchanged_on_success(self, fake_cli):
        payload = '[{"id": 1, "text": "héllo\\nworld"}]\n'
        fake_cli.respond(stdout=payload)
        assert server._run("list") == payload

    def test_nonzero_exit_returns_stderr(self, fake_cli):
        fake_cli.respond(stderr="journal-cli: no entry with id 9\n", exit_code=1)
        assert error_of(server._run("show", "9")) == "journal-cli: no entry with id 9"

    def test_nonzero_exit_falls_back_to_stdout(self, fake_cli):
        # doctor reports problems on stdout and exits 1.
        fake_cli.respond(stdout="store    /x/moments.sqlite\n         NOT FOUND\n", exit_code=1)
        assert "NOT FOUND" in error_of(server._run("doctor", as_json=False))

    @pytest.mark.parametrize(
        "message",
        ["PERMISSION DENIED - grant Full Disk Access", "Operation not permitted: permission"],
    )
    def test_permission_errors_get_full_disk_access_hint(self, fake_cli, message):
        fake_cli.respond(stdout=message, exit_code=1)
        err = error_of(server._run("doctor", as_json=False))
        assert err.startswith(message)
        assert "Privacy & Security" in err

    def test_other_errors_get_no_hint(self, fake_cli):
        fake_cli.respond(stderr="journal-cli: cannot parse date 'x'", exit_code=1)
        assert "Privacy & Security" not in error_of(server._run("list"))

    def test_timeout_is_reported(self, fake_cli, monkeypatch):
        def hang(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

        monkeypatch.setattr(subprocess, "run", hang)
        assert "timed out" in error_of(server._run("list"))

    def test_arguments_are_passed_as_separate_argv_items(self, fake_cli):
        server._run("search", "golden gate; rm -rf ~", "--limit", "5")
        assert fake_cli.calls == [["search", "golden gate; rm -rf ~", "--limit", "5", "--json"]]
