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
anne books add "O Príncipe" --author "Maquiavel"

# list books
anne books list

# import a source file
anne sources import o-principe ~/path/to/highlights.html

# list sources for a book
anne sources list o-principe
```

More pipeline commands (idea parsing, curation, review, media generation) are coming in future phases.

## License

Under [MIT License](./LICENSE).

Copyright (c) 2026 Marcell "Mazuh" G. C. da Silva.
