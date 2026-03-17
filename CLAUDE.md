# Anne

Local-first Python CLI pipeline for turning book reading notes into Instagram-ready posts.

## Tech stack

- Python 3.14, SQLite, Typer (CLI), Rich (output), Pydantic (models), PyYAML (config)
- FFmpeg for media rendering (future phase)
- pytest for tests

## Project structure

```
src/anne/
  cli/          # Typer commands (bootstrap, doctor, books, sources, ideas)
  models/       # Pydantic DTOs + StrEnums (Book, Source, Idea, Asset, Post)
  services/     # Business logic (books, sources, ideas, parsers, llm, filesystem)
  db/           # SQLite connection, schema.sql, migrations
  config/       # Pydantic Settings, YAML config loader
  utils/        # slugify, exceptions
tests/          # pytest tests (test_cli, test_db, test_models, test_services)
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
uv run anne idea-parse [slug]                # parse sources into ideas
uv run anne idea-triage [slug]               # triage parsed ideas (triage/reject)
uv run anne idea-review [slug]              # review triaged ideas (refine quotes, add context)
uv run anne idea-caption [slug]             # generate Instagram captions for reviewed ideas
uv run anne ideas list [slug]               # list ideas (--status, --page, --per-page)
uv run anne ideas show <id>                 # show full idea details
uv run anne ideas edit <id>                 # edit idea fields (--status, --raw-quote, --tags, etc.)
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
- WAL mode enabled, foreign keys enforced
- `schema_version` table tracks migrations
- All tables: books, sources, ideas, assets, posts

## Testing

- Real SQLite databases (no mocks for DB)
- Temp directories via pytest `tmp_path`
- `CliRunner` for CLI integration tests
- Fixtures in `tests/conftest.py`

## Pipeline stages (idea status flow)

parsed → triaged → reviewed → ready
       ↘ rejected (reversible)

## Field naming

Follows the technical proposal at `~/Downloads/anne-technical-proposal.md`.
