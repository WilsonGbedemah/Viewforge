"""
Manages Playwright browser instances.
One persistent browser profile per account — cookies survive across sessions.
"""
import asyncio
import os
import json
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

# Map account_id -> (playwright, context)
_active_contexts: Dict[int, tuple] = {}


def _proxy_config(proxy) -> Optional[dict]:
    """Convert Proxy ORM object to Playwright proxy dict."""
    if not proxy:
        return None
    cfg = {
        "server": f"{proxy.protocol}://{proxy.host}:{proxy.port}",
    }
    if proxy.username:
        cfg["username"] = proxy.username
    if proxy.password:
        cfg["password"] = proxy.password
    return cfg


async def get_context(account) -> BrowserContext:
    """
    Return an existing or new persistent BrowserContext for an account.
    """
    if account.id in _active_contexts:
        _, context = _active_contexts[account.id]
        return context

    pw: Playwright = await async_playwright().start()

    profile_dir = account.profile_dir or f"./profiles/{account.id}"
    os.makedirs(profile_dir, exist_ok=True)

    context = await pw.chromium.launch_persistent_context(
        profile_dir,
        headless=os.getenv("HEADLESS", "true").lower() == "true",
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ],
        ignore_https_errors=True,
        proxy=_proxy_config(account.proxy) if account.proxy else None,
        viewport={"width": 1280, "height": 800},
        user_agent=_random_ua(),
        locale="en-US",
        timezone_id="America/New_York",
    )

    # Inject stealth: hide navigator.webdriver
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    """)

    # Restore cookies if stored
    if account.cookie_data:
        try:
            cookies = json.loads(account.cookie_data)
            await context.add_cookies(cookies)
        except Exception:
            pass

    _active_contexts[account.id] = (pw, context)
    return context


async def close_context(account_id: int):
    """Close and remove the browser context for an account."""
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


async def get_page(account) -> Page:
    """Open a new page in the account's context."""
    context = await get_context(account)
    page = await context.new_page()
    return page


def _random_ua() -> str:
    import random
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]
    return random.choice(uas)
