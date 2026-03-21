from pathlib import Path
from unittest.mock import patch

from anne.utils.icloud import (
    ensure_available,
    find_evicted_files,
    is_icloud_evicted,
)

import pytest


def test_is_icloud_evicted_false_when_file_exists(tmp_path: Path):
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    assert is_icloud_evicted(f) is False


def test_is_icloud_evicted_false_when_nothing_exists(tmp_path: Path):
    f = tmp_path / "notes.txt"
    assert is_icloud_evicted(f) is False


def test_is_icloud_evicted_true_when_placeholder_exists(tmp_path: Path):
    placeholder = tmp_path / ".notes.txt.icloud"
    placeholder.write_bytes(b"")
    f = tmp_path / "notes.txt"
    assert is_icloud_evicted(f) is True


def test_ensure_available_file_exists(tmp_path: Path):
    f = tmp_path / "notes.txt"
    f.write_text("hello")
    assert ensure_available(f) == f


def test_ensure_available_not_found(tmp_path: Path):
    f = tmp_path / "notes.txt"
    with pytest.raises(FileNotFoundError, match="File not found"):
        ensure_available(f)


def test_ensure_available_evicted_downloads(tmp_path: Path):
    placeholder = tmp_path / ".notes.txt.icloud"
    placeholder.write_bytes(b"")
    f = tmp_path / "notes.txt"

    # Simulate brctl download: after subprocess call, create the real file
    def fake_brctl(*args, **kwargs):
        f.write_text("downloaded content")
        placeholder.unlink()

    with patch("anne.utils.icloud.subprocess.run", side_effect=fake_brctl):
        with patch("anne.utils.icloud.platform.system", return_value="Darwin"):
            result = ensure_available(f, timeout=5)

    assert result == f
    assert f.read_text() == "downloaded content"


def test_ensure_available_evicted_non_darwin(tmp_path: Path):
    placeholder = tmp_path / ".notes.txt.icloud"
    placeholder.write_bytes(b"")
    f = tmp_path / "notes.txt"

    with patch("anne.utils.icloud.platform.system", return_value="Linux"):
        with pytest.raises(FileNotFoundError, match="only supported on macOS"):
            ensure_available(f)


def test_ensure_available_evicted_timeout(tmp_path: Path):
    placeholder = tmp_path / ".notes.txt.icloud"
    placeholder.write_bytes(b"")
    f = tmp_path / "notes.txt"

    with patch("anne.utils.icloud.subprocess.run"):
        with patch("anne.utils.icloud.platform.system", return_value="Darwin"):
            with pytest.raises(FileNotFoundError, match="timed out"):
                ensure_available(f, timeout=1)


def test_find_evicted_files(tmp_path: Path):
    # Regular file — not evicted
    (tmp_path / "real.txt").write_text("ok")
    # Evicted files
    (tmp_path / ".evicted1.txt.icloud").write_bytes(b"")
    sub = tmp_path / "subdir"
    sub.mkdir()
    (sub / ".evicted2.md.icloud").write_bytes(b"")

    evicted = find_evicted_files(tmp_path)
    names = sorted(p.name for p in evicted)
    assert names == ["evicted1.txt", "evicted2.md"]


def test_find_evicted_files_empty_dir(tmp_path: Path):
    assert find_evicted_files(tmp_path) == []


def test_find_evicted_files_nonexistent_dir(tmp_path: Path):
    assert find_evicted_files(tmp_path / "nope") == []
