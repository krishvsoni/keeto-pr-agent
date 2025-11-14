from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # GitHub Configuration
    GITHUB_TOKEN: str = Field(..., alias="GITHUB_TOKEN")
    GITHUB_WEBHOOK_SECRET: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET")
    
    # OpenRouter Configuration
    OPENROUTER_API_KEY: str = Field(..., alias="OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL"
    )
    OPENROUTER_MODEL: str = Field(
        default="openai/gpt-4o-mini",
        alias="OPENROUTER_MODEL"
    )
    
    # Server Configuration
    HOST: str = Field(default="0.0.0.0", alias="HOST")
    PORT: int = Field(default=8000, alias="PORT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
