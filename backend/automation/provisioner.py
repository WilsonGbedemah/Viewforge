"""
Account Auto-Provisioner.

Called by the campaign engine when the account pool is too small or
has been exhausted. Runs Google account creation in the background,
waits for completion, then returns the new account IDs so the engine
can immediately add them to the campaign and continue.

Flow:
  engine detects pool_size < campaign.min_accounts
    → provisioner.ensure_pool(campaign, db, log)
      → creates (min_accounts - current_count) new accounts
      → each creation runs AccountCreator fully automated (no UI)
      → newly created accounts are saved to DB and added to campaign
      → returns list of new account IDs

SMS mode:
  - If SMS_PROVIDER + SMS_API_KEY are set → fully automatic, no human input
  - If not set → creation raises AccountCreationError and the engine logs
    a clear "configure SMS provider" warning; campaign continues with
    existing accounts rather than crashing
"""
import asyncio
import os
import time
import logging
from typing import Callable, List, Optional

from sqlalchemy.orm import Session as DBSession

import models
from database import SessionLocal
from automation.account_creator import AccountCreator, AccountCreationError
from automation.sms_providers import get_sms_provider

logger = logging.getLogger("viewforge.provisioner")


async def ensure_pool(
    campaign: models.Campaign,
    db: DBSession,
    log_cb: Callable,
) -> List[int]:
    """
    Ensure the campaign has at least `campaign.min_accounts` idle accounts.
    Creates the deficit and returns the IDs of any newly created accounts.
    Mutates campaign.account_ids and commits to DB.
    """
    current_ids: list = list(campaign.account_ids or [])
    current_count = len(current_ids)
    needed = max(0, campaign.min_accounts - current_count)

    if needed == 0:
        return []

    # Check SMS provider availability before attempting
    provider = get_sms_provider()
    if provider is None:
        log_cb(
            f"Auto-provisioning needs {needed} new account(s) but no SMS provider "
            "is configured. Set SMS_PROVIDER and SMS_API_KEY in .env to enable "
            "fully automated account creation. Continuing with existing accounts.",
            "warning",
        )
        return []

    log_cb(
        f"Pool has {current_count} account(s), minimum is {campaign.min_accounts}. "
        f"Auto-creating {needed} new account(s)…",
        "info",
    )

    # Resolve proxy for new accounts
    proxy = None
    if campaign.auto_create_proxy_id:
        proxy = db.query(models.Proxy).filter(
            models.Proxy.id == campaign.auto_create_proxy_id
        ).first()

    profiles_dir = os.getenv("PROFILES_DIR", "./profiles")
    country      = campaign.auto_create_country or "us"
    new_ids: List[int] = []

    for i in range(needed):
        log_cb(f"Creating account {i + 1}/{needed}…", "info")
        try:
            creator = AccountCreator(
                proxy            = proxy,
                profile_base_dir = profiles_dir,
                log_cb           = log_cb,
                sms_provider     = provider,
            )
            result = await creator.create(country=country)

            # Persist account in a fresh session to avoid stale state issues
            acc_db = SessionLocal()
            try:
                existing = acc_db.query(models.Account).filter(
                    models.Account.email == result.email
                ).first()

                if existing:
                    existing.cookie_data     = result.cookie_data
                    existing.profile_dir     = result.profile_dir
                    existing.google_password = result.password
                    acc_db.commit()
                    account_id = existing.id
                else:
                    account = models.Account(
                        label           = f"{campaign.name} — auto {int(time.time())}",
                        email           = result.email,
                        google_password = result.password,
                        profile_dir     = result.profile_dir,
                        cookie_data     = result.cookie_data,
                        proxy_id        = campaign.auto_create_proxy_id,
                        watch_style     = "random",
                        status          = "idle",
                    )
                    acc_db.add(account)
                    acc_db.commit()
                    acc_db.refresh(account)
                    account_id = account.id
            finally:
                acc_db.close()

            new_ids.append(account_id)
            log_cb(f"Auto-created account: {result.email} (id={account_id})", "info")

        except AccountCreationError as e:
            log_cb(f"Account creation blocked: {e}", "warning")
            break  # typically a config issue — don't retry in a loop
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log_cb(f"Account creation failed (attempt {i+1}): {e}", "error")
            # Small back-off before next attempt
            await asyncio.sleep(10)

    # Attach new accounts to campaign
    if new_ids:
        updated_ids = list(set(current_ids + new_ids))
        campaign.account_ids = updated_ids
        db.commit()
        log_cb(
            f"Pool updated: {len(updated_ids)} account(s) assigned to campaign.",
            "info",
        )

    return new_ids
