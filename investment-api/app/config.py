from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5434/investment"
    api_key: str = "dev-api-key"
    tinkoff_token: str = ""
    secret_key: str = "change-me-in-production"
    debug: bool = True

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
