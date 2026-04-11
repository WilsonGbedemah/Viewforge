from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


def now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=now_utc)


class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    protocol = Column(String, default="http")  # http, socks5
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_utc)

    accounts = relationship("Account", back_populates="proxy")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    profile_dir = Column(String, nullable=True)           # path to Playwright profile
    cookie_data = Column(Text, nullable=True)             # JSON cookie string
    proxy_id = Column(Integer, ForeignKey("proxies.id"), nullable=True)
    status = Column(String, default="idle")               # idle, running, cooldown, error
    watch_style = Column(String, default="random")        # random, short, medium, long
    daily_session_count = Column(Integer, default=0)
    last_active = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now_utc)

    proxy = relationship("Proxy", back_populates="accounts")
    sessions = relationship("Session", back_populates="account")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    target_url = Column(String, nullable=False)           # YouTube URL (video, channel, playlist)
    target_type = Column(String, default="video")         # video, short, livestream, channel, playlist
    status = Column(String, default="paused")             # paused, running, completed, stopped
    min_watch_seconds = Column(Integer, default=30)
    max_watch_seconds = Column(Integer, default=180)
    sessions_per_account_day = Column(Integer, default=2)
    total_sessions_target = Column(Integer, default=100)
    completed_sessions = Column(Integer, default=0)
    enable_likes = Column(Boolean, default=False)
    enable_comments = Column(Boolean, default=False)
    comment_phrases = Column(JSON, default=list)          # list of safe phrases
    entry_paths = Column(JSON, default=list)              # home, search, suggested, channel, playlist
    search_keywords = Column(String, nullable=True)       # keywords used for search entry path
    account_ids = Column(JSON, default=list)              # assigned account IDs
    schedule_start = Column(DateTime, nullable=True)
    schedule_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc, onupdate=now_utc)

    sessions = relationship("Session", back_populates="campaign")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    status = Column(String, default="pending")            # pending, running, completed, failed
    entry_path = Column(String, nullable=True)
    watch_seconds = Column(Float, nullable=True)
    dwell_seconds = Column(Float, default=0.0)
    liked = Column(Boolean, default=False)
    commented = Column(Boolean, default=False)
    warmup_done = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now_utc)

    account = relationship("Account", back_populates="sessions")
    campaign = relationship("Campaign", back_populates="sessions")
    logs = relationship("Log", back_populates="session")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    account_id = Column(Integer, nullable=True)
    campaign_id = Column(Integer, nullable=True)
    level = Column(String, default="info")                # info, warning, error, debug
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now_utc)

    session = relationship("Session", back_populates="logs")
