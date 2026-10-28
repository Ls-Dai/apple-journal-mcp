---
name: smoke-test
description: End-to-end check of the apple-journal MCP server over real stdio against a synthetic Journal store, launched the way Claude Desktop launches it. Use after changing server.py, dependencies, or the entry point, before committing, or when asked to smoke test, try the server, or check that it works in Claude.
---

# Smoke test

This checks the server as a client sees it: spawned via `uv run --directory
<repo> apple-journal-mcp` with Claude Desktop's minimal `PATH`, then every tool
called over MCP stdio.

**Never run it against the user's real journal.** Entries are private, and
the output lands in the transcript. Always use a synthetic store through
`--db`/`JOURNAL_DB`.

## 1. Build a fixture store

The journal-cli repo ships a schema-only fixture builder:

```sh
CLI_SRC=~/Development/apple-journal-cli   # ask the user if it isn't there
FIX=$(mktemp -d /tmp/journal-mcp-fixture.XXXXXX)
DB=$("$CLI_SRC/tests/make-fixture.sh" "$FIX" | tail -1)
```

If there is no checkout, clone https://github.com/omarshahine/apple-journal-cli
into a fresh temp dir and use that.

## 2. Seed a few entries

```sh
export JOURNAL_DB="$DB"
journal-cli write --title "Mid month" --body "Planning the Tokyo trip" --date "2025-01-15 12:00"
journal-cli write --title "Evening" --body "Late dinner" --date "2025-01-31 20:15"
journal-cli write --title "Today" --body "Smoke test entry" --date "$(date +%F) 00:01"
```

These writes reach the fixture only because `JOURNAL_DB` is set. Without it,
journal-cli refuses because `--live` is missing. Never add `--live`.

## 3. Run

```sh
uv run python .claude/skills/smoke-test/scripts/smoke.py --db "$DB"
JOURNAL_CLI_SRC="$CLI_SRC" uv run pytest -m integration
```

Expect 7 tools, all with `readOnlyHint=True`, `0 failure(s)`, and exit code 0,
then all integration tests passing.

## Reading failures

| Symptom | Likely cause |
|---|---|
| Tool list differs | A tool was added or removed; check `EXPECTED_TOOLS` in `tests/test_mcp_protocol.py` too |
| `journal-cli not found` | The binary is outside the `_candidates()` fallbacks; the minimal `PATH` hides it |
| Hangs, then times out | A negative `--limit` reached journal-cli, which traps. Kill stray `journal-cli` processes |
| `unknown option --…` | A user value starting with `--` reached the CLI unvalidated |
| `cannot parse date` | A date bypassed `_parse_day` |

## Clean up

```sh
trash "$FIX"
```
