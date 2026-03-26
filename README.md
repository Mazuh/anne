# Anne

## About

Pipeline CLI for converting my reading notes into short posts for social networks.

It's not a service meant for general availability,
it's just a personal tool to assist me in creating my non-tech content.

Its name is inspired in [Anne Frank](https://en.wikipedia.org/wiki/Anne_Frank).
Her diary is one of my favorite books, I was very touched by her story
and how she loved to read, study languages, do research and write to the world
or, in any case, just to write for herself.

## Setup

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync
```

## Usage

Initialize the workspace, then follow the hint to set up a shell alias:

```sh
anne bootstrap
```

The examples below assume the alias is set (otherwise use `uv run anne`). Check workspace health anytime with `anne doctor`.

### Pipeline

```sh
anne books add "O Príncipe" --author "Maquiavel"   # add a book
anne sources import o-principe <file-or-url>        # import reading notes
anne ideas parse [slug]                             # extract ideas from sources
anne ideas triage [slug]                            # LLM triage (keep/reject)
anne ideas review [slug]                            # LLM review (refine quotes, add context)
anne ideas caption [slug]                           # LLM caption for Instagram
```

### Browsing and editing

```sh
anne books list
anne ideas list o-principe --status triaged
anne ideas show 42
anne ideas edit 42 --status reviewed --force
anne ideas edit 42 --reviewed-quote "New text" --tags '["poder"]'
```

### TUI

```sh
anne start               # dashboard with all books
anne start o-principe    # jump into a book workspace
```

Keybindings: `j/k` navigate, `a` triage, `x` reject, `u` unreject, `e` edit field, `t` edit tags, `E` open in `$EDITOR`, `f` filter by status, `/` search, `n/p` page, `q` back.

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
