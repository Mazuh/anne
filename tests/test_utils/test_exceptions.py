import sqlite3
from pathlib import Path

import pytest

from anne.utils.exceptions import (
    WorkspaceAccessError,
    access_error_if_denied,
    translate_access_errors,
)

DB_PATH = Path("/Users/someone/Documents/anne/data/anne.db")


def test_authorization_denied_maps_to_workspace_access_error():
    # "authorization denied" is exactly what a real macOS TCC denial produces:
    # reproduced against a TCC-protected ~/Documents DB, sqlite3.connect() raises
    # DatabaseError('authorization denied'). This is not a synthetic-only string.
    exc = sqlite3.OperationalError("authorization denied")
    result = access_error_if_denied(exc, DB_PATH)
    assert isinstance(result, WorkspaceAccessError)
    assert result.db_path == DB_PATH
    assert result.original is exc


def test_access_permission_denied_maps_to_workspace_access_error():
    exc = sqlite3.OperationalError("access permission denied")
    assert isinstance(access_error_if_denied(exc, DB_PATH), WorkspaceAccessError)


def test_unable_to_open_is_not_treated_as_access_denial():
    # SQLITE_CANTOPEN also fires for genuinely missing/corrupt DBs, so it must
    # not be misclassified as a permission problem.
    exc = sqlite3.OperationalError("unable to open database file")
    assert access_error_if_denied(exc, DB_PATH) is None


def test_permission_error_maps_to_workspace_access_error():
    exc = PermissionError("Operation not permitted")
    result = access_error_if_denied(exc, DB_PATH)
    assert isinstance(result, WorkspaceAccessError)
    assert result.original is exc


def test_unrelated_sqlite_error_returns_none():
    exc = sqlite3.OperationalError("no such table: ideas")
    assert access_error_if_denied(exc, DB_PATH) is None


def test_unrelated_exception_returns_none():
    assert access_error_if_denied(ValueError("nope"), DB_PATH) is None


def test_message_is_actionable():
    message = str(WorkspaceAccessError(DB_PATH))
    assert str(DB_PATH) in message
    assert "Privacy & Security" in message
    assert "Files and Folders" in message


def test_translate_access_errors_translates_denial_in_block():
    # Covers denials that surface lazily (e.g. from a PRAGMA after connect),
    # not just from connect() itself.
    with pytest.raises(WorkspaceAccessError):
        with translate_access_errors(DB_PATH):
            raise sqlite3.OperationalError("authorization denied")


def test_translate_access_errors_passes_through_other_errors():
    with pytest.raises(sqlite3.OperationalError):
        with translate_access_errors(DB_PATH):
            raise sqlite3.OperationalError("no such table: ideas")
