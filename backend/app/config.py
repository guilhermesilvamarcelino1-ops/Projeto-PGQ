from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    anthropic_api_key: str
    voyage_api_key: str
    openai_api_key: str | None = None  # usado só para transcrição de áudio (Whisper)
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24
    claude_model: str = "claude-sonnet-5"
    embedding_model: str = "voyage-3"
    retrieval_top_k: int = 6
    storage_dir: str = "./storage"


settings = Settings()
