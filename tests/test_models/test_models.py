from anne.models import (
    Book, Source, Idea, Asset, Post,
    SourceType, IdeaStatus, AssetType, PostStatus,
)


def test_source_type_values():
    assert SourceType.kindle_export_html == "kindle_export_html"
    assert SourceType.essay_md == "essay_md"
    assert SourceType.essay_txt == "essay_txt"
    assert SourceType.essay_html == "essay_html"
    assert SourceType.manual_notes == "manual_notes"


def test_idea_status_values():
    assert IdeaStatus.parsed == "parsed"
    assert IdeaStatus.approved == "approved"
    assert IdeaStatus.rejected == "rejected"
    assert IdeaStatus.reviewed == "reviewed"
    assert IdeaStatus.ready == "ready"


def test_asset_type_values():
    assert AssetType.image == "image"
    assert AssetType.video == "video"


def test_post_status_values():
    assert PostStatus.draft == "draft"
    assert PostStatus.rendered == "rendered"
    assert PostStatus.ready == "ready"
    assert PostStatus.posted == "posted"


def test_book_model():
    book = Book(id=1, slug="test", title="Test", author="Author", created_at="2026-01-01T00:00:00")
    assert book.slug == "test"
    assert book.title == "Test"


def test_source_model():
    source = Source(
        id=1, book_id=1, type=SourceType.essay_md,
        path="sources/essays/test.md", fingerprint="abc123",
        imported_at="2026-01-01T00:00:00",
    )
    assert source.type == SourceType.essay_md


def test_idea_model_defaults():
    idea = Idea(
        id=1, book_id=1, source_id=1, status=IdeaStatus.parsed,
        raw_quote="quote", created_at="2026-01-01", updated_at="2026-01-01",
    )
    assert idea.raw_note is None
    assert idea.tags == "[]"


def test_post_model_defaults():
    post = Post(
        id=1, book_id=1, idea_id=1, status=PostStatus.draft,
        created_at="2026-01-01",
    )
    assert post.asset_id is None
    assert post.publish_count == 0
