from pathlib import Path

import yaml
from pydantic import BaseModel

CONFIG_PATH = Path.home() / ".config" / "anne" / "config.yaml"


class Settings(BaseModel):
    root_dir: Path = Path.home() / "Documents" / "anne"

    @property
    def db_path(self) -> Path:
        return self.root_dir / "data" / "anne.db"

    @property
    def books_dir(self) -> Path:
        return self.root_dir / "books"


def load_settings() -> Settings:
    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text()) or {}
        return Settings(**raw)
    return Settings()


def save_settings(settings: Settings) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"root_dir": str(settings.root_dir)}
    CONFIG_PATH.write_text(yaml.dump(data, default_flow_style=False))
