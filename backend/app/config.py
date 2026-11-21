import os
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    LLM_API_KEYS: str = "mock-key-1,mock-key-2"
    DATABASE_URL: str = "sqlite:///./app.db"
    ALLOWED_ORIGINS: str = "*"
    ENABLE_FAILURE_SIMULATION: bool = False
    DEFAULT_MODEL: str = "gemini/gemini-2.0-flash"
    DEFAULT_SYSTEM_PROMPT: str = "You are a helpful and concise AI assistant."

    @property
    def key_pool(self) -> List[tuple[str, str]]:
        """Returns list of (key_id, api_key) e.g. [('key_1', 'val1'), ('key_2', 'val2')]"""
        keys = [k.strip() for k in self.LLM_API_KEYS.split(",") if k.strip()]
        return [(f"key_{i+1}", k) for i, k in enumerate(keys)]

    @property
    def cors_origins(self) -> List[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def sqlite_path(self) -> str:
        """Parses path from sqlite:///... URL"""
        url = self.DATABASE_URL
        if url.startswith("sqlite:////"):
            return "/" + url[len("sqlite:////"):]
        elif url.startswith("sqlite:///"):
            return url[len("sqlite:///"):]
        return "./app.db"


settings = Settings()
