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
anne ideas queue 42                                 # visual flag: queued for posting
anne ideas publish 42                               # mark as published
```

### Browsing and editing

```sh
anne books list
anne ideas list o-principe --status triaged
anne ideas show 42
anne ideas edit 42 --status reviewed --force
anne ideas edit 42 --reviewed-quote "New text" --tags '["poder"]'
anne books show o-principe
anne sources list o-principe
anne ideas prompt 42 -p "suggest a shorter version" # custom LLM prompt about an idea
anne ideas curiosity -b o-principe                  # generate a curiosity phrase
```

### TUI

```sh
anne start               # dashboard with all books
anne start o-principe    # jump into a book workspace
```

Keybindings: `j/k` navigate, `a` triage, `x` reject, `u` unreject, `e` edit field, `t` edit tags, `E` open in `$EDITOR`, `f` filter by status, `/` search, `n/p` page, `q` back.

### Database

For pragmatic reasons, this tool uses SQLite.
It's just designed for local usage of a single user.
And there are some simple maintenance scripts:

```sh
anne db info                     # show what's in DB vs filesystem
anne db backup                   # create timestamped backup
anne db backup-restore [path]    # restore from a backup
```

Worth mentioning,
[SQLite does not encourage usage over network](https://sqlite.org/useovernet.html),
but at the same time it feels reasonable to store SQLite and the entire Anne workspace
in a cloud-synced folder (iCloud, Google Drive, etc.), and these folders might
make the file content unavailable (iCloud might erase it locally but
download it again on demand like a user click, to spare local disk usage).
And to address that, we keep journal mode in "delete" (so SQLite deletes the journal after
using it, and reading doesn't depend on long-living files which would be just another sync risk)
a slightly increased busy timeout (so if the database is momentarily locked during sync, the app waits a little bit),
and an eviction check that triggers iCloud to re-download files before reading them.
That said, data corruption is still a risk, so run backups as you wish, especially after many
ideas went through the pipeline, to avoid having to repeat LLM-related costs.

## License

Under [MIT License](./LICENSE).

Copyright (c) 2026 Marcell "Mazuh" G. C. da Silva.
