from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://localhost:5432/everest"
    test_database_url: str = "postgresql+psycopg://localhost:5432/everest_test"
    jwt_secret: str = "dev-only-secret-set-JWT_SECRET-in-env-file"
    jwt_ttl_hours: int = 12
    cookie_secure: bool = False
    upload_dir: str = "../../data/uploads"
    demo_data: bool = False
    llm_key_secret: str = ""


settings = Settings()
