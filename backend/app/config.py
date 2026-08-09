from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sales Inbox Task Router"
    environment: str = "development"

    candidate_id: str

    gemini_api_key: str

    database_url: str

    task_api_base_url: str
    task_api_timeout_seconds: float = 10.0

    frontend_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()