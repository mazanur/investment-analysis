from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/investment"
    api_key: str = "dev-api-key"
    debug: bool = True

    model_config = {"env_prefix": "", "env_file": ".env"}


settings = Settings()
