CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id),
    type TEXT NOT NULL,
    path TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    imported_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(book_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id),
    source_id INTEGER NOT NULL REFERENCES sources(id),
    status TEXT NOT NULL DEFAULT 'parsed',
    raw_quote TEXT,
    raw_note TEXT,
    raw_ref TEXT,
    rejection_reason TEXT,
    reviewed_quote TEXT,
    reviewed_comment TEXT,
    quick_context TEXT,
    presentation_text TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id),
    path TEXT NOT NULL,
    type TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id),
    idea_id INTEGER NOT NULL REFERENCES ideas(id),
    asset_id INTEGER REFERENCES assets(id),
    status TEXT NOT NULL DEFAULT 'draft',
    caption_text TEXT,
    output_folder TEXT,
    media_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    ready_at TEXT,
    posted_at TEXT,
    publish_count INTEGER NOT NULL DEFAULT 0,
    performance_notes TEXT
);
