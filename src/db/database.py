"""
src/db/database.py

Database engine, session factory, and dependency injection helper.
Works with PostgreSQL running in Docker via the DATABASE_URL in .env
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from src.core.config import settings
from src.db.models import Base


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# pool_pre_ping=True  — tests each connection before using it.
#                       Silently reconnects if Postgres restarted.
# pool_size           — number of persistent connections kept alive.
# max_overflow        — extra connections allowed beyond pool_size under load.
# echo                — set True temporarily to log every SQL query (dev only).
# ---------------------------------------------------------------------------

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DB_ECHO,       # set DB_ECHO=True in .env to debug queries
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
# autocommit=False  — YOU control when to commit (explicit is better)
# autoflush=False   — don't flush to DB automatically before every query
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Init DB  (create all tables that don't exist yet)
# ---------------------------------------------------------------------------
# We also use Alembic for migrations — call this only in dev/testing.
# In production, run: alembic upgrade head
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables defined in Base.metadata if they don't already exist.
    Safe to call on startup — skips tables that are already there.
    """
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created / verified.")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_db_connection() -> bool:
    """
    Ping the database. Returns True if reachable, False otherwise.
    Call this on app startup to fail fast if Postgres is not up.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Dependency — use this in FastAPI route handlers
# ---------------------------------------------------------------------------
# Usage in a route:
#
#   from src.db.database import get_db
#   from sqlalchemy.orm import Session
#   from fastapi import Depends
#
#   @router.get("/something")
#   def my_route(db: Session = Depends(get_db)):
#       results = db.query(MyModel).all()
#       return results
# ---------------------------------------------------------------------------

def get_db():
    """
    FastAPI dependency that yields a database session per request.
    Automatically closes the session when the request is done.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()