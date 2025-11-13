from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # GitHub Configuration
    github_token: str = Field(..., alias="GITHUB_TOKEN")
    github_webhook_secret: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET")
    
    # OpenRouter Configuration
    openrouter_api_key: str = Field(..., alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL"
    )
    openrouter_model: str = Field(
        default="meta-llama/llama-3.1-8b-instruct:free",
        alias="OPENROUTER_MODEL"
    )
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
