from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    # This allows loading variables from a .env file
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()