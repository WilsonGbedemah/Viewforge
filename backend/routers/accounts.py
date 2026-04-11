import asyncio
import uuid
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import os, json

from database import get_db, SessionLocal
import models, schemas
import broadcast

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

PROFILES_DIR = os.getenv("PROFILES_DIR", "./profiles")

# In-memory creation job store
# { creation_id: {"status": pending|running|success|failed, "account_id": int|None, "error": str|None} }
_creation_jobs: Dict[str, dict] = {}


@router.get("/", response_model=List[schemas.AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(models.Account).order_by(models.Account.id.desc()).all()


@router.post("/", response_model=schemas.AccountOut, status_code=201)
def create_account(data: schemas.AccountCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Account).filter(models.Account.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    profile_dir = os.path.join(PROFILES_DIR, data.email.replace("@", "_at_").replace(".", "_"))
    os.makedirs(profile_dir, exist_ok=True)

    account = models.Account(
        label=data.label,
        email=data.email,
        proxy_id=data.proxy_id,
        notes=data.notes,
        cookie_data=data.cookie_data,
        profile_dir=profile_dir,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}", response_model=schemas.AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db)):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=schemas.AccountOut)
def update_account(account_id: int, data: schemas.AccountUpdate, db: Session = Depends(get_db)):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()


@router.post("/{account_id}/reset-daily", response_model=schemas.AccountOut)
def reset_daily_count(account_id: int, db: Session = Depends(get_db)):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.daily_session_count = 0
    account.status = "idle"
    db.commit()
    db.refresh(account)
    return account


# ── Automated account creation ────────────────────────────────────────────────

@router.post("/auto-create", response_model=schemas.AutoCreateResponse, status_code=202)
async def auto_create_account(data: schemas.AutoCreateRequest):
    """
    Start an automated Google account creation job in the background.
    Progress is streamed to all WebSocket clients as account_creation events.
    Poll GET /auto-create-status/{creation_id} for the final result.
    """
    creation_id = uuid.uuid4().hex[:10]
    _creation_jobs[creation_id] = {
        "status": "pending",
        "account_id": None,
        "email": None,
        "error": None,
    }
    asyncio.create_task(_run_creation(creation_id, data))
    return schemas.AutoCreateResponse(
        creation_id=creation_id,
        message="Account creation started",
    )


@router.get("/auto-create-status/{creation_id}")
def get_creation_status(creation_id: str):
    job = _creation_jobs.get(creation_id)
    if not job:
        raise HTTPException(status_code=404, detail="Creation job not found")
    return job


# ── Background creation task ──────────────────────────────────────────────────

def _msg_to_step(msg: str) -> int:
    m = msg.lower()
    if "generated" in m or "generating" in m:
        return 1
    if "opening" in m or "signup page" in m or "browser" in m:
        return 2
    if any(k in m for k in ("filling", "name", "username", "password", "birthday", "gender")):
        return 3
    if any(k in m for k in ("phone", "sms", "verification", "code", "number")):
        return 4
    if any(k in m for k in ("terms", "accepting", "agree", "skipping", "recovery")):
        return 5
    if any(k in m for k in ("created", "cookies", "saving")):
        return 6
    return 3


def _emit(creation_id: str, msg: str, step: int = None, status: str = "running", **extra):
    broadcast.emit({
        "type":        "account_creation",
        "creation_id": creation_id,
        "step":        step if step is not None else _msg_to_step(msg),
        "total_steps": 6,
        "message":     msg,
        "status":      status,
        **extra,
    })


async def _run_creation(creation_id: str, data: schemas.AutoCreateRequest):
    from automation.account_creator import AccountCreator

    _creation_jobs[creation_id]["status"] = "running"
    _emit(creation_id, "Starting account creation…", step=1)

    try:
        # Resolve proxy (needs its own DB session)
        proxy = None
        if data.proxy_id:
            db = SessionLocal()
            try:
                proxy = db.query(models.Proxy).filter(
                    models.Proxy.id == data.proxy_id
                ).first()
            finally:
                db.close()

        profiles_dir = os.getenv("PROFILES_DIR", "./profiles")

        def log_cb(msg: str, level: str = "info"):
            _emit(creation_id, msg)

        creator = AccountCreator(
            proxy            = proxy,
            profile_base_dir = profiles_dir,
            log_cb           = log_cb,
        )
        result = await creator.create(country=data.country)

        # Persist the new account
        db = SessionLocal()
        try:
            existing = db.query(models.Account).filter(
                models.Account.email == result.email
            ).first()

            if existing:
                existing.cookie_data     = result.cookie_data
                existing.profile_dir     = result.profile_dir
                existing.google_password = result.password
                db.commit()
                account_id = existing.id
            else:
                account = models.Account(
                    label           = data.label,
                    email           = result.email,
                    google_password = result.password,
                    profile_dir     = result.profile_dir,
                    cookie_data     = result.cookie_data,
                    proxy_id        = data.proxy_id,
                    watch_style     = data.watch_style,
                    status          = "idle",
                )
                db.add(account)
                db.commit()
                db.refresh(account)
                account_id = account.id
        finally:
            db.close()

        _creation_jobs[creation_id].update({
            "status":     "success",
            "account_id": account_id,
            "email":      result.email,
        })
        _emit(
            creation_id,
            f"Account created: {result.email}",
            step=6,
            status="success",
            account_id=account_id,
            email=result.email,
        )

    except Exception as exc:
        err = str(exc)
        _creation_jobs[creation_id].update({"status": "failed", "error": err})
        _emit(creation_id, f"Creation failed: {err}", step=None, status="failed")
