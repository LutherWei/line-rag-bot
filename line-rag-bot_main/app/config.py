from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    line_channel_access_token: str = ""
    line_channel_secret: str = ""
    google_api_key: str = ""
    chromadb_path: str = "./chroma_data"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
