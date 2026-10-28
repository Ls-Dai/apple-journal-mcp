# apple-journal-mcp

A read-only [MCP](https://modelcontextprotocol.io) server that lets Claude (or
any MCP client) read your Apple Journal entries on macOS: recent entries, date
ranges, search, photos, locations, links, and audio transcripts.

It is a thin wrapper around
[journal-cli](https://github.com/omarshahine/apple-journal-cli), which reads
Journal's local data store through a temporary snapshot, so the live store is
never opened.

## Tools

| Tool | What it does |
|---|---|
| `recent_entries(days=7, limit=200)` | Last N days including today, full text. `days=1` is today only |
| `list_entries(since, until="", limit=200)` | Date range, full text. `YYYY-MM-DD`, local time, both ends inclusive |
| `show_entry(entry_id)` | One entry with photos, locations, links, audio transcripts |
| `search_entries(query, limit=50)` | Case-insensitive substring search over titles and text |
| `list_journals()` | Journals with entry counts |
| `journal_stats()` | Entry, word, attachment counts and a per-year histogram |
| `doctor()` | Checks the install and Full Disk Access |

Entry JSON has `id`, `uuid`, `date` (`YYYY-MM-DD HH:MM:SS`, local time),
`title`, `text`, `chars`, `bookmarked`, `draft` and `synced`. `show_entry`
adds `assets`, where each asset has a `type` (photo, video, livePhoto,
multiPinMap, link, audio, drawing, …), `files[].path`, and type-specific
fields: `places[]` for locations, `url`/`link_title` for links, and
`duration`/`transcript` for audio.

### Read-only by design

A journal is yours to write. This server lets Claude read, find and reflect on
what you wrote, and it never writes for you. The guards below keep it that way:

- The server only runs the read commands `list`, `show`, `search`, `journals`,
  `stats` and `doctor`. It refuses anything else, and refuses `--live`,
  `--accept-risk`, `--force` and `--hard` even on read commands.
- Every tool carries the MCP `readOnlyHint` annotation, so clients can tell
  that it does not modify anything.
- Inputs are validated before journal-cli sees them. Dates must be real
  `YYYY-MM-DD` dates, limits must be positive, and search queries cannot
  start with `--` (journal-cli would read those as options).

## Requirements

- A Mac where Apple Journal is set up, so its entries are in this Mac's local store
- [journal-cli](https://github.com/omarshahine/apple-journal-cli):
  `brew install omarshahine/tap/journal-cli`
- [uv](https://docs.astral.sh/uv/): `brew install uv`

## Install

```sh
git clone https://github.com/Ls-Dai/apple-journal-mcp.git
cd apple-journal-mcp
uv sync
```

Find the absolute paths you'll need for the config:

```sh
which uv journal-cli   # e.g. /opt/homebrew/bin/uv, /opt/homebrew/bin/journal-cli
pwd                    # the repo path
```

Smoke test from Terminal (Terminal needs Full Disk Access for this step):

```sh
uv run python -c "from apple_journal_mcp import server; print(server.doctor())"
```

You should see `Read N entries. All good.`

## Configure

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add
the server under `mcpServers`, using the absolute paths from above:

```json
{
  "mcpServers": {
    "apple-journal": {
      "command": "/opt/homebrew/bin/uv",
      "args": ["run", "--directory", "/Users/you/Development/apple-journal-mcp", "apple-journal-mcp"],
      "env": { "JOURNAL_CLI": "/opt/homebrew/bin/journal-cli" }
    }
  }
}
```

Then:

1. Grant **Full Disk Access** to **Claude.app** in System Settings → Privacy &
   Security → Full Disk Access. macOS checks the app that launched the
   process, so granting it to Terminal is not enough.
2. Quit Claude completely (⌘Q) and reopen it.
3. Ask Claude to run the `doctor` tool.

Claude Desktop launches servers with a minimal `PATH`, which is why the config
uses absolute paths. Without `JOURNAL_CLI`, the server also looks in
`/opt/homebrew/bin`, `/usr/local/bin`, `~/.homebrew/bin`, `~/.npm-global/bin`
and `~/.local/bin`.

### Claude Code

```sh
claude mcp add apple-journal --scope user \
  -e JOURNAL_CLI=/opt/homebrew/bin/journal-cli \
  -- uv run --directory /Users/you/Development/apple-journal-mcp apple-journal-mcp
```

Claude Code runs inside your terminal, so the terminal app (Terminal, iTerm2,
Ghostty, …) needs Full Disk Access. Check with `claude mcp list`, or `/mcp`
inside a session.

### Without cloning

uv can run the server straight from GitHub:

```json
"apple-journal": {
  "command": "/opt/homebrew/bin/uvx",
  "args": ["--from", "git+https://github.com/Ls-Dai/apple-journal-mcp", "apple-journal-mcp"],
  "env": { "JOURNAL_CLI": "/opt/homebrew/bin/journal-cli" }
}
```

### Other MCP clients

This is a standard stdio server. The command is `uv`, the args are
`run --directory /path/to/apple-journal-mcp apple-journal-mcp`, and
`JOURNAL_CLI` is optional. Whatever app launches it needs Full Disk Access.

### Environment variables

| Variable | Purpose |
|---|---|
| `JOURNAL_CLI` | Absolute path to `journal-cli`. Checked before `PATH` and the usual install locations |
| `JOURNAL_DB` | Read a different `moments.sqlite`, such as a sandbox copy from `journal-cli sandbox --dir DIR`. Passed through to journal-cli |

## Agent skill (optional)

[`skills/apple-journal/SKILL.md`](skills/apple-journal/SKILL.md) teaches
Claude how to use these tools well: picking date ranges, searching
effectively, reading assets, and handling journal content with care.

- **Claude Code**: `ln -s "$PWD/skills/apple-journal" ~/.claude/skills/apple-journal`
- **Claude Desktop / claude.ai**: zip the `skills/apple-journal` folder and
  upload it as a custom skill in Claude's settings.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `journal-cli not found` | Set `JOURNAL_CLI` to the output of `which journal-cli` |
| `PERMISSION DENIED` / permission errors | Grant Full Disk Access to the app that launches the server (Claude.app or your terminal), then quit and reopen it |
| Server missing in Claude Desktop | Check `~/Library/Logs/Claude/mcp-server-apple-journal.log`, and that the JSON is valid |
| Fewer entries than expected | Dates are local time. Make sure Journal has synced to this Mac; entries with no title and no text are skipped |
| Interactive testing | `npx @modelcontextprotocol/inspector uv run --directory /path/to/apple-journal-mcp apple-journal-mcp` |

## Development

`main` only changes through pull requests: work on a branch, then open a PR.
Git hooks in `.githooks/` refuse commits on main and pushes to it. Enable them
once per clone:

```sh
git config core.hooksPath .githooks
```

```sh
uv sync                    # installs pytest and ruff too
uv run pytest              # unit tests; never call a real journal-cli
uv run ruff check . && uv run ruff format --check .
```

Integration tests run the real journal-cli against a synthetic store built by
the CLI repo's `tests/make-fixture.sh`. That store contains no personal data,
and your real journal is never opened:

```sh
JOURNAL_CLI_SRC=~/Development/apple-journal-cli uv run pytest -m integration
```

See [CLAUDE.md](CLAUDE.md) for architecture notes and journal-cli quirks.

## Credits

[journal-cli](https://github.com/omarshahine/apple-journal-cli) by Omar
Shahine does the hard part of decoding Journal's private Core Data store.

## License

[MIT](LICENSE)
