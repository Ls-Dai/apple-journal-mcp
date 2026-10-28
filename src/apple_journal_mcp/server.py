"""Read-only MCP server for Apple Journal, backed by journal-cli.

Exposes list / recent / show / search / journals / stats / doctor.
No write commands are wired up, and --live is never passed, so this server
cannot modify Journal or anything that syncs to iCloud.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

mcp = FastMCP(
    "apple-journal",
    instructions=(
        "Read-only access to the user's Apple Journal on this Mac. Entries are "
        "personal: quote only what the task needs. Dates are local time and "
        "list_entries ranges include both end days. Use show_entry for photos, "
        "locations, links and audio transcripts. Nothing here can create, edit "
        "or delete entries. If a call reports a permission error, run doctor."
    ),
)

# Every tool only reads local data, so clients can skip write confirmations.
_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

# Defense in depth: refuse anything that could write, even if a future tool
# forwards user-supplied arguments.
_BLOCKED_FLAGS = {"--live", "--accept-risk", "--force", "--hard"}
_READ_COMMANDS = {"list", "show", "search", "journals", "stats", "doctor"}

_TIMEOUT = 90
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _candidates() -> list[str]:
    # Claude Desktop launches MCP servers with a minimal PATH, so check the
    # usual install locations explicitly. Override with JOURNAL_CLI if needed.
    return [
        os.environ.get("JOURNAL_CLI", ""),
        shutil.which("journal-cli") or "",
        "/opt/homebrew/bin/journal-cli",
        "/usr/local/bin/journal-cli",
        str(Path.home() / ".homebrew/bin/journal-cli"),
        str(Path.home() / ".npm-global/bin/journal-cli"),
        str(Path.home() / ".local/bin/journal-cli"),
    ]


def _cli_path() -> str:
    for p in _candidates():
        if p and os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    raise FileNotFoundError(
        "journal-cli not found. Set JOURNAL_CLI in the MCP config env to its "
        "absolute path (run `which journal-cli` in Terminal)."
    )


def _error(message: str) -> str:
    return json.dumps({"error": message})


def _parse_day(value: str) -> date | None:
    """Parse a strict YYYY-MM-DD date, or return None."""
    if not _DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:  # well-formed but impossible, e.g. 2025-02-30
        return None


def _run(command: str, *args: str, as_json: bool = True) -> str:
    if command not in _READ_COMMANDS:
        return _error(f"command '{command}' is not allowed")
    if _BLOCKED_FLAGS.intersection(args):
        return _error("write flags are not allowed")
    try:
        cmd = [_cli_path(), command, *args]
        if as_json:
            cmd.append("--json")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT)
    except FileNotFoundError as e:
        return _error(str(e))
    except subprocess.TimeoutExpired:
        return _error(f"journal-cli timed out after {_TIMEOUT}s")

    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        hint = ""
        if "disk access" in err.lower() or "permission" in err.lower():
            hint = (
                " Grant Full Disk Access to Claude.app in System Settings > "
                "Privacy & Security, then restart Claude."
            )
        return _error(err + hint)
    return result.stdout


# journal-cli crashes (and can hang) on a negative --limit, and treats any
# argument starting with "--" as an option, so inputs are checked up front.


@mcp.tool(annotations=_READ_ONLY)
def recent_entries(days: int = 7, limit: int = 200) -> str:
    """Entries from the last N days (inclusive of today), with full text, as JSON.

    days=1 is today only; days=7 is today plus the six days before it.
    """
    if days < 1:
        return _error("days must be at least 1")
    if limit < 1:
        return _error("limit must be at least 1")
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    return _run("list", "--since", since, "--full", "--limit", str(limit))


@mcp.tool(annotations=_READ_ONLY)
def list_entries(since: str, until: str = "", limit: int = 200) -> str:
    """Entries in a date range with full text, as JSON.

    Dates are YYYY-MM-DD in local time, and both ends are inclusive.
    """
    start = _parse_day(since)
    if start is None:
        return _error(f"since must be a YYYY-MM-DD date, got {since!r}")
    end = _parse_day(until) if until else None
    if until and end is None:
        return _error(f"until must be a YYYY-MM-DD date, got {until!r}")
    if end and end < start:
        return _error("since must be on or before until")
    if limit < 1:
        return _error("limit must be at least 1")
    args = ["--since", since, "--full", "--limit", str(limit)]
    if until:
        # journal-cli reads a bare date as midnight and drops anything later,
        # which would exclude the whole end day.
        args += ["--until", f"{until} 23:59:59"]
    return _run("list", *args)


@mcp.tool(annotations=_READ_ONLY)
def show_entry(entry_id: int) -> str:
    """One entry with its assets: photos, locations, links, audio transcripts."""
    return _run("show", str(int(entry_id)))


@mcp.tool(annotations=_READ_ONLY)
def search_entries(query: str, limit: int = 50) -> str:
    """Case-insensitive substring search over entry titles and text, as JSON."""
    query = query.strip()
    if not query:
        return _error("query must not be empty")
    if query.startswith("--"):
        return _error("query must not start with '--' (journal-cli reads it as an option)")
    if limit < 1:
        return _error("limit must be at least 1")
    return _run("search", query, "--full", "--limit", str(limit))


@mcp.tool(annotations=_READ_ONLY)
def list_journals() -> str:
    """All journals with entry counts, as JSON."""
    return _run("journals")


@mcp.tool(annotations=_READ_ONLY)
def journal_stats() -> str:
    """Entry, word, attachment and per-year counts (plain text)."""
    return _run("stats", as_json=False)


@mcp.tool(annotations=_READ_ONLY)
def doctor() -> str:
    """Check that journal-cli is installed and can read the Journal store."""
    return _run("doctor", as_json=False)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
