from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import csv, io
from fastapi.responses import StreamingResponse

from database import get_db
import models, schemas

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/", response_model=List[schemas.LogOut])
def list_logs(
    limit: int = Query(100, le=500),
    campaign_id: Optional[int] = None,
    account_id: Optional[int] = None,
    level: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Log)
    if campaign_id:
        q = q.filter(models.Log.campaign_id == campaign_id)
    if account_id:
        q = q.filter(models.Log.account_id == account_id)
    if level:
        q = q.filter(models.Log.level == level)
    return q.order_by(models.Log.id.desc()).limit(limit).all()


@router.get("/export")
def export_logs(
    campaign_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Log)
    if campaign_id:
        q = q.filter(models.Log.campaign_id == campaign_id)
    logs = q.order_by(models.Log.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "session_id", "account_id", "campaign_id", "level", "message", "created_at"])
    for log in logs:
        writer.writerow([log.id, log.session_id, log.account_id, log.campaign_id, log.level, log.message, log.created_at])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=viewforge_logs.csv"},
    )


@router.delete("/", status_code=204)
def clear_logs(campaign_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(models.Log)
    if campaign_id:
        q = q.filter(models.Log.campaign_id == campaign_id)
    q.delete(synchronize_session=False)
    db.commit()
