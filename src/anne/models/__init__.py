from enum import StrEnum

from pydantic import BaseModel


class SourceType(StrEnum):
    kindle_export_html = "kindle_export_html"
    essay_md = "essay_md"
    essay_txt = "essay_txt"
    essay_html = "essay_html"
    manual_notes = "manual_notes"


class IdeaStatus(StrEnum):
    parsed = "parsed"
    approved = "approved"
    rejected = "rejected"
    reviewed = "reviewed"
    ready = "ready"


class AssetType(StrEnum):
    image = "image"
    video = "video"


class PostStatus(StrEnum):
    draft = "draft"
    rendered = "rendered"
    ready = "ready"
    posted = "posted"


class Book(BaseModel):
    id: int
    slug: str
    title: str
    author: str
    created_at: str


class Source(BaseModel):
    id: int
    book_id: int
    type: SourceType
    path: str
    fingerprint: str
    imported_at: str


class Idea(BaseModel):
    id: int
    book_id: int
    source_id: int
    status: IdeaStatus
    raw_quote: str | None = None
    raw_note: str | None = None
    raw_ref: str | None = None
    rejection_reason: str | None = None
    reviewed_quote: str | None = None
    reviewed_quote_emphasis: str | None = None
    reviewed_comment: str | None = None
    quick_context: str | None = None
    presentation_text: str | None = None
    tags: str = "[]"
    created_at: str
    updated_at: str


class Asset(BaseModel):
    id: int
    book_id: int
    path: str
    type: AssetType
    tags: str = "[]"
    created_at: str


class Post(BaseModel):
    id: int
    book_id: int
    idea_id: int
    asset_id: int | None = None
    status: PostStatus
    caption_text: str | None = None
    output_folder: str | None = None
    media_path: str | None = None
    created_at: str
    ready_at: str | None = None
    posted_at: str | None = None
    publish_count: int = 0
    performance_notes: str | None = None
