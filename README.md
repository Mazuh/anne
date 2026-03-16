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

```sh
# initialize workspace (creates directories and database)
uv run anne bootstrap

# a hint will show up to make "anne" command globally available as a shell alias,
# the commands above will assume you did it and restarted the shell
# (otherwise keep in this same directory and using the full "uv run anne")

# check workspace health
anne doctor

# add a book
# (just to group pipeline inputs and outputs, author flag is optional, just for books of same name)
anne books add "O Príncipe" --author "Maquiavel"

# list books
anne books list

# import a source of human thoughts
# (a ssr url for an essay about the book, a file path to kindle highlights/notes etc.)
anne sources import o-principe https://notebook.mazuh.com/p/a-logica-politica-eterna-do-principe

# list sources for a book
anne sources list o-principe

# parse sources into ideas (deterministic for Kindle HTML, LLM-assisted for essays)
# requires Gemini API key (prompted during bootstrap, or set ANNE_GEMINI_API_KEY env var)
anne idea-parse o-principe

# parse all books at once
anne idea-parse

# triage parsed ideas: approve or reject using LLM (lenient first pass)
anne curation-triage o-principe

# triage all books at once
anne curation-triage
```

More pipeline commands (review, media generation) are coming in future phases.

## Planning

From Claude using ~/Downloads/anne-technical-proposal.md as source of truth,
and as optional context for motivations behind it we have /Users/mazuh/Downloads/anne-original-draft.md too.

```
  - ✅ DONE Phase 1 — Foundation + Books + Import
  - ✅ DONE Phase 2 — Idea parsing (Kindle HTML parser, LLM-assisted essay parsing via Gemini; extract quotes/notes into Idea records)
  - ✅ DONE Phase 3 — Curation triage (approve/reject ideas via LLM, lenient first pass, configurable chunking)                                                                                              
  - Phase 4 — Initial review + Context (LLM-assisted: reviewed_quote, reviewed_comment, quick_context, emphasis markers)                                                                     
  - Phase 5 — Curation presentation (caption/presentation text generation, tags)                                                                                                             
  - Phase 6 — Assets + Matching (asset registration, tag-based suggestion, manual pairing)                                                                                                   
  - Phase 7 — Media generation (FFmpeg rendering, text overlay, image/video output, export bundles)                                                                                          
  - Phase 8 — TUI (Textual-based terminal UI for the editorial workflow: triage, review, pairing, publishing)                                                                                
  - Phase 9 — Publication tracking (posted_at, publish_count, performance_notes, repost candidates) 
```

## License

Under [MIT License](./LICENSE).

Copyright (c) 2026 Marcell "Mazuh" G. C. da Silva.
