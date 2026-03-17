import os
from pathlib import Path

import yaml
from pydantic import BaseModel

CONFIG_PATH = Path.home() / ".config" / "anne" / "config.yaml"


class Settings(BaseModel):
    root_dir: Path = Path.home() / "Documents" / "anne"
    gemini_api_key: str | None = None
    max_llm_input_tokens: int = 7500
    llm_call_interval: int = 10
    triage_chunk_size: int = 25
    content_language: str = "pt-BR"
    review_chunk_size: int = 10
    review_quote_target_length: int = 80
    cta_link: str = ""
    caption_chunk_size: int = 1 # preferred 1 for llm focused quality context

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
    defaults = Settings()
    data: dict = {"root_dir": str(settings.root_dir)}
    if settings.gemini_api_key:
        data["gemini_api_key"] = settings.gemini_api_key
    # Persist any field that differs from its default
    for field_name in (
        "max_llm_input_tokens", "llm_call_interval", "triage_chunk_size",
        "content_language", "review_chunk_size", "review_quote_target_length",
        "cta_link", "caption_chunk_size",
    ):
        value = getattr(settings, field_name)
        if value != getattr(defaults, field_name):
            data[field_name] = value
    CONFIG_PATH.write_text(yaml.dump(data, default_flow_style=False))
