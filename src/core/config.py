from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Postgres ──────────────────────────────────────────────────────────
    # Full DSN, e.g.:
    #   postgresql://logistics_user:yourpassword@localhost:5432/logistics_db
    DATABASE_URL: str

    # Set to True in .env during development to print every SQL query
    DB_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── App ───────────────────────────────────────────────────────────────
    APP_ENV: str = "development"   # development | production
    SECRET_KEY: str = "change-me-in-production"
    
    # ── Matrix builder ─────────────────────────────────────────────────────
    # Returned for unreachable pairs — large enough that OR-Tools avoids them
    # but not so large it breaks the solver's integer arithmetic
    PENALTY_SEC: int = 7 * 3600          # 7 hours

    # Redis TTL for cached pairs — 24 hours
    CACHE_TTL_SEC: int = 86_400

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()