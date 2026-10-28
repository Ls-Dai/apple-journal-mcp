# CLAUDE.md

Read-only MCP server for Apple Journal. All logic is in
`src/apple_journal_mcp/server.py`: FastMCP tools build an argv, and `_run()`
shells out to [journal-cli](https://github.com/omarshahine/apple-journal-cli),
which reads Journal's Core Data store through a temp snapshot.

## Commands

```sh
git config core.hooksPath .githooks        # once per clone: enables the main-branch guard
uv sync                                    # env incl. dev deps (pytest, ruff)
uv run pytest                              # unit tests (fake journal-cli, no real store)
JOURNAL_CLI_SRC=~/Development/apple-journal-cli uv run pytest -m integration
uv run ruff check . && uv run ruff format --check .
uv run python .claude/skills/smoke-test/scripts/smoke.py --db <fixture>/moments.sqlite
```

The integration tests and the smoke test need a synthetic store; see the
`smoke-test` skill. To add a tool, follow the `add-tool` skill.

## Workflow: main changes only through pull requests

Every change to `main`, code or docs, goes through a branch and a PR:

1. Before editing, switch off main: `git switch -c <type>/<short-name>`
   (`feat/`, `fix/`, `docs/`, `test/`, `chore/`). If you already edited on
   main, run the same command; uncommitted changes come along.
2. Commit on the branch. Run the unit tests and ruff before pushing.
3. Push the branch with `git push -u origin <branch>`, then open a PR with `gh pr create`.
4. Merge on GitHub. Afterwards: `git switch main && git pull --ff-only`.

`.githooks/` enforces this locally: `pre-commit` refuses commits on main, and
`pre-push` refuses any push to main, including local merges. **Never bypass
them with `--no-verify`.** If a hook fires, move the work to a branch. Do not
commit, push or merge without the user asking you to.

## Invariants

- **Read-only is the purpose, not just a safety measure.** A journal should be
  written by its owner; this server exists to read and reflect. Do not add
  write tools on the grounds that journal-cli can write safely (sandbox,
  `--dry-run`, backups).
- **Enforced twice.** `_READ_COMMANDS` is an allowlist of
  journal-cli subcommands and `_BLOCKED_FLAGS` rejects write flags. Never add
  `write`, `edit`, `delete`, `restore`, `empty`, `sandbox`, `export` (writes
  files) or `render`, and never pass `--live`. `tests/test_mcp_protocol.py`
  pins the exact tool set, so a new tool fails it until listed on purpose.
- **Every tool gets `annotations=_READ_ONLY`** (`readOnlyHint=True`).
- **Tools return strings.** Success passes journal-cli's stdout through
  unchanged (JSON, except `stats` and `doctor`, which have no `--json`).
  Failures are `{"error": "..."}` built with `_error()`, never raised.
- **Never run against the real journal while developing.** Use a fixture via
  `JOURNAL_DB`. Journal entries are private; do not print real ones into a
  transcript, test, or fixture.
- `mcp` is pinned `>=1.21.1,<2`. 2.x renames FastMCP to MCPServer, and older
  releases fail to import against current pydantic.

## journal-cli behavior this code works around

Confirmed against the Swift source (`swift/Sources/journal-cli/`):

- `--until D` parses a bare date as **midnight at the start of D** and drops
  anything later, so `list_entries` sends `--until "D 23:59:59"`.
  `--since D` is also midnight, which is already inclusive.
- A **negative `--limit` traps the binary** (Swift `prefix(-1)`). It exits 133
  and can hang in crash reporting, so tools reject `limit < 1`.
- Any argument starting with `--` is read as an option: unknown ones abort,
  and `--db` is scanned across the **whole** argv and consumes the next
  argument. Search queries starting with `--` are rejected, and dates are
  validated as strict `YYYY-MM-DD`.
- Exit code 1 means an error, with the message on stderr prefixed
  `journal-cli:`. `doctor` reports problems on **stdout**, which is why
  `_run()` falls back to stdout for the error text.
- `$JOURNAL_DB` (inherited by the subprocess) points every command at another
  store. Sandbox stores skip the `--live` gate and the "Journal.app is
  running" check.

## Tests

- `tests/conftest.py` `fake_cli` writes an executable stand-in for
  journal-cli that logs its argv and replies via `FAKE_STDOUT`, `FAKE_STDERR`
  and `FAKE_EXIT`. It also pins `_candidates()` so a real journal-cli on the
  machine is never reached. Assert on `fake_cli.calls`.
- `frozen_today` fixes `date.today()` at 2026-10-28.
- For rejected input, assert both the error text and `fake_cli.calls == []`.
- `tests/test_githooks.py` runs the hooks with real commits and pushes against
  a throwaway repo and bare remote, with the global git config disabled.

## Docs to keep in sync

When a tool's name, parameters or semantics change, update the tools table in
`README.md`, `EXPECTED_TOOLS` in `tests/test_mcp_protocol.py`, and
`skills/apple-journal/SKILL.md`.
