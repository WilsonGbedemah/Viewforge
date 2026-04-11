from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import os, json

from database import get_db
import models, schemas

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

PROFILES_DIR = os.getenv("PROFILES_DIR", "./profiles")


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
