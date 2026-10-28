---
name: add-tool
description: Add or change a tool in the apple-journal MCP server while keeping it read-only. Use when asked to expose another journal-cli capability (for example Recently Deleted entries or bookmarked-only lists), add or change a tool parameter, or change what a tool returns.
---

# Add or change a tool

## 1. Confirm it only reads

Only journal-cli **read** subcommands qualify. Check `journal-cli --help`.

- Allowed to expose: `list`, `show`, `search`, `journals`, `stats`, `doctor`
  (already wired), and `deleted` (Recently Deleted, read-only, not yet exposed).
- Never expose: `write`, `edit`, `delete`, `restore`, `empty`, `sandbox`,
  `repair-locations`, `sync-journals`, `render`, and `export`, which writes
  files to disk.

If someone asks for write access, point out that it was left out on purpose:
a journal should be written by its owner, and this server only reads. Confirm
they really want to change that before touching `_READ_COMMANDS` or
`_BLOCKED_FLAGS`.

## 2. Pin down the CLI's real semantics

Read the subcommand in the CLI checkout (`swift/Sources/journal-cli/`:
`main.swift` lists the `valueFlags` and `boolFlags`, and `ReadCommands.swift`
implements each command). Establish:

- Which flags it accepts. Unknown `--flags` abort the CLI.
- Whether it supports `--json`. If not, call `_run(..., as_json=False)`.
- How values are parsed. Dates become midnight local time; ints go through
  `Int()`, and a negative `--limit` crashes the binary.
- How it reports failure: exit 1 with the reason on stderr (stdout for `doctor`).

Try it against a fixture store (see the `smoke-test` skill), never the
user's real journal.

## 3. Implement in `src/apple_journal_mcp/server.py`

- Add a new subcommand to `_READ_COMMANDS`.
- Decorate with `@mcp.tool(annotations=_READ_ONLY)`.
- The docstring is what the model reads, so state formats, units, defaults and
  whether ranges are inclusive.
- Validate every caller-supplied value before `_run`, and return `_error(...)`
  on bad input. Never raise.
  - Counts that become `--limit` must be `>= 1`.
  - Dates go through `_parse_day` (strict `YYYY-MM-DD`). Inclusive end dates
    need `" 23:59:59"` appended.
  - Free text must not start with `--`.
- Pass each value as its own argv element. Never join into a shell string.

## 4. Tests

- `tests/test_tools.py`: assert the exact argv via `fake_cli.calls`. For each
  rejected input, assert the error text **and** `fake_cli.calls == []`.
- `tests/test_mcp_protocol.py`: add the name to `EXPECTED_TOOLS`.
- `tests/test_integration.py`: add a case when the result depends on CLI
  semantics (date bounds, filtering, ordering).

## 5. Docs

Update the tools table in `README.md`, the tool guide in
`skills/apple-journal/SKILL.md`, and the quirks list in `CLAUDE.md` if you
found new CLI behavior.

## 6. Verify

```sh
uv run pytest
uv run ruff check . && uv run ruff format --check .
JOURNAL_CLI_SRC=~/Development/apple-journal-cli uv run pytest -m integration
```

Then run the `smoke-test` skill.
