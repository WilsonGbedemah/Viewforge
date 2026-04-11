from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, date
from typing import Optional
import csv, io
from fastapi.responses import StreamingResponse

from database import get_db
import models, schemas

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/", response_model=schemas.DashboardStats)
def get_stats(db: Session = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    return schemas.DashboardStats(
        total_accounts=db.query(models.Account).count(),
        active_accounts=db.query(models.Account).filter(models.Account.status == "running").count(),
        total_campaigns=db.query(models.Campaign).count(),
        running_campaigns=db.query(models.Campaign).filter(models.Campaign.status == "running").count(),
        total_sessions=db.query(models.Session).count(),
        sessions_today=db.query(models.Session).filter(models.Session.created_at >= today_start).count(),
        completed_sessions=db.query(models.Session).filter(models.Session.status == "completed").count(),
        failed_sessions=db.query(models.Session).filter(models.Session.status == "failed").count(),
    )


@router.get("/export")
def export_sessions(
    campaign_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Export session statistics as CSV."""
    q = db.query(models.Session)
    if campaign_id:
        q = q.filter(models.Session.campaign_id == campaign_id)
    sessions = q.order_by(models.Session.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "account_id", "campaign_id", "status",
        "entry_path", "watch_seconds", "dwell_seconds",
        "liked", "commented", "warmup_done",
        "error_message", "started_at", "completed_at",
    ])
    for s in sessions:
        writer.writerow([
            s.id, s.account_id, s.campaign_id, s.status,
            s.entry_path, s.watch_seconds, getattr(s, "dwell_seconds", 0),
            s.liked, s.commented, s.warmup_done,
            s.error_message, s.started_at, s.completed_at,
        ])
    output.seek(0)

    filename = f"sessions_{campaign_id or 'all'}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
