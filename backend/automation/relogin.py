"""
Auto re-login module.

Before each automation session, the engine calls ensure_logged_in()
to verify the account is still signed into Google/YouTube.
If the session has expired, this module uses the stored google_password
to re-authenticate silently in the background.
"""
import asyncio
import random
from typing import Callable, Optional

from playwright.async_api import Page

from automation.interaction import move_mouse_to

YOUTUBE_URL    = "https://www.youtube.com"
GOOGLE_SIGNIN  = "https://accounts.google.com/signin"


# ── Public API ────────────────────────────────────────────────────────────────

async def ensure_logged_in(
    page: Page,
    account,
    log_cb: Optional[Callable] = None,
) -> bool:
    """
    Check login state; re-login if the session has expired.
    Returns True when the account is (or becomes) signed in.
    """
    if await is_signed_in(page):
        return True

    _log(log_cb, f"Session expired for {account.email} — attempting re-login…")
    return await relogin(page, account, log_cb)


async def is_signed_in(page: Page) -> bool:
    """
    Navigate to YouTube and check whether a Google account is signed in.
    Returns True if the account avatar button is visible.
    """
    try:
        if "youtube.com" not in page.url:
            await page.goto(YOUTUBE_URL, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(random.uniform(1.5, 2.5))

        # A visible "Sign in" button means we are NOT logged in
        sign_in = await page.query_selector(
            'a[href*="ServiceLogin"], '
            'ytd-button-renderer:has-text("Sign in"), '
            'a.yt-spec-button-shape-next:has-text("Sign in")'
        )
        if sign_in:
            return False

        # Account avatar means we ARE logged in
        avatar = await page.query_selector(
            "button#avatar-btn, "
            "yt-img-shadow#avatar, "
            "ytd-masthead #avatar-btn"
        )
        return avatar is not None

    except Exception:
        return False


async def relogin(
    page: Page,
    account,
    log_cb: Optional[Callable] = None,
) -> bool:
    """
    Sign into Google using the credentials stored on the Account model.
    Returns True on success, False on failure.
    """
    if not getattr(account, "google_password", None):
        _log(log_cb,
             f"No password stored for {account.email} — cannot log in. "
             "Go to Accounts → click the Edit (pencil) icon on this account → enter the Google password → save. "
             "Then restart the campaign.",
             "warning")
        return False

    _log(log_cb, f"Re-logging in as {account.email}…")

    try:
        await page.goto(GOOGLE_SIGNIN, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # Fill email
        await _type_field(page, 'input[type="email"], input[name="identifier"]', account.email)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await _click_next(page)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # Fill password
        pass_sel = 'input[type="password"], input[name="Passwd"]'
        try:
            await page.wait_for_selector(pass_sel, timeout=8000)
        except Exception:
            _log(log_cb, "Password field not found during re-login", "error")
            return False

        await _type_field(page, pass_sel, account.google_password)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await _click_next(page)
        await asyncio.sleep(random.uniform(2.5, 4.0))

        # Navigate to YouTube to confirm
        await page.goto(YOUTUBE_URL, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        ok = await is_signed_in(page)
        if ok:
            _log(log_cb, "Re-login successful")
        else:
            _log(log_cb, "Re-login may have failed — signed-in state unclear", "warning")
        return ok

    except Exception as exc:
        _log(log_cb, f"Re-login error: {exc}", "error")
        return False


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log(cb, msg: str, level: str = "info"):
    if cb:
        cb(msg, level)


async def _type_field(page: Page, selector: str, text: str):
    try:
        el = await page.wait_for_selector(selector, timeout=5000)
        if not el:
            return
        box = await el.bounding_box()
        if box:
            tx = box["x"] + box["width"]  * 0.5
            ty = box["y"] + box["height"] * 0.5
            await move_mouse_to(page, tx, ty)
            await asyncio.sleep(random.uniform(0.1, 0.2))
            await page.mouse.click(tx, ty)
            await asyncio.sleep(random.uniform(0.1, 0.2))
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")
        for char in text:
            await page.keyboard.type(char, delay=random.uniform(60, 160))
    except Exception:
        pass


async def _click_next(page: Page):
    for sel in [
        "#identifierNext button",
        "#passwordNext button",
        'button:has-text("Next")',
        'div[jsname="0UZ4fc"] button',
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                return
        except Exception:
            continue
    await page.keyboard.press("Enter")
