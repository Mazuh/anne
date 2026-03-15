from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from anne.cli.app import app
from anne.config.settings import CONFIG_PATH

runner = CliRunner()


def test_bootstrap_creates_workspace(tmp_path: Path):
    root = tmp_path / "anne-workspace"
    config_path = tmp_path / "config.yaml"

    with patch("anne.cli.bootstrap.typer.prompt", return_value=str(root)):
        with patch("anne.config.settings.CONFIG_PATH", config_path):
            result = runner.invoke(app, ["bootstrap"])

    assert result.exit_code == 0
    assert (root / "data").exists()
    assert (root / "books").exists()
    assert (root / "data" / "anne.db").exists()


def test_bootstrap_blocks_existing_folder(tmp_path: Path):
    root = tmp_path / "anne-workspace"
    root.mkdir()

    with patch("anne.cli.bootstrap.typer.prompt", return_value=str(root)):
        result = runner.invoke(app, ["bootstrap"])

    assert result.exit_code == 1
    assert "already exists" in result.output
