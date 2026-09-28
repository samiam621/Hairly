from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    gemini_api_key: str
    max_image_mb: int = 10

    # env_ignore_empty: a blank `MAX_IMAGE_MB=` falls back to the default instead of failing to parse
    model_config = SettingsConfigDict(env_file=Path(__file__).parents[2] / ".env", extra="ignore", env_ignore_empty=True)


settings = Settings()
