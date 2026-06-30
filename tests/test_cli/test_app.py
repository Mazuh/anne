from pathlib import Path

import pytest

import anne.cli.app as app_module
from anne.utils.exceptions import WorkspaceAccessError

DB_PATH = Path("/Users/someone/Documents/anne/data/anne.db")


def test_main_translates_workspace_access_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    def _raise() -> None:
        raise WorkspaceAccessError(DB_PATH)

    monkeypatch.setattr(app_module, "app", _raise)

    with pytest.raises(SystemExit) as excinfo:
        app_module.main()

    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "Privacy & Security" in out
    assert str(DB_PATH) in out


def test_main_passes_through_normal_exit(monkeypatch: pytest.MonkeyPatch):
    def _ok() -> None:
        raise SystemExit(0)

    monkeypatch.setattr(app_module, "app", _ok)

    with pytest.raises(SystemExit) as excinfo:
        app_module.main()
    assert excinfo.value.code == 0
