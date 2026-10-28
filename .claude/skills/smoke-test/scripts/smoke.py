"""Drive the server over stdio the way Claude Desktop launches it.

Spawns `uv run --directory <repo> apple-journal-mcp` with a minimal PATH (as
Claude Desktop does), lists the tools, and calls each one against the store
given by --db. Exits 1 if any call errors.

    uv run python .claude/skills/smoke-test/scripts/smoke.py --db /tmp/x/moments.sqlite
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[4]


def text_of(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


def failed(result) -> bool:
    if result.isError:
        return True
    try:
        body = json.loads(text_of(result))
    except ValueError:
        return False
    return isinstance(body, dict) and "error" in body


async def smoke(db: str) -> int:
    params = StdioServerParameters(
        command=shutil.which("uv") or "/opt/homebrew/bin/uv",
        args=["run", "--quiet", "--directory", str(REPO), "apple-journal-mcp"],
        env={"PATH": "/usr/bin:/bin", "HOME": os.environ["HOME"], "JOURNAL_DB": db},
    )
    failures = 0
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        for t in tools:
            ro = t.annotations.readOnlyHint if t.annotations else None
            print(f"tool  {t.name:<16} readOnlyHint={ro}")

        async def call(name: str, args: dict) -> str:
            nonlocal failures
            result = await session.call_tool(name, args)
            body = text_of(result)
            status = "FAIL" if failed(result) else "ok"
            failures += status == "FAIL"
            print(f"\n[{status}] {name}({json.dumps(args)})\n{body[:300].rstrip()}")
            return body

        await call("doctor", {})
        await call("journal_stats", {})
        await call("list_journals", {})
        await call("recent_entries", {"days": 7, "limit": 3})
        first = json.loads(await call("list_entries", {"since": "1900-01-01", "limit": 1}))
        if first:
            await call("show_entry", {"entry_id": first[0]["id"]})
            word = (first[0]["title"] or first[0]["text"] or "a").split()[0]
            await call("search_entries", {"query": word, "limit": 3})
        else:
            print("\n(store is empty: skipped show_entry and search_entries)")

    print(f"\n{len(tools)} tools, {failures} failure(s)")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True, help="moments.sqlite to read (use a fixture)")
    args = parser.parse_args()
    sys.exit(asyncio.run(smoke(os.path.abspath(args.db))))


if __name__ == "__main__":
    main()
