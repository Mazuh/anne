"""Utilities for handling files on cloud-synced directories (iCloud, etc).

iCloud may "evict" files to save local storage, replacing ``file.txt`` with a
placeholder ``.file.txt.icloud``.  The helpers here detect eviction and trigger
a re-download via macOS ``brctl``.
"""

import platform
import subprocess
import time
from pathlib import Path


def _icloud_placeholder(path: Path) -> Path:
    """Return the iCloud placeholder path for *path*.

    iCloud replaces ``dir/file.txt`` with ``dir/.file.txt.icloud``.
    """
    return path.parent / f".{path.name}.icloud"


def is_icloud_evicted(path: Path) -> bool:
    """Check whether *path* has been evicted by iCloud."""
    return not path.exists() and _icloud_placeholder(path).exists()


def ensure_available(path: Path, *, timeout: int = 30) -> Path:
    """Ensure *path* is available on disk, downloading from iCloud if needed.

    Returns *path* when the file is ready.
    Raises ``FileNotFoundError`` if the file cannot be made available.
    """
    if path.exists():
        return path

    if not is_icloud_evicted(path):
        raise FileNotFoundError(f"File not found: {path}")

    # Trigger iCloud download (macOS only).
    if platform.system() != "Darwin":
        raise FileNotFoundError(
            f"File evicted by iCloud but automatic download is only supported on macOS: {path}"
        )

    subprocess.run(
        ["brctl", "download", str(path)],
        check=False,
        capture_output=True,
    )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return path
        time.sleep(0.5)

    raise FileNotFoundError(
        f"File evicted by iCloud and download timed out after {timeout}s: {path}"
    )


def find_evicted_files(directory: Path) -> list[Path]:
    """Return original paths of all iCloud-evicted files under *directory*."""
    evicted: list[Path] = []
    if not directory.is_dir():
        return evicted
    for placeholder in directory.rglob(".*.icloud"):
        # Reconstruct original name: .file.txt.icloud -> file.txt
        name = placeholder.name
        if name.startswith(".") and name.endswith(".icloud"):
            original_name = name[1:-7]  # strip leading dot and trailing .icloud
            evicted.append(placeholder.parent / original_name)
    return evicted
