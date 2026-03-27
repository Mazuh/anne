# Anne

Local-first Python CLI pipeline for turning book reading notes into Instagram-ready posts.

## Platform

- macOS only (TUI clipboard features use `pbcopy`)

## Tech stack

- Python 3.14, SQLite, Typer (CLI), Rich (output), Pydantic (models), PyYAML (config)
- Textual (TUI framework for `anne start`)
- FFmpeg for media rendering (future phase)
- pytest, pytest-asyncio for tests

## Project structure

```
src/anne/
  cli/          # Typer commands (bootstrap, doctor, books, sources, ideas, review)
  tui/          # Textual TUI (AnneApp, screens, widgets, modals)
  models/       # Pydantic DTOs + StrEnums (Book, Source, Idea, Asset, Post)
  services/     # Business logic (books, sources, ideas, parsers, llm, filesystem)
  db/           # SQLite connection, schema.sql, migrations
  config/       # Pydantic Settings, YAML config loader
  utils/        # slugify, exceptions
tests/          # pytest tests (test_cli, test_db, test_models, test_services, test_tui)
```

## Commands

```sh
uv sync                                      # install dependencies
uv run pytest                                 # run tests
uv run anne bootstrap                         # initialize workspace
uv run anne doctor                            # check workspace health
uv run anne books add "Title" --author "Foo"  # add a book
uv run anne books list                        # list books
uv run anne books show <slug>                 # show book details
uv run anne sources import <slug> <file>      # import source file
uv run anne sources list <slug>               # list sources for a book
uv run anne ideas parse [slug]               # parse sources into ideas
uv run anne ideas triage [slug]              # triage parsed ideas (triage/reject)
uv run anne ideas review [slug]             # review triaged ideas (refine quotes, add context)
uv run anne ideas caption [slug]            # generate Instagram captions for reviewed ideas
uv run anne ideas list [slug]               # list ideas (--status, --page, --per-page)
uv run anne ideas show <id>                 # show full idea details
uv run anne ideas edit <id>                 # edit idea fields (--status, --raw-quote, --tags, etc.)
uv run anne db info                        # show what's in DB vs filesystem
uv run anne db backup                      # create timestamped DB backup
uv run anne db backup-restore [path]       # restore DB from backup
uv run anne start                          # open TUI dashboard
uv run anne start <slug>                   # open TUI directly into book workspace
```

## Conventions

- Type hints everywhere
- Pydantic for validation, no ORM
- Parameterized SQL queries (never string interpolation)
- ISO 8601 dates stored as TEXT in SQLite
- StrEnum for status/type fields
- Services layer between CLI and DB

## Database

- Schema: `src/anne/db/schema.sql`
- DELETE journal mode (not WAL), foreign keys enforced
- `schema_version` table tracks migrations
- All tables: books, sources, ideas, assets, posts
- The workspace directory may be stored on a cloud-synced folder (iCloud, Google Drive, OneDrive). Source files may not be immediately available (cloud eviction) and SQLite may face corruption risks. DELETE journal mode is used instead of WAL for this reason. See `src/anne/utils/icloud.py` for eviction handling and `anne db backup` for backup/restore support.

## Testing

- Real SQLite databases (no mocks for DB)
- Temp directories via pytest `tmp_path`
- `CliRunner` for CLI integration tests
- Textual `run_test()` + `pilot` for TUI tests (async, pytest-asyncio)
- Fixtures in `tests/conftest.py` and `tests/test_tui/conftest.py`

## Pipeline stages (idea status flow)

parsed → triaged → reviewed → ready
       ↘ rejected (reversible)

## Field naming

Follows the technical proposal at `~/Downloads/anne-technical-proposal.md`.
