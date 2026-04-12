"""
Manages Playwright browser instances.

Cookie-only sessions: instead of storing a full persistent profile per
account (which at 20,000 accounts would consume 1-4 TB of disk), each
session launches a fresh temporary browser context and injects the
account's saved cookies from the database. The context is discarded
after the session ends. Cookies are harvested and saved back to the DB
at the end of every session so the account stays logged in next time.

Persistent profiles are still used during account CREATION (in
account_creator.py) so that the full Google signup flow works correctly.
For all subsequent viewing sessions, this cookie-only approach is used.
"""
import asyncio
import os
import json
import random
import logging
from typing import Optional, Dict
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

logger = logging.getLogger("viewforge.browser")

# Map account_id -> (playwright, context) for contexts still in use
_active_contexts: Dict[int, tuple] = {}


def _proxy_config(proxy) -> Optional[dict]:
    """Convert Proxy ORM object to Playwright proxy dict."""
    if not proxy:
        return None
    cfg = {"server": f"{proxy.protocol}://{proxy.host}:{proxy.port}"}
    if proxy.username:
        cfg["username"] = proxy.username
    if proxy.password:
        cfg["password"] = proxy.password
    return cfg


def _random_ua() -> str:
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]
    return random.choice(uas)


_STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    window.chrome = { runtime: {} };
"""


async def _new_cookie_context(pw: Playwright, account) -> BrowserContext:
    """
    Launch a fresh non-persistent browser context and inject the account's
    saved cookies. Much lighter than a persistent profile — no disk storage
    per account beyond the cookie JSON already in the database.
    """
    browser = await pw.chromium.launch(
        headless=os.getenv("HEADLESS", "true").lower() == "true",
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )

    context = await browser.new_context(
        viewport={"width": random.choice([1280, 1366, 1440, 1920]),
                  "height": random.choice([768, 800, 900, 1080])},
        user_agent=_random_ua(),
        locale="en-US",
        timezone_id="America/New_York",
        proxy=_proxy_config(account.proxy) if account.proxy else None,
        ignore_https_errors=True,
    )

    await context.add_init_script(_STEALTH_SCRIPT)

    # Inject saved cookies so the account is already signed in
    if account.cookie_data:
        try:
            cookies = json.loads(account.cookie_data)
            await context.add_cookies(cookies)
        except Exception as e:
            logger.warning(f"Cookie injection failed for account {account.id}: {e}")

    return context


async def get_page(account) -> Page:
    """
    Open a new page for an account using a cookie-only context.
    Stores the (playwright, context) pair so close_context() can clean up.
    """
    if account.id in _active_contexts:
        # Reuse existing context within the same session
        _, context = _active_contexts[account.id]
        page = await context.new_page()
        return page

    pw: Playwright = await async_playwright().start()
    context = await _new_cookie_context(pw, account)
    _active_contexts[account.id] = (pw, context)

    page = await context.new_page()
    return page


async def close_context(account_id: int):
    """
    Close and discard the browser context for an account.
    Call this at the end of every session to free RAM immediately.
    """
    if account_id in _active_contexts:
        pw, context = _active_contexts.pop(account_id)
        try:
            await context.close()
        except Exception:
            pass
        try:
            await pw.stop()
        except Exception:
            pass


async def harvest_cookies(account_id: int) -> Optional[str]:
    """
    Extract the current cookies from the active context and return them
    as a JSON string to be saved back to the database. Called at the end
    of a successful session so the account stays signed in next time.
    """
    if account_id not in _active_contexts:
        return None
    try:
        _, context = _active_contexts[account_id]
        cookies = await context.cookies()
        return json.dumps(cookies)
    except Exception as e:
        logger.warning(f"Cookie harvest failed for account {account_id}: {e}")
        return None
