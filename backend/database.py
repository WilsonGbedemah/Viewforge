from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./viewforge.db")

# SQLite needs check_same_thread=False; PostgreSQL does not need it and
# will error if it is passed, so we only include it for SQLite.
_is_sqlite = "sqlite" in DB_PATH

engine = create_engine(
    DB_PATH,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # PostgreSQL connection pooling — ignored by SQLite
    pool_size=10 if not _is_sqlite else 5,
    max_overflow=20 if not _is_sqlite else 10,
    pool_pre_ping=True,  # drop stale connections automatically
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
    """Add new columns to existing tables without dropping data.
    Safe for both SQLite (dev/test) and PostgreSQL (production).
    """
    # Column definitions vary slightly between SQLite and PostgreSQL
    if _is_sqlite:
        new_columns = [
            ("accounts",  "watch_style",           "VARCHAR DEFAULT 'random'"),
            ("accounts",  "google_password",        "VARCHAR"),
            ("sessions",  "dwell_seconds",          "FLOAT DEFAULT 0.0"),
            ("campaigns", "search_keywords",        "VARCHAR"),
            ("campaigns", "auto_create_accounts",   "BOOLEAN DEFAULT 0"),
            ("campaigns", "min_accounts",           "INTEGER DEFAULT 1"),
            ("campaigns", "auto_create_country",    "VARCHAR DEFAULT 'us'"),
            ("campaigns", "auto_create_proxy_id",   "INTEGER"),
        ]
    else:
        # PostgreSQL uses standard SQL types
        new_columns = [
            ("accounts",  "watch_style",           "VARCHAR DEFAULT 'random'"),
            ("accounts",  "google_password",        "VARCHAR"),
            ("sessions",  "dwell_seconds",          "FLOAT DEFAULT 0.0"),
            ("campaigns", "search_keywords",        "VARCHAR"),
            ("campaigns", "auto_create_accounts",   "BOOLEAN DEFAULT FALSE"),
            ("campaigns", "min_accounts",           "INTEGER DEFAULT 1"),
            ("campaigns", "auto_create_country",    "VARCHAR DEFAULT 'us'"),
            ("campaigns", "auto_create_proxy_id",   "INTEGER"),
        ]

    with engine.connect() as conn:
        for table, column, col_def in new_columns:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                conn.commit()
            except Exception:
                pass  # Column already exists — safe to ignore


def init_db():
    from models import User, Account, Proxy, Campaign, Session, Log  # noqa
    Base.metadata.create_all(bind=engine)
    _run_migrations()
