from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "Smart Support Ticket Management System"
    environment: str = "development"
    secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./support.db"
    redis_url: str = "redis://localhost:6379/0"
    access_token_minutes: int = 30
    first_response_high_minutes: int = 240
    resolution_high_minutes: int = 1440
    first_response_critical_minutes: int = 60
    resolution_critical_minutes: int = 480
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = "no-reply@example.test"


settings = Settings()
