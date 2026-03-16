import shutil
from pathlib import Path

from anne.models import SourceType


SOURCE_TYPE_SUBFOLDER = {
    SourceType.kindle_export_html: "kindle",
    SourceType.my_clippings_txt: "kindle",
    SourceType.essay_md: "essays",
    SourceType.essay_txt: "essays",
    SourceType.essay_html: "essays",
    SourceType.manual_notes: "manual",
}


def create_book_dirs(books_dir: Path, slug: str) -> Path:
    book_dir = books_dir / slug
    (book_dir / "sources" / "kindle").mkdir(parents=True, exist_ok=True)
    (book_dir / "sources" / "essays").mkdir(parents=True, exist_ok=True)
    (book_dir / "sources" / "manual").mkdir(parents=True, exist_ok=True)
    (book_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (book_dir / "assets" / "videos").mkdir(parents=True, exist_ok=True)
    (book_dir / "posts").mkdir(parents=True, exist_ok=True)
    return book_dir


def resolve_source_dest(books_dir: Path, slug: str, source_type: SourceType, filename: str) -> Path:
    subfolder = SOURCE_TYPE_SUBFOLDER[source_type]
    return books_dir / slug / "sources" / subfolder / filename


def copy_source_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
