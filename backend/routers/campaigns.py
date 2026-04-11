from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models, schemas
from automation.engine import start_campaign_engine, stop_campaign_engine

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("/", response_model=List[schemas.CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return db.query(models.Campaign).order_by(models.Campaign.id.desc()).all()


@router.post("/", response_model=schemas.CampaignOut, status_code=201)
def create_campaign(data: schemas.CampaignCreate, db: Session = Depends(get_db)):
    if not data.entry_paths:
        data.entry_paths = ["home", "search", "suggested"]
    campaign = models.Campaign(**data.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=schemas.CampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}", response_model=schemas.CampaignOut)
def update_campaign(campaign_id: int, data: schemas.CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status == "running":
        raise HTTPException(status_code=400, detail="Campaign already running")

    campaign.status = "running"
    db.commit()

    # Fire-and-forget: engine runs in background
    await start_campaign_engine(campaign_id)
    return {"message": f"Campaign {campaign_id} started"}


@router.post("/{campaign_id}/stop")
async def stop_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign.status = "stopped"
    db.commit()

    await stop_campaign_engine(campaign_id)
    return {"message": f"Campaign {campaign_id} stopped"}


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()


@router.get("/{campaign_id}/sessions", response_model=List[schemas.SessionOut])
def campaign_sessions(campaign_id: int, limit: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(models.Session)
        .filter(models.Session.campaign_id == campaign_id)
        .order_by(models.Session.id.desc())
        .limit(limit)
        .all()
    )
