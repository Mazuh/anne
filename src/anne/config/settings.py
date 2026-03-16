import os
from pathlib import Path

import yaml
from pydantic import BaseModel

CONFIG_PATH = Path.home() / ".config" / "anne" / "config.yaml"


class Settings(BaseModel):
    root_dir: Path = Path.home() / "Documents" / "anne"
    gemini_api_key: str | None = None

    @property
    def db_path(self) -> Path:
        return self.root_dir / "data" / "anne.db"

    @property
    def books_dir(self) -> Path:
        return self.root_dir / "books"


def load_settings() -> Settings:
    if CONFIG_PATH.exists():
        raw = yaml.safe_load(CONFIG_PATH.read_text()) or {}
        settings = Settings(**raw)
    else:
        settings = Settings()
    env_key = os.environ.get("ANNE_GEMINI_API_KEY")
    if env_key:
        settings.gemini_api_key = env_key
    return settings


def save_settings(settings: Settings) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"root_dir": str(settings.root_dir)}
    if settings.gemini_api_key:
        data["gemini_api_key"] = settings.gemini_api_key
    CONFIG_PATH.write_text(yaml.dump(data, default_flow_style=False))
