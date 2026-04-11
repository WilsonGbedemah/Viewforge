"""
ViewForge Automation Engine.
Orchestrates full sessions: warm-up → navigate → watch → log → cooldown.
Handles safety limits, daily caps, schedule windows, proxy sharing, and
time-of-day activity shaping.
"""
import asyncio
import random
import logging
import time
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy.orm import Session as DBSession

from database import SessionLocal
import models
from automation.browser import get_page
from automation.warmup import warmup_session
from automation.watcher import pick_watch_duration, navigate_to_video, watch_video
from automation.relogin import ensure_logged_in

logger = logging.getLogger("viewforge.engine")

# Active campaign task map: campaign_id -> asyncio.Task
_running_tasks: Dict[int, asyncio.Task] = {}

# Broadcast callback for live WebSocket logs
_ws_broadcast = None

# Maximum total active time per session (spec: 5–90 min). Warmup + watch must
# not exceed this — we cap watch_seconds before starting.
_MAX_SESSION_SECONDS = 90 * 60


def set_broadcast_callback(fn):
    global _ws_broadcast
    _ws_broadcast = fn


def _broadcast(msg: str, level: str = "info", campaign_id: int = None, account_id: int = None):
    if _ws_broadcast:
        asyncio.create_task(_ws_broadcast({
            "level": level,
            "message": msg,
            "campaign_id": campaign_id,
            "account_id": account_id,
        }))


def _db_log(db: DBSession, message: str, level: str = "info",
            session_id: int = None, account_id: int = None, campaign_id: int = None):
    log_entry = models.Log(
        session_id=session_id,
        account_id=account_id,
        campaign_id=campaign_id,
        level=level,
        message=message,
    )
    db.add(log_entry)
    db.commit()
    _broadcast(message, level, campaign_id, account_id)


def _time_of_day_multiplier() -> float:
    """
    Return a delay multiplier for inter-session gaps based on local hour.
    Spec: higher activity in evening, lower activity late night.
      6 pm – 11 pm  → peak activity    (1.0×  — baseline)
      9 am –  6 pm  → normal daytime   (1.5×  — moderately less)
      6 am –  9 am  → morning ramp-up  (2.5×  — sparse)
     11 pm –  6 am  → deep night       (5.0×  — near-inactive)
    """
    hour = datetime.now().hour
    if 18 <= hour < 23:
        return 1.0
    elif 9 <= hour < 18:
        return 1.5
    elif 6 <= hour < 9:
        return 2.5
    else:
        return 5.0


def _should_suppress_session() -> bool:
    """
    During deep night hours (midnight – 5 am) randomly suppress ~45% of
    session attempts entirely, producing near-zero traffic in that window
    without a hard blackout (some real users do watch at 2 am).
    """
    hour = datetime.now().hour
    if 0 <= hour < 5:
        return random.random() < 0.45
    if hour == 23 or hour == 5:          # shoulder hours: lighter suppression
        return random.random() < 0.20
    return False


def _is_within_schedule(campaign: models.Campaign) -> bool:
    """Return False if we are outside the campaign's scheduled window."""
    now = datetime.now(timezone.utc)
    if campaign.schedule_start and now < campaign.schedule_start:
        return False
    if campaign.schedule_end and now > campaign.schedule_end:
        return False
    return True


async def start_campaign_engine(campaign_id: int):
    """Launch campaign as a background asyncio task."""
    if campaign_id in _running_tasks:
        return
    task = asyncio.create_task(_run_campaign(campaign_id))
    _running_tasks[campaign_id] = task
    task.add_done_callback(lambda t: _running_tasks.pop(campaign_id, None))


async def stop_campaign_engine(campaign_id: int):
    """Cancel the running campaign task."""
    task = _running_tasks.pop(campaign_id, None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _run_campaign(campaign_id: int):
    """Main campaign loop. Runs until target hit, stopped, schedule ended, or error."""
    db = SessionLocal()
    try:
        campaign = db.query(models.Campaign).filter(models.Campaign.id == campaign_id).first()
        if not campaign:
            return

        _db_log(db, f"Campaign '{campaign.name}' started", "info",
                campaign_id=campaign_id)

        account_ids: list = campaign.account_ids or []
        if not account_ids:
            _db_log(db, "No accounts assigned to this campaign", "warning",
                    campaign_id=campaign_id)
            campaign.status = "stopped"
            db.commit()
            return

        completed = campaign.completed_sessions

        while completed < campaign.total_sessions_target:
            db.refresh(campaign)

            # Stop if status changed externally
            if campaign.status != "running":
                break

            # Schedule window check
            if not _is_within_schedule(campaign):
                if campaign.schedule_start and datetime.now(timezone.utc) < campaign.schedule_start:
                    wait_secs = min(
                        (campaign.schedule_start - datetime.now(timezone.utc)).total_seconds(),
                        300,  # re-check every 5 min max
                    )
                    _db_log(db, f"Waiting for schedule window — sleeping {wait_secs:.0f}s",
                            "debug", campaign_id=campaign_id)
                    await asyncio.sleep(wait_secs)
                    continue
                else:
                    # Past schedule_end
                    _db_log(db, "Schedule window closed — stopping campaign",
                            "info", campaign_id=campaign_id)
                    break

            # Activity wave: suppress sessions during deep-night hours
            if _should_suppress_session():
                suppressed_wait = random.uniform(600, 1800)  # 10–30 min
                _db_log(db, f"Low-activity window — suppressing session for {suppressed_wait/60:.0f} min",
                        "debug", campaign_id=campaign_id)
                await asyncio.sleep(suppressed_wait)
                continue

            # Occasional browse-only safety session (~5% of cycles)
            if random.random() < 0.05:
                account = _pick_account(db, account_ids, campaign)
                if account:
                    await _run_browse_only_session(db, account, campaign)
                # Does not count toward completed — just burns some activity safely

            # Pick a random eligible account
            account = _pick_account(db, account_ids, campaign)
            if not account:
                _db_log(db, "All accounts at daily limit or busy — waiting 30 min",
                        "info", campaign_id=campaign_id)
                await asyncio.sleep(30 * 60)
                continue

            success = await _run_session(db, account, campaign)
            if success:
                completed += 1
                campaign.completed_sessions = completed
                db.commit()
                _db_log(db, f"Session {completed}/{campaign.total_sessions_target} completed",
                        "info", campaign_id=campaign_id, account_id=account.id)

            # Inter-session delay shaped by time of day
            base_delay = random.uniform(120, 600)
            delay = base_delay * _time_of_day_multiplier()
            _db_log(db, f"Waiting {delay:.0f}s before next session",
                    "debug", campaign_id=campaign_id)
            await asyncio.sleep(delay)

        # Campaign finished
        db.refresh(campaign)
        if campaign.status == "running":
            campaign.status = "completed"
            db.commit()
        _db_log(db, f"Campaign '{campaign.name}' finished ({completed} sessions)",
                "info", campaign_id=campaign_id)

    except asyncio.CancelledError:
        db.refresh(campaign)
        campaign.status = "stopped"
        db.commit()
        _db_log(db, f"Campaign '{campaign.name}' was stopped", "warning",
                campaign_id=campaign_id)
        raise
    except Exception as e:
        _db_log(db, f"Campaign engine error: {e}", "error", campaign_id=campaign_id)
        db.query(models.Campaign).filter(models.Campaign.id == campaign_id).update({"status": "stopped"})
        db.commit()
    finally:
        db.close()


async def _run_session(db: DBSession, account: models.Account, campaign: models.Campaign) -> bool:
    """Run a single targeted viewing session for one account."""
    session = models.Session(
        account_id=account.id,
        campaign_id=campaign.id,
        status="running",
        started_at=datetime.now(timezone.utc),
        entry_path=random.choice(campaign.entry_paths or ["home"]),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    def log(msg, level="info"):
        _db_log(db, msg, level, session_id=session.id,
                account_id=account.id, campaign_id=campaign.id)

    page = None
    try:
        account.status = "running"
        db.commit()

        page = await get_page(account)

        # Verify Google session is still valid; re-login if cookies expired
        logged_in = await ensure_logged_in(page, account, log_cb=log)
        if not logged_in:
            raise Exception("Could not verify signed-in state — skipping session")

        # Warm-up (counts toward the 90-min session budget)
        session_start = time.monotonic()
        log("Starting warm-up phase")
        warmup_ok = await warmup_session(page, logger=log)
        session.warmup_done = warmup_ok
        db.commit()

        # Navigate to target
        log(f"Navigating via: {session.entry_path}")
        nav_ok = await navigate_to_video(
            page,
            campaign.target_url,
            session.entry_path,
            search_keywords=campaign.search_keywords,
            logger=log,
        )
        if not nav_ok:
            raise Exception("Navigation failed")

        # Determine watch duration — honour per-account style and session budget
        elapsed_so_far = time.monotonic() - session_start
        budget = max(0, _MAX_SESSION_SECONDS - elapsed_so_far)

        watch_secs = pick_watch_duration(
            campaign.min_watch_seconds,
            campaign.max_watch_seconds,
            style=account.watch_style or "random",
        )
        watch_secs = min(watch_secs, budget)
        session.watch_seconds = watch_secs

        if watch_secs < 2:
            log("Skipping this view (below threshold)")
        else:
            result = await watch_video(page, watch_secs, campaign, logger=log)
            session.watch_seconds = result["watch_seconds"]
            session.dwell_seconds = result.get("dwell_seconds", 0.0)
            session.liked = result["liked"]
            session.commented = result["commented"]

        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)

        account.daily_session_count += 1
        account.last_active = datetime.now(timezone.utc)
        account.status = "cooldown"
        db.commit()

        # Account-level cooldown: 15–45 min
        cooldown = random.uniform(15 * 60, 45 * 60)
        log(f"Account entering cooldown for {cooldown/60:.0f} min")
        await asyncio.sleep(cooldown)

        account.status = "idle"
        db.commit()

        return True

    except asyncio.CancelledError:
        session.status = "failed"
        session.error_message = "Cancelled"
        session.completed_at = datetime.now(timezone.utc)
        account.status = "idle"
        db.commit()
        if page:
            try:
                await page.close()
            except Exception:
                pass
        raise

    except Exception as e:
        session.status = "failed"
        session.error_message = str(e)
        session.completed_at = datetime.now(timezone.utc)
        account.status = "idle"
        db.commit()
        log(f"Session failed: {e}", "error")
        if page:
            try:
                await page.close()
            except Exception:
                pass
        return False


async def _run_browse_only_session(db: DBSession, account: models.Account, campaign: models.Campaign):
    """
    Safety browse: warm-up only, no video targeting.
    Simulates the spec's 'occasional browsing without interaction' safety layer.
    """
    def log(msg, level="info"):
        _db_log(db, msg, level, account_id=account.id, campaign_id=campaign.id)

    page = None
    try:
        account.status = "running"
        db.commit()
        log("Browse-only safety session starting")

        page = await get_page(account)
        await warmup_session(page, logger=log)

        log("Browse-only session completed")
    except Exception as e:
        log(f"Browse-only session error: {e}", "error")
    finally:
        account.status = "idle"
        db.commit()
        if page:
            try:
                await page.close()
            except Exception:
                pass


def _pick_account(db: DBSession, account_ids: list, campaign: models.Campaign):
    """
    Select a random idle account that:
    - is idle
    - hasn't hit the daily session limit
    - does NOT share a proxy with any currently running account in this campaign
      (spec: no proxy sharing between active accounts)
    """
    # Proxy IDs currently in use by running accounts in this campaign pool
    running_accounts = (
        db.query(models.Account)
        .filter(
            models.Account.id.in_(account_ids),
            models.Account.status == "running",
            models.Account.proxy_id.isnot(None),
        )
        .all()
    )
    busy_proxy_ids = {a.proxy_id for a in running_accounts}

    candidates = [
        a for a in (
            db.query(models.Account)
            .filter(
                models.Account.id.in_(account_ids),
                models.Account.status == "idle",
                models.Account.daily_session_count < campaign.sessions_per_account_day,
            )
            .all()
        )
        if a.proxy_id is None or a.proxy_id not in busy_proxy_ids
    ]

    if not candidates:
        return None
    return random.choice(candidates)
