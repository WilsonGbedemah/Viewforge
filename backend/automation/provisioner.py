"""
Account Auto-Provisioner.

Called by the campaign engine when the account pool is too small or
has been exhausted. Creates new accounts concurrently (up to
PROVISIONER_CONCURRENCY at a time, default 5) so large pools are
built quickly without hitting 69-day sequential runtimes.

Unique IP per account:
  If ROTATING_PROXY_HOST + ROTATING_PROXY_PASSWORD are set in .env,
  each new account gets its own sticky-session proxy entry so no two
  accounts share an IP.

SMS mode:
  - If SMS_PROVIDER + SMS_API_KEY are set → fully automatic
  - If not set → logs a warning and returns empty list
"""
import asyncio
import os
import time
import uuid
import logging
from typing import Callable, List, Optional

from sqlalchemy.orm import Session as DBSession

import models
from database import SessionLocal
from automation.account_creator import AccountCreator, AccountCreationError
from automation.sms_providers import get_sms_provider, NO_FREE_PHONES, FallbackSMSProvider

logger = logging.getLogger("viewforge.provisioner")

# How many accounts to create simultaneously
_CONCURRENCY = int(os.getenv("PROVISIONER_CONCURRENCY", "5"))


def _make_sticky_proxy(db: DBSession, label: str) -> Optional[models.Proxy]:
    """
    Create a unique sticky-session Proxy entry for one account using the
    rotating proxy credentials in .env.

    Providers use a session ID embedded in the username to pin a specific
    IP to that session. Format supported:
      username: user-session-{UUID}   (Smartproxy, IPRoyal, etc.)
      username: user_session-{UUID}   (BrightData format — auto-detected)
    """
    host     = os.getenv("ROTATING_PROXY_HOST", "").strip()
    password = os.getenv("ROTATING_PROXY_PASSWORD", "").strip()
    if not host or not password:
        return None

    port      = int(os.getenv("ROTATING_PROXY_PORT", "10000"))
    protocol  = os.getenv("ROTATING_PROXY_PROTOCOL", "http").strip()
    base_user = os.getenv("ROTATING_PROXY_USERNAME", "user").strip()
    session_id = uuid.uuid4().hex

    if "brightdata" in host or "luminati" in host:
        username = f"{base_user}_session-{session_id}"
    else:
        username = f"{base_user}-session-{session_id}"

    proxy = models.Proxy(
        label    = label,
        host     = host,
        port     = port,
        username = username,
        password = password,
        protocol = protocol,
        is_active= True,
    )
    db.add(proxy)
    db.commit()
    db.refresh(proxy)
    return proxy


# How many times to retry when 5sim has no numbers in stock before giving up.
# Each retry waits _NO_STOCK_RETRY_DELAY seconds. Total max wait ≈ 5 min.
_NO_STOCK_RETRIES    = 5
_NO_STOCK_RETRY_DELAY = 60   # seconds between retries


async def _create_one_account(
    index: int,
    campaign: models.Campaign,
    provider,
    rotating_proxy_enabled: bool,
    shared_proxy,
    profiles_dir: str,
    country: str,
    log_cb: Callable,
    semaphore: asyncio.Semaphore,
) -> Optional[int]:
    """
    Create a single account, respecting the concurrency semaphore.
    Returns the new account's DB id, or None on failure.

    Retries automatically when 5sim reports no numbers in stock —
    inventory fluctuates minute-to-minute so a brief wait usually resolves it.
    """
    async with semaphore:
        for attempt in range(1, _NO_STOCK_RETRIES + 2):  # +2 so first attempt is #1
            log_cb(f"Creating account {index + 1}…", "info")
            try:
                acc_db = SessionLocal()
                try:
                    if rotating_proxy_enabled:
                        acc_proxy = _make_sticky_proxy(
                            acc_db,
                            label=f"{campaign.name} — proxy {int(time.time())}-{index}",
                        )
                        proxy_id = acc_proxy.id if acc_proxy else None
                    else:
                        acc_proxy = shared_proxy
                        proxy_id = campaign.auto_create_proxy_id if shared_proxy else None

                    creator = AccountCreator(
                        proxy            = acc_proxy,
                        profile_base_dir = profiles_dir,
                        log_cb           = log_cb,
                        sms_provider     = provider,
                    )
                    result = await creator.create(country=country)

                    existing = acc_db.query(models.Account).filter(
                        models.Account.email == result.email
                    ).first()

                    if existing:
                        existing.cookie_data     = result.cookie_data
                        existing.profile_dir     = result.profile_dir
                        existing.google_password = result.password
                        if proxy_id:
                            existing.proxy_id = proxy_id
                        acc_db.commit()
                        account_id = existing.id
                    else:
                        account = models.Account(
                            label           = f"{campaign.name} — auto {int(time.time())}",
                            email           = result.email,
                            google_password = result.password,
                            profile_dir     = result.profile_dir,
                            cookie_data     = result.cookie_data,
                            proxy_id        = proxy_id,
                            watch_style     = "random",
                            status          = "idle",
                        )
                        acc_db.add(account)
                        acc_db.commit()
                        acc_db.refresh(account)
                        account_id = account.id

                    ip_note = (
                        f" (unique IP: {acc_proxy.username})"
                        if rotating_proxy_enabled and acc_proxy else ""
                    )
                    log_cb(f"Created: {result.email} (id={account_id}){ip_note}", "info")
                    return account_id

                finally:
                    acc_db.close()

            except AccountCreationError as e:
                log_cb(f"Account creation blocked: {e}", "warning")
                return None
            except asyncio.CancelledError:
                raise
            except Exception as e:
                err_str = str(e)
                # No numbers in stock — inventory recovers within minutes so we
                # retry rather than give up immediately.  The FallbackSMSProvider
                # already tried all configured providers before raising this.
                if NO_FREE_PHONES in err_str:
                    if attempt <= _NO_STOCK_RETRIES:
                        log_cb(
                            f"No phone numbers available right now (attempt {attempt}/{_NO_STOCK_RETRIES + 1}). "
                            f"Waiting {_NO_STOCK_RETRY_DELAY}s for inventory to refresh…",
                            "warning",
                        )
                        await asyncio.sleep(_NO_STOCK_RETRY_DELAY)
                        continue
                    else:
                        log_cb(
                            "All SMS providers have no numbers after all retries. "
                            "Check your provider balances and try again in 10–15 minutes.",
                            "error",
                        )
                        return None
                log_cb(f"Account creation failed (slot {index + 1}): {e}", "error")
                await asyncio.sleep(10)
                return None
        return None  # unreachable but satisfies type checker


async def ensure_pool(
    campaign: models.Campaign,
    db: DBSession,
    log_cb: Callable,
) -> List[int]:
    """
    Ensure the campaign has at least `campaign.min_accounts` idle accounts.
    Creates the deficit concurrently and returns the IDs of new accounts.
    Mutates campaign.account_ids and commits to DB.
    """
    current_ids: list = list(campaign.account_ids or [])
    current_count = len(current_ids)
    needed = max(0, campaign.min_accounts - current_count)

    if needed == 0:
        return []

    provider = get_sms_provider()
    if provider is None:
        log_cb(
            f"Auto-provisioning needs {needed} new account(s) but no SMS provider "
            "is configured. Set SMS_PROVIDER and SMS_API_KEY in .env to enable "
            "fully automated account creation. Continuing with existing accounts.",
            "warning",
        )
        return []

    rotating_proxy_enabled = bool(
        os.getenv("ROTATING_PROXY_HOST", "").strip() and
        os.getenv("ROTATING_PROXY_PASSWORD", "").strip()
    )

    shared_proxy = None
    if not rotating_proxy_enabled and campaign.auto_create_proxy_id:
        shared_proxy = db.query(models.Proxy).filter(
            models.Proxy.id == campaign.auto_create_proxy_id
        ).first()

    profiles_dir = os.getenv("PROFILES_DIR", "./profiles")
    country      = campaign.auto_create_country or "us"

    # ── Pre-flight: verify SMS provider(s) are reachable and have balance ──────
    if hasattr(provider, "check_balance"):
        try:
            balance = await provider.check_balance()
            if isinstance(balance, dict):
                # FallbackSMSProvider returns {name: float}
                all_low = True
                for name, bal in balance.items():
                    if isinstance(bal, float):
                        log_cb(f"{name} balance: ${bal:.2f}", "info")
                        if bal >= 0.50:
                            all_low = False
                    else:
                        log_cb(f"{name} balance check failed: {bal}", "warning")
                if all_low:
                    log_cb(
                        "All SMS provider balances are too low (< $0.50). "
                        "Top up at least one provider before creating accounts.",
                        "warning",
                    )
                    return []
            else:
                log_cb(f"SMS provider balance: ${balance:.2f}", "info")
                if balance < 0.50:
                    log_cb(
                        f"SMS provider balance is too low (${balance:.2f}). "
                        "Top up your account before creating accounts.",
                        "warning",
                    )
                    return []
        except Exception as e:
            log_cb(
                f"Cannot reach SMS provider: {e}. "
                "Verify your API key(s) are set correctly in Railway Variables.",
                "error",
            )
            return []

    log_cb(
        f"Pool has {current_count} account(s), minimum is {campaign.min_accounts}. "
        f"Auto-creating {needed} account(s) "
        f"({min(needed, _CONCURRENCY)} at a time)…",
        "info",
    )
    if rotating_proxy_enabled:
        log_cb("Rotating proxy enabled — each account will get a unique IP", "info")

    semaphore = asyncio.Semaphore(_CONCURRENCY)

    tasks = [
        _create_one_account(
            index                 = i,
            campaign              = campaign,
            provider              = provider,
            rotating_proxy_enabled= rotating_proxy_enabled,
            shared_proxy          = shared_proxy,
            profiles_dir          = profiles_dir,
            country               = country,
            log_cb                = log_cb,
            semaphore             = semaphore,
        )
        for i in range(needed)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=False)
    new_ids = [r for r in results if r is not None]

    if new_ids:
        updated_ids = list(set(current_ids + new_ids))
        campaign.account_ids = updated_ids
        db.commit()
        log_cb(
            f"Pool updated: {len(updated_ids)} account(s) assigned to campaign "
            f"({len(new_ids)} newly created).",
            "info",
        )

    return new_ids
