from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional


class Settings(BaseSettings):
    # Bot
    BOT_TOKEN: str
    ADMINS: str = ""

    # Database
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_NAME: str = "kino_bot"
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Rate limit (seconds between messages)
    RATE_LIMIT: float = 0.5

    # Auto code start number
    AUTO_CODE_START: int = 1

    # Pagination
    MOVIES_PER_PAGE: int = 5
    SEARCH_RESULTS_LIMIT: int = 10

    # Batch import settings
    BATCH_SIZE: int = 20
    BATCH_DELAY: int = 3

    # Mandatory channels (comma separated)
    MANDATORY_CHANNELS: str = ""

    @property
    def admins_list(self) -> List[int]:
        if not self.ADMINS.strip():
            return []
        result = []
        for x in self.ADMINS.split(","):
            x = x.strip()
            if x.isdigit():
                result.append(int(x))
        return result

    @property
    def channels_list(self) -> List[str]:
        if not self.MANDATORY_CHANNELS.strip():
            return []
        return [x.strip() for x in self.MANDATORY_CHANNELS.split(",") if x.strip()]

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


config = Settings()
