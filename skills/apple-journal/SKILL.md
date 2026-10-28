---
name: apple-journal
description: Read, search and reflect on the user's Apple Journal entries through the apple-journal MCP tools (recent_entries, list_entries, search_entries, show_entry, list_journals, journal_stats, doctor). Use whenever the user asks about their journal, Journal.app, what they wrote on a day or during a trip, wants a weekly or monthly review, recurring themes or moods, or to find an entry, even if they never say "Apple Journal".
---

# Apple Journal

The `apple-journal` MCP server gives **read-only** access to the user's
Apple Journal on their Mac. It cannot create, edit or delete entries. That is
deliberate: the journal is the user's own writing, and your role is to help
them read, find and reflect on it.

## Pick the tool

| The user wants | Call |
|---|---|
| "lately", "this week", "yesterday" | `recent_entries(days=N)`: N counts today, so `days=1` is today and `days=7` is today plus the six days before |
| A specific period: a month, a trip, a year | `list_entries(since, until)`: `YYYY-MM-DD`, local time, both ends inclusive |
| A topic, person or place | `search_entries(query)` |
| Photos, places, links or voice notes of one entry | `show_entry(entry_id)` |
| Which journals exist | `list_journals()` |
| How much they've written, since when | `journal_stats()` |
| Anything returned `{"error": ...}` | `doctor()` |

Turn relative dates into concrete ones before calling. For example, "last
month" in November 2026 is `list_entries("2026-10-01", "2026-10-31")`.

## Search well

`search_entries` is a case-insensitive **substring** match over titles and
text. It has no boolean operators, fuzzy matching or stemming.

- `"run"` also matches "brunch". Prefer distinctive words.
- Search variants separately: `"mom"`, `"mother"`, `"mum"`. Several short
  queries beat one long phrase, which must appear verbatim.
- The default `limit` is 50. Raise it for common words.
- A query cannot start with `--`.

## Read the results

- Entries come newest first, with `id`, `date` (`YYYY-MM-DD HH:MM:SS` local),
  `title` (often empty), `text`, `bookmarked` (starred by the user) and `draft`.
- Entries with no title and no text, such as photo-only ones, are omitted
  from lists and search.
- `show_entry` adds `assets`, each with a `type`: photo, video, livePhoto,
  multiPinMap (location), link, audio, drawing, stateOfMind, workoutRoute, …
  - Locations: `places[]` with `name`, `city`, `lat`, `lon`.
  - Links: `url`, `link_title`.
  - Audio: `duration`, `transcript`. Transcripts are machine speech-to-text,
    so expect errors.
  - Drawings: `drawing_text`, from handwriting recognition.
  - Files: `files[].path` on the user's disk. You can only see a photo if you
    also have a tool that reads local files.

## Large ranges

Each call returns at most `limit` entries (default 200). For a year in review,
start with `journal_stats()` to see the shape, then go month by month rather
than in one huge call. If a result hits the limit exactly, there are probably
more entries.

## Handle it with care

A journal is the most private thing most people write.

- Summarize and paraphrase. Quote briefly, and only when it helps. Do not
  reproduce whole entries unless asked.
- Do not copy entries into other tools or services (notes, email, documents,
  web searches) unless the user asks for that specifically.
- Say plainly when a period has no entries. Never fill gaps with guesses.
- Reflect, don't diagnose. Mirror what the user wrote; leave conclusions about
  their health or relationships to them.

## When something fails

- `journal-cli not found`: set `JOURNAL_CLI` in the server's MCP config to
  the output of `which journal-cli`.
- Permission errors: grant Full Disk Access to the app that launches the
  server (Claude.app, or the terminal for Claude Code), then quit and reopen it.
  `doctor()` confirms the fix.
- Requests to write or edit entries: explain that the server is read-only on
  purpose, so entries stay in the user's own words. Offer to help them reflect
  instead, with questions or with what they wrote about it before, and leave
  the writing to them in Journal.app.
