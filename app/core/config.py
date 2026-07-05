from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/innovation_engine")
    OPENAI_API_KEY: str = Field(default="")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small")
    ANTHROPIC_API_KEY: str = Field(default="")
    SYNTHESIS_MODEL: str = Field(default="claude-3-5-sonnet-20241022")
    COGNEE_METADATA_DIR: str = Field(default=".tmp/cognee_meta")
    COGNEE_MAX_MEMORY_MB: int = Field(default=50)
    SIMULATION_MODE: bool = False
    
    # We will load from .env in root
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

