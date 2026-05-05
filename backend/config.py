from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    kimi_api_key: str
    openai_api_key: str
    wx_app_id: str
    wx_app_secret: str
    jwt_secret: str = "change-me-in-production"
    similarity_threshold: float = 0.85

    class Config:
        env_file = ".env"


settings = Settings()
