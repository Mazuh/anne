# Anne

## About

Pipeline CLI for converting my reading notes into short posts for social networks.

It's not a service meant for general availability,
it's just a personal tool to assist me in creating my non-tech content.

Its name is inspired in [Anne Frank](https://en.wikipedia.org/wiki/Anne_Frank).
Her diary is one of my favorite books, I was very touched by her story
and how she loved to read, study languages, do research and write to the world
or, in any case, just to write for herself.

## Setting up locally

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/):

```sh
# install dependencies
uv sync

# activate the virtual environment
source .venv/bin/activate
```

## Usage

First, initialize the workspace (creates directories and database):

```sh
anne bootstrap
```

A hint will show up to make `anne` globally available as a shell alias. The examples below assume you did it (otherwise stay in the project directory and use `uv run anne`).

Check workspace health anytime with `anne doctor`.

### Books management

Add a book to group pipeline inputs and outputs. The `--author` flag is optional (useful for books with the same title):

```sh
anne books add "O Príncipe" --author "Maquiavel"
anne books list
```

### Importing sources

Import reading notes or essays about a book. Sources can be Kindle HTML exports, essay files, or SSR URLs:

```sh
anne sources import o-principe https://notebook.mazuh.com/p/a-logica-politica-eterna-do-principe
anne sources list o-principe
```

### Idea parsing — status: "parsed"

Parse sources into ideas. Kindle HTML parsing is deterministic; essays use LLM. The book slug is optional (omit to parse all books):

```sh
anne idea-parse o-principe
anne idea-parse
```

### Idea triage — status: "triaged" or "rejected"

Triage parsed ideas using LLM (lenient first pass). Each idea is either kept or rejected:

```sh
anne idea-triage
```

### Idea review — status: "reviewed"

Triaged ideas get refined and translated quotes plus factual context via LLM:

```sh
anne idea-review
```

### Idea caption — status: "ready"

Generate Instagram captions for reviewed ideas using LLM:

```sh
anne idea-caption
```

### Browsing and editing ideas

List, view, and edit ideas without raw SQL:

```sh
anne ideas list o-principe --status triaged --page 1 --per-page 25
anne ideas show 42
anne ideas edit 42 --status reviewed --force
anne ideas edit 42 --reviewed-quote "New text" --tags '["poder"]'
```

### TUI mode

Open a keyboard-driven terminal UI for browsing and editing ideas:

```sh
anne start               # opens dashboard with all books
anne start o-principe    # opens directly into book workspace
```

Keybindings: `j/k` navigate, `a` triage, `x` reject, `u` unreject, `e` edit field, `t` edit tags, `E` open in `$EDITOR`, `f` filter by status, `/` search, `n/p` page, `q` back.

More pipeline commands (asset matching, media generation) are coming in future phases.

## Planning

From Claude using ~/Downloads/anne-technical-proposal.md as source of truth:

- [x] Phase 1 — Foundation + Books + Import
- [x] Phase 2 — Idea parsing (Kindle HTML parser, LLM-assisted essay parsing via Gemini; extract quotes/notes into Idea records)
- [x] Phase 3 — Curation triage (triage/reject ideas via LLM, lenient first pass, configurable chunking)
- [x] Phase 4 — Initial review + Context (LLM-assisted: reviewed_quote, reviewed_comment, quick_context, emphasis markers)
- [x] Phase 5 — Caption generation (Instagram captions, mood/tone tags, CTA link support)
- [ ] Phase 6 — Assets + Matching (asset registration, tag-based suggestion, manual pairing)
- [ ] Phase 7 — Media generation (FFmpeg rendering, text overlay, image/video output, export bundles)
- [x] Phase 8 — TUI (Textual-based terminal UI for the editorial workflow: triage, review, pairing, publishing)
- [ ] Phase 9 — Publication tracking (posted_at, publish_count, performance_notes, repost candidates)

## License

Under [MIT License](./LICENSE).

Copyright (c) 2026 Marcell "Mazuh" G. C. da Silva.
