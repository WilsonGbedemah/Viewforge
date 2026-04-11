from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Any
from datetime import datetime


# ── Proxy ────────────────────────────────────────────────────────────────────

class ProxyBase(BaseModel):
    label: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"

class ProxyCreate(ProxyBase):
    pass

class ProxyUpdate(BaseModel):
    label: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: Optional[str] = None
    is_active: Optional[bool] = None

class ProxyOut(ProxyBase):
    id: int
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Account ───────────────────────────────────────────────────────────────────

class AccountBase(BaseModel):
    label: str
    email: str
    proxy_id: Optional[int] = None
    watch_style: str = "random"
    notes: Optional[str] = None

class AccountCreate(AccountBase):
    cookie_data: Optional[str] = None
    google_password: Optional[str] = None

class AccountUpdate(BaseModel):
    label: Optional[str] = None
    email: Optional[str] = None
    proxy_id: Optional[int] = None
    cookie_data: Optional[str] = None
    google_password: Optional[str] = None
    watch_style: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class AutoCreateRequest(BaseModel):
    label: str
    proxy_id: Optional[int] = None
    watch_style: str = "random"
    country: str = "us"

class AutoCreateResponse(BaseModel):
    creation_id: str
    message: str

class AccountOut(AccountBase):
    id: int
    status: str
    daily_session_count: int
    last_active: Optional[datetime]
    created_at: datetime
    proxy: Optional[ProxyOut] = None
    model_config = {"from_attributes": True}


# ── Campaign ──────────────────────────────────────────────────────────────────

class CampaignBase(BaseModel):
    name: str
    target_url: str
    target_type: str = "video"
    min_watch_seconds: int = 30
    max_watch_seconds: int = 180
    sessions_per_account_day: int = 2
    total_sessions_target: int = 100
    enable_likes: bool = False
    enable_comments: bool = False
    comment_phrases: List[str] = []
    entry_paths: List[str] = ["home", "search", "suggested"]
    search_keywords: Optional[str] = None
    account_ids: List[int] = []

class CampaignCreate(CampaignBase):
    schedule_start: Optional[datetime] = None
    schedule_end: Optional[datetime] = None

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    target_url: Optional[str] = None
    target_type: Optional[str] = None
    status: Optional[str] = None
    min_watch_seconds: Optional[int] = None
    max_watch_seconds: Optional[int] = None
    sessions_per_account_day: Optional[int] = None
    total_sessions_target: Optional[int] = None
    enable_likes: Optional[bool] = None
    enable_comments: Optional[bool] = None
    comment_phrases: Optional[List[str]] = None
    entry_paths: Optional[List[str]] = None
    search_keywords: Optional[str] = None
    account_ids: Optional[List[int]] = None
    schedule_start: Optional[datetime] = None
    schedule_end: Optional[datetime] = None

class CampaignOut(CampaignBase):
    id: int
    status: str
    completed_sessions: int
    schedule_start: Optional[datetime]
    schedule_end: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Session ───────────────────────────────────────────────────────────────────

class SessionOut(BaseModel):
    id: int
    account_id: int
    campaign_id: Optional[int]
    status: str
    entry_path: Optional[str]
    watch_seconds: Optional[float]
    dwell_seconds: float
    liked: bool
    commented: bool
    warmup_done: bool
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Log ───────────────────────────────────────────────────────────────────────

class LogOut(BaseModel):
    id: int
    session_id: Optional[int]
    account_id: Optional[int]
    campaign_id: Optional[int]
    level: str
    message: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Stats ─────────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_accounts: int
    active_accounts: int
    total_campaigns: int
    running_campaigns: int
    total_sessions: int
    sessions_today: int
    completed_sessions: int
    failed_sessions: int
