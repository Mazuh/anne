# Anne

## About

Pipeline CLI for converting reading notes into short posts for social networks.

This is a personal tool — designed for my own workflow, but open source in case
it's useful as reference or inspiration.

Its name is inspired in [Anne Frank](https://en.wikipedia.org/wiki/Anne_Frank).
Her diary is one of my favorite books, I was very touched by her story
and how she loved to read, study languages, do research and write to the world
or, in any case, just to write for herself.

## Setup

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/):

```sh
uv run anne bootstrap
```

## Usage

Follow the bootstrap hint to set up a shell alias.

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

## License

Under [MIT License](./LICENSE).

Copyright (c) 2026 Marcell "Mazuh" G. C. da Silva.
