from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    line_channel_access_token: str = ""
    line_channel_secret: str = ""
    google_api_key: str = ""
    chromadb_path: str = "./chroma_data"
    allowed_group_ids: str = ""

    @property
    def allowed_group_id_list(self) -> list[str]:
        """Parse comma-separated group IDs into a list."""
        if not self.allowed_group_ids:
            return []
        return [gid.strip() for gid in self.allowed_group_ids.split(",") if gid.strip()]

    @property
    def cleaned_database_url(self) -> str:
        # asyncpg does not support sslmode in connection string
        if "sslmode=" in self.database_url:
            import urllib.parse as urlparse
            url = urlparse.urlparse(self.database_url)
            query = urlparse.parse_qs(url.query)
            query.pop('sslmode', None)
            query.pop('channel_binding', None) # asyncpg also doesn't like this
            new_query = urlparse.urlencode(query, doseq=True)
            url = url._replace(query=new_query)
            return urlparse.urlunparse(url)
        return self.database_url

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
