"""
Auto re-login module.

Before each automation session, the engine calls ensure_logged_in()
to verify the account is still signed into Google/YouTube.
If the session has expired, this module uses the stored google_password
to re-authenticate silently in the background.

Google's login flow has multiple screens that can appear between entering
the email and reaching the password field (passkey prompts, account pickers,
"Choose how to sign in" pages). This module handles all of them.
"""
import asyncio
import random
from typing import Callable, Optional

from playwright.async_api import Page

from automation.interaction import move_mouse_to

YOUTUBE_URL   = "https://www.youtube.com"
GOOGLE_SIGNIN = "https://accounts.google.com/signin"


# ── Public API ────────────────────────────────────────────────────────────────

async def ensure_logged_in(
    page: Page,
    account,
    log_cb: Optional[Callable] = None,
) -> bool:
    if await is_signed_in(page):
        return True
    _log(log_cb, f"Session expired for {account.email} — attempting re-login…")
    return await relogin(page, account, log_cb)


async def is_signed_in(page: Page) -> bool:
    try:
        if "youtube.com" not in page.url:
            await page.goto(YOUTUBE_URL, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(random.uniform(1.5, 2.5))

        sign_in = await page.query_selector(
            'a[href*="ServiceLogin"], '
            'ytd-button-renderer:has-text("Sign in"), '
            'a.yt-spec-button-shape-next:has-text("Sign in")'
        )
        if sign_in:
            return False

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
    if not getattr(account, "google_password", None):
        _log(log_cb,
             f"No password stored for {account.email} — cannot log in. "
             "Go to Accounts → Edit (pencil icon) → enter the Google password → save. "
             "Then reset the account status (refresh icon) and restart the campaign.",
             "warning")
        return False

    _log(log_cb, f"Re-logging in as {account.email}…")

    try:
        await page.goto(GOOGLE_SIGNIN, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # ── Step 1: handle account picker ─────────────────────────────────────
        # If Google shows "Choose an account" we click the matching email,
        # or click "Use another account" if ours isn't listed.
        await _handle_account_picker(page, account.email, log_cb)

        # ── Step 2: fill email (may already be filled after picker) ───────────
        email_sel = 'input[type="email"], input[name="identifier"]'
        email_field = await page.query_selector(email_sel)
        if email_field:
            await _type_field(page, email_sel, account.email)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await _click_next(page)
            await asyncio.sleep(random.uniform(2.0, 3.0))

        # ── Step 3: navigate past passkey / "choose sign-in method" screens ───
        # Google increasingly shows a passkey screen first. We click through
        # to reach the password field.
        await _navigate_to_password_screen(page, log_cb)

        # ── Step 4: fill password ─────────────────────────────────────────────
        pass_sel = 'input[type="password"], input[name="Passwd"]'
        try:
            await page.wait_for_selector(pass_sel, timeout=15000)
        except Exception:
            url = page.url
            body = ""
            try:
                body = (await page.inner_text("body"))[:300]
            except Exception:
                pass
            _log(log_cb,
                 f"Password field not found after navigating Google login (URL: {url}). "
                 f"Page content: {body}. "
                 "Google may be requiring a passkey, phone verification, or is blocking "
                 "this sign-in attempt. Check the account at myaccount.google.com.",
                 "error")
            return False

        await _type_field(page, pass_sel, account.google_password)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await _click_next(page)
        await asyncio.sleep(random.uniform(2.5, 4.0))

        # ── Step 5: check for 2FA challenge ───────────────────────────────────
        if await _is_2fa_challenge(page):
            _log(log_cb,
                 f"2-Step Verification is enabled on {account.email} — cannot log in automatically. "
                 "OPTION 1 (easiest): go to myaccount.google.com/security → 2-Step Verification → Turn off. "
                 "OPTION 2: go to myaccount.google.com/apppasswords, generate an App Password, "
                 "then edit this account in ViewForge and paste the 16-character app password into the Password field.",
                 "error")
            return False

        # ── Step 6: confirm sign-in on YouTube ────────────────────────────────
        await page.goto(YOUTUBE_URL, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        ok = await is_signed_in(page)
        if ok:
            _log(log_cb, "Re-login successful")
        else:
            _log(log_cb,
                 "Re-login failed — Google may have blocked this sign-in attempt from this server. "
                 "Check the account's security alerts at myaccount.google.com.",
                 "warning")
        return ok

    except Exception as exc:
        _log(log_cb, f"Re-login error: {exc}", "error")
        return False


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log(cb, msg: str, level: str = "info"):
    if cb:
        cb(msg, level)


async def _handle_account_picker(page: Page, email: str, log_cb=None):
    """
    If Google shows a 'Choose an account' page, click the matching account
    or click 'Use another account' to proceed to the email entry screen.
    """
    try:
        # Check for the account picker heading
        picker = await page.query_selector('div[data-identifier], [data-email], li[data-email]')
        if not picker:
            return

        # Try to click the matching account
        account_btn = await page.query_selector(f'[data-identifier="{email}"], [data-email="{email}"]')
        if account_btn:
            await account_btn.click()
            await asyncio.sleep(1.5)
            return

        # Click "Use another account"
        for sel in [
            'li:has-text("Use another account")',
            'div:has-text("Use another account")',
            'button:has-text("Use another account")',
        ]:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await asyncio.sleep(1.5)
                return
    except Exception:
        pass


async def _navigate_to_password_screen(page: Page, log_cb=None):
    """
    After the email step, Google may show a passkey prompt or
    'Choose how to sign in' list. This function clicks through to the
    password field by trying 'Try another way' → 'Use your password'.
    """
    await asyncio.sleep(1.5)

    # If we're already on the password page, nothing to do
    pass_check = await page.query_selector('input[type="password"], input[name="Passwd"]')
    if pass_check:
        return

    # Try "Try another way" — appears on passkey and phone-prompt screens
    for sel in [
        'button:has-text("Try another way")',
        'a:has-text("Try another way")',
        'div[jsname="SApxQ"]',
        'span:has-text("Try another way")',
    ]:
        try:
            el = await page.wait_for_selector(sel, timeout=3000)
            if el:
                _log(log_cb, "Passkey screen detected — clicking 'Try another way'")
                await el.click()
                await asyncio.sleep(1.5)
                break
        except Exception:
            continue

    # After "Try another way", look for "Use your password" option
    for sel in [
        'li:has-text("Use your password")',
        'div:has-text("Use your password")',
        '[data-challengetype="PASSWORD"]',
        'button:has-text("Use your password")',
        'span:has-text("Use your password")',
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                _log(log_cb, "Selecting 'Use your password' option")
                await el.click()
                await asyncio.sleep(1.5)
                return
        except Exception:
            continue

    # Some Google UIs show numbered challenge options — try clicking the password one
    for sel in [
        '[data-challengetype="14"]',  # PASSWORD challenge type
        '[data-challengetype="2"]',
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await asyncio.sleep(1.5)
                return
        except Exception:
            continue


async def _is_2fa_challenge(page: Page) -> bool:
    try:
        if any(seg in page.url for seg in ("/challenge/", "/2sv/", "signin/v2/challenge")):
            return True
        totp = await page.query_selector('input[name="totpPin"], input[name="idvPin"]')
        if totp:
            return True
        challenge_div = await page.query_selector('div[data-challengetype], div[data-challengeid]')
        if challenge_div:
            return True
        body = (await page.inner_text("body")).lower()
        if any(phrase in body for phrase in (
            "2-step verification", "verify it's you", "verify its you",
            "check your phone", "get a verification code",
            "enter the code", "authenticator app",
        )):
            return True
        return False
    except Exception:
        return False


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
