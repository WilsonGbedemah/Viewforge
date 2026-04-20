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

        # Check if Google is asking for a 2FA / verification challenge
        if await _is_2fa_challenge(page):
            _log(log_cb,
                 f"2-Step Verification is enabled on {account.email} — the engine cannot log in automatically. "
                 "Fix this with ONE of the following options:\n"
                 "  OPTION 1 (easiest): Disable 2-Step Verification — "
                 "sign into that Google account in a browser, go to "
                 "myaccount.google.com/security, click '2-Step Verification', and turn it OFF.\n"
                 "  OPTION 2 (keep 2FA on): Create a Google App Password — "
                 "go to myaccount.google.com/apppasswords, generate a 16-character app password, "
                 "then edit this account in ViewForge and paste that app password into the Password field instead.",
                 "error")
            return False

        # Navigate to YouTube to confirm sign-in
        await page.goto(YOUTUBE_URL, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        ok = await is_signed_in(page)
        if ok:
            _log(log_cb, "Re-login successful")
        else:
            _log(log_cb, "Re-login failed — Google may have blocked the sign-in attempt. "
                         "Check the account at myaccount.google.com for any security alerts.", "warning")
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


async def _is_2fa_challenge(page: Page) -> bool:
    """
    Return True if the current page is a Google 2-Step Verification / challenge screen.
    Covers: authenticator TOTP, SMS pin, phone prompt, and the generic 'Verify it's you' page.
    """
    try:
        # URL-based check — Google challenge pages always contain these path segments
        if any(seg in page.url for seg in ("/challenge/", "/2sv/", "signin/v2/challenge")):
            return True

        # Input fields only present on 2FA screens
        totp = await page.query_selector('input[name="totpPin"], input[name="idvPin"]')
        if totp:
            return True

        # Generic challenge container Google uses for all 2FA types
        challenge_div = await page.query_selector('div[data-challengetype], div[data-challengeid]')
        if challenge_div:
            return True

        # Text that appears on the "Verify it's you" and phone-prompt screens
        body = await page.inner_text("body")
        body_lower = body.lower()
        if any(phrase in body_lower for phrase in (
            "2-step verification",
            "verify it's you",
            "verify its you",
            "check your phone",
            "get a verification code",
            "enter the code",
            "authenticator app",
        )):
            return True

        return False
    except Exception:
        return False


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
