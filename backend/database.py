from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./viewforge.db")

engine = create_engine(
    DB_PATH,
    connect_args={"check_same_thread": False} if "sqlite" in DB_PATH else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations():
    """Add new columns to existing tables without dropping data."""
    new_columns = [
        ("accounts", "watch_style", "VARCHAR DEFAULT 'random'"),
        ("accounts", "google_password", "VARCHAR"),
        ("sessions", "dwell_seconds", "FLOAT DEFAULT 0.0"),
        ("campaigns", "search_keywords", "VARCHAR"),
    ]
    with engine.connect() as conn:
        for table, column, col_def in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                conn.commit()
            except Exception:
                pass  # Column already exists


def init_db():
    from models import User, Account, Proxy, Campaign, Session, Log  # noqa
    Base.metadata.create_all(bind=engine)
    _run_migrations()
