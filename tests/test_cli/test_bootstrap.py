from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from anne.cli.app import app
from anne.config.settings import CONFIG_PATH

runner = CliRunner()


def test_bootstrap_creates_workspace(tmp_path: Path):
    root = tmp_path / "anne-workspace"
    config_path = tmp_path / "config.yaml"

    mock_sync = MagicMock(returncode=0)
    prompts = iter([str(root), "fake-key", "", ""])
    with (
        patch("anne.cli.bootstrap.subprocess.run", return_value=mock_sync),
        patch("anne.cli.bootstrap.typer.prompt", side_effect=prompts),
        patch("anne.config.settings.CONFIG_PATH", config_path),
    ):
        result = runner.invoke(app, ["bootstrap"])

    assert result.exit_code == 0
    assert (root / "data").exists()
    assert (root / "books").exists()
    assert (root / "data" / "anne.db").exists()


def test_bootstrap_idempotent(tmp_path: Path):
    root = tmp_path / "anne-workspace"
    config_path = tmp_path / "config.yaml"

    mock_sync = MagicMock(returncode=0)
    prompts = iter([str(root), "", "", ""])
    with (
        patch("anne.cli.bootstrap.subprocess.run", return_value=mock_sync),
        patch("anne.cli.bootstrap.typer.prompt", side_effect=prompts),
        patch("anne.config.settings.CONFIG_PATH", config_path),
    ):
        runner.invoke(app, ["bootstrap"])

    # Run again — should succeed, not error
    prompts = iter([str(root), "fake-key", "", ""])
    with (
        patch("anne.cli.bootstrap.subprocess.run", return_value=mock_sync),
        patch("anne.cli.bootstrap.typer.prompt", side_effect=prompts),
        patch("anne.config.settings.CONFIG_PATH", config_path),
    ):
        result = runner.invoke(app, ["bootstrap"])

    assert result.exit_code == 0
    assert "Bootstrap complete" in result.output
    assert "configured" in result.output
