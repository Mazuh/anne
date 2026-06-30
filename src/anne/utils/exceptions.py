import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


class AnneError(Exception):
    pass


class DuplicateSourceError(AnneError):
    pass


class BookNotFoundError(AnneError):
    pass


class ConfigError(AnneError):
    pass


class WorkspaceAccessError(AnneError):
    """The workspace database exists but the OS denied access to it.

    On macOS this happens when the terminal lacks permission to a TCC-protected
    folder (e.g. ~/Documents, ~/Desktop, ~/Downloads). SQLite surfaces the
    underlying ``EPERM`` as the cryptic ``authorization denied`` message, so we
    translate it into actionable guidance here.
    """

    def __init__(self, db_path: Path, original: Optional[BaseException] = None) -> None:
        self.db_path = db_path
        self.original = original
        super().__init__(self._build_message(db_path))

    @staticmethod
    def _build_message(db_path: Path) -> str:
        return (
            f"Cannot access the workspace database at:\n  {db_path}\n\n"
            "macOS is blocking access to this folder. This usually happens when\n"
            "the workspace lives in a protected location (e.g. ~/Documents,\n"
            "~/Desktop, or ~/Downloads) and your terminal hasn't been granted\n"
            "access to it.\n\n"
            "To fix:\n"
            "  1. Open System Settings -> Privacy & Security -> Files and Folders\n"
            '  2. Find your terminal app (e.g. Terminal) and enable "Documents\n'
            '     Folder" -- or add it under "Full Disk Access".\n'
            "  3. Quit and reopen the terminal, then run the command again."
        )


# On macOS, a TCC/EPERM folder-access denial surfaces from SQLite as
# SQLITE_AUTH ("authorization denied") — verified by reproducing against a
# real TCC-protected ~/Documents DB, where sqlite3.connect() itself raises
# DatabaseError('authorization denied'). SQLITE_PERM ("access permission
# denied") is included as defensive coverage for other builds/paths.
#
# Deliberately NOT matched: "unable to open database file" (SQLITE_CANTOPEN).
# That message is also produced by a genuinely missing/corrupt DB, so treating
# it as an access denial would misdirect users away from the real problem.
_ACCESS_DENIED_MARKERS = ("authorization denied", "access permission denied")


def access_error_if_denied(
    exc: BaseException, db_path: Path
) -> Optional[WorkspaceAccessError]:
    """Return a ``WorkspaceAccessError`` if *exc* is an OS access denial.

    Returns ``None`` for unrelated errors so callers can re-raise the original.
    """
    if isinstance(exc, PermissionError):
        return WorkspaceAccessError(db_path, exc)
    if isinstance(exc, sqlite3.Error):
        message = str(exc).lower()
        if any(marker in message for marker in _ACCESS_DENIED_MARKERS):
            return WorkspaceAccessError(db_path, exc)
    return None


@contextmanager
def translate_access_errors(db_path: Path) -> Iterator[None]:
    """Translate macOS folder-access denials inside the block.

    Wraps connect and the immediately-following PRAGMA/setup statements: SQLite
    opens the file lazily, so a denial can surface from either. Non-access
    errors propagate unchanged.
    """
    try:
        yield
    except (sqlite3.Error, OSError) as exc:
        raise access_error_if_denied(exc, db_path) or exc
