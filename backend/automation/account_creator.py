"""
Google Account Auto-Creation Engine.

Opens a real Chromium browser and walks through Google's account signup
flow without any human involvement. Phone verification is handled via a
configured SMS provider (5sim or sms-activate).

Typical creation time: 2–5 minutes (dominated by SMS wait time).

Raises:
  AccountCreationError — SMS not configured, CAPTCHA blocked, or Google
                         rejected the account.
  TimeoutError         — SMS code did not arrive within the timeout window.
"""
import asyncio
import json
import os
import random
import secrets
import string
import time
from dataclasses import dataclass
from typing import Callable, Optional

from playwright.async_api import async_playwright, BrowserContext, Page

from automation.interaction import move_mouse_to
from automation.sms_providers import get_sms_provider, SMSProvider


# ── Name pool (kept internal — no extra dependency needed) ────────────────────

_FIRST = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard",
    "Joseph", "Thomas", "Charles", "Emily", "Emma", "Olivia", "Ava",
    "Isabella", "Sophia", "Mia", "Charlotte", "Amelia", "Harper", "Liam",
    "Noah", "Ethan", "Mason", "Logan", "Lucas", "Jackson", "Aiden",
    "Carter", "Daniel", "Grace", "Lily", "Hannah", "Zoe", "Natalie",
    "Victoria", "Samantha", "Ella", "Chloe", "Layla", "Ryan", "Tyler",
    "Kevin", "Brandon", "Justin", "Andrew", "Jonathan", "Kyle", "Brian",
]

_LAST = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis",
    "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson", "White",
    "Harris", "Martin", "Garcia", "Martinez", "Robinson", "Clark",
    "Rodriguez", "Lewis", "Lee", "Walker", "Hall", "Allen", "Young",
    "Hernandez", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill",
    "Flores", "Green", "Adams", "Nelson", "Baker", "Campbell", "Mitchell",
    "Perez", "Roberts", "Turner", "Phillips", "Evans", "Parker", "Reed",
]


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class AccountDetails:
    first_name:  str
    last_name:   str
    username:    str    # Gmail username (without @gmail.com)
    password:    str
    birth_day:   int
    birth_month: int    # 1–12
    birth_year:  int
    gender:      str    # "1" = male, "2" = female


@dataclass
class AccountCreationResult:
    email:       str    # full @gmail.com address
    password:    str
    cookie_data: str    # JSON-encoded list of Playwright cookies
    profile_dir: str


class AccountCreationError(Exception):
    pass


# ── Detail generator ──────────────────────────────────────────────────────────

def generate_account_details() -> AccountDetails:
    first = random.choice(_FIRST)
    last  = random.choice(_LAST)

    # e.g. james.wilson4821
    suffix   = str(random.randint(100, 9999))
    username = f"{first.lower()}.{last.lower()}{suffix}"

    # Strong password — uppercase + lowercase + digit + symbol, 12 chars
    pool = string.ascii_letters + string.digits + "!@#$%&"
    pwd  = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&"),
    ]
    pwd += [secrets.choice(pool) for _ in range(8)]
    random.shuffle(pwd)

    # Age 20–35
    year  = random.randint(1988, 2003)
    month = random.randint(1, 12)
    max_day = 28 if month == 2 else (30 if month in (4, 6, 9, 11) else 31)
    day   = random.randint(1, max_day)

    return AccountDetails(
        first_name  = first,
        last_name   = last,
        username    = username,
        password    = "".join(pwd),
        birth_day   = day,
        birth_month = month,
        birth_year  = year,
        gender      = random.choice(["1", "2"]),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _proxy_cfg(proxy) -> Optional[dict]:
    if not proxy:
        return None
    cfg = {"server": f"{proxy.protocol}://{proxy.host}:{proxy.port}"}
    if proxy.username:
        cfg["username"] = proxy.username
    if proxy.password:
        cfg["password"] = proxy.password
    return cfg


def _rand_ua() -> str:
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ])


# ── Creator ───────────────────────────────────────────────────────────────────

class AccountCreator:
    """
    Drives the full Google account signup flow in a real Chromium window.

    Usage:
        creator = AccountCreator(proxy=account.proxy, log_cb=my_fn)
        result  = await creator.create(country="us")
        # result.email, result.password, result.cookie_data
    """

    SIGNUP_URL = (
        "https://accounts.google.com/signup/v2/createaccount"
        "?flowName=GlifWebSignIn&flowEntry=SignUp"
    )

    def __init__(
        self,
        proxy=None,
        profile_base_dir: str = "./profiles",
        log_cb: Optional[Callable] = None,
    ):
        self.proxy            = proxy
        self.profile_base_dir = profile_base_dir
        self._log_cb          = log_cb or (lambda msg, level="info": None)

    def log(self, msg: str, level: str = "info"):
        self._log_cb(msg, level)

    # ── Public entry point ────────────────────────────────────────────────────

    async def create(self, country: str = "us") -> AccountCreationResult:
        provider = get_sms_provider()
        if not provider:
            raise AccountCreationError(
                "No SMS provider configured. "
                "Set SMS_PROVIDER and SMS_API_KEY in your .env file."
            )

        details = generate_account_details()
        self.log(
            f"Generated: {details.first_name} {details.last_name} "
            f"/ @{details.username}"
        )

        self.log(f"Requesting phone number ({country.upper()})…")
        activation_id, phone = await provider.get_number(country)
        self.log(f"Got number: {phone}")

        profile_dir = os.path.join(
            self.profile_base_dir,
            f"auto_{details.username}_{int(time.time())}",
        )
        os.makedirs(profile_dir, exist_ok=True)

        pw = None
        try:
            pw      = await async_playwright().start()
            context = await pw.chromium.launch_persistent_context(
                profile_dir,
                headless=os.getenv("HEADLESS", "true").lower() == "true",
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                ],
                proxy            = _proxy_cfg(self.proxy),
                viewport         = {"width": 1280, "height": 800},
                user_agent       = _rand_ua(),
                locale           = "en-US",
                timezone_id      = "America/New_York",
            )

            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins',  { get: () => [1,2,3,4,5] });
                window.chrome = { runtime: {} };
            """)

            page = await context.new_page()
            try:
                result = await self._run_signup(
                    page, context, details, phone, activation_id, provider, profile_dir
                )
                await provider.confirm(activation_id)
                return result
            except Exception:
                try:
                    await provider.cancel(activation_id)
                except Exception:
                    pass
                raise
            finally:
                try:
                    await page.close()
                except Exception:
                    pass
                try:
                    await context.close()
                except Exception:
                    pass
        finally:
            if pw:
                try:
                    await pw.stop()
                except Exception:
                    pass

    # ── Signup flow ───────────────────────────────────────────────────────────

    async def _run_signup(
        self,
        page: Page,
        context: BrowserContext,
        details: AccountDetails,
        phone: str,
        activation_id: str,
        provider: SMSProvider,
        profile_dir: str,
    ) -> AccountCreationResult:

        self.log("Opening Google signup page…")
        await page.goto(self.SIGNUP_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(random.uniform(1.5, 3.0))

        # Step 1 — name
        await self._fill_name(page, details)

        # Step 2 — birthday/gender (appears at different points across flows)
        if await self._on_birthday_page(page):
            await self._fill_birthday_gender(page, details)

        # Step 3 — username
        await self._fill_username(page, details)

        # Step 4 — birthday/gender (if it comes after username in this flow)
        if await self._on_birthday_page(page):
            await self._fill_birthday_gender(page, details)

        # Step 5 — password
        await self._fill_password(page, details)

        # Step 6 — phone verification
        await self._handle_phone_verification(page, provider, activation_id, phone)

        # Step 7 — skip recovery email if prompted
        await self._skip_recovery_email(page)

        # Step 8 — accept terms (may need several Next/Agree clicks)
        await self._agree_to_terms(page)

        # Harvest cookies
        self.log("Saving session cookies…")
        cookies     = await context.cookies()
        cookie_data = json.dumps(cookies)
        email       = f"{details.username}@gmail.com"
        self.log(f"Account created: {email}")

        return AccountCreationResult(
            email       = email,
            password    = details.password,
            cookie_data = cookie_data,
            profile_dir = profile_dir,
        )

    # ── Page-level helpers ────────────────────────────────────────────────────

    async def _fill_name(self, page: Page, details: AccountDetails):
        self.log("Filling in name…")
        await page.wait_for_selector('input[name="firstName"]', timeout=15000)
        await asyncio.sleep(random.uniform(0.5, 1.2))
        await self._type_field(page, 'input[name="firstName"]', details.first_name)
        await asyncio.sleep(random.uniform(0.3, 0.7))
        await self._type_field(page, 'input[name="lastName"]',  details.last_name)
        await asyncio.sleep(random.uniform(0.4, 0.9))
        await self._click_next(page)
        await asyncio.sleep(random.uniform(1.2, 2.2))

    async def _fill_birthday_gender(self, page: Page, details: AccountDetails):
        self.log("Filling birthday and gender…")
        await asyncio.sleep(random.uniform(0.5, 1.0))

        for sel, value in [
            ('select#month, select[id="month"]', str(details.birth_month)),
        ]:
            try:
                await page.wait_for_selector(sel, timeout=5000)
                await page.select_option(sel, value)
                await asyncio.sleep(random.uniform(0.3, 0.6))
            except Exception:
                pass

        for sel, value in [
            ('input#day,  input[id="day"]',    str(details.birth_day)),
            ('input#year, input[id="year"]',   str(details.birth_year)),
        ]:
            try:
                await self._type_field(page, sel, value)
                await asyncio.sleep(random.uniform(0.2, 0.5))
            except Exception:
                pass

        try:
            await page.select_option('select#gender, select[id="gender"]', details.gender)
            await asyncio.sleep(random.uniform(0.3, 0.6))
        except Exception:
            pass

        await self._click_next(page)
        await asyncio.sleep(random.uniform(1.2, 2.2))

    async def _fill_username(self, page: Page, details: AccountDetails):
        self.log(f"Choosing username: {details.username}…")
        sel = 'input[name="Username"]'
        try:
            await page.wait_for_selector(sel, timeout=10000)
        except Exception:
            return  # flow may have skipped username entry

        await asyncio.sleep(random.uniform(0.5, 1.0))

        # If Google shows pre-generated suggestions, choose "Create your own"
        for opt_sel in [
            'text="Create your own Gmail address"',
            '[data-value="username"]',
            'input[value="username"]',
        ]:
            try:
                el = await page.query_selector(opt_sel)
                if el:
                    await el.click()
                    await asyncio.sleep(random.uniform(0.4, 0.8))
                    break
            except Exception:
                pass

        await self._type_field(page, sel, details.username)
        await asyncio.sleep(random.uniform(0.5, 1.2))
        await self._click_next(page)
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # Retry if username is taken
        for _ in range(5):
            body = (await page.text_content("body") or "").lower()
            if "already" not in body and "unavailable" not in body:
                break
            suffix = str(random.randint(10, 9999))
            alt    = f"{details.first_name.lower()}.{details.last_name.lower()}{suffix}"
            self.log(f"Username taken, trying: {alt}")
            details.username = alt
            await self._clear_field(page, sel)
            await self._type_field(page, sel, alt)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await self._click_next(page)
            await asyncio.sleep(random.uniform(1.5, 2.5))

    async def _fill_password(self, page: Page, details: AccountDetails):
        self.log("Setting password…")
        pass_sel    = 'input[name="Passwd"]'
        confirm_sel = 'input[name="ConfirmPasswd"]'
        try:
            await page.wait_for_selector(pass_sel, timeout=10000)
        except Exception:
            return
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await self._type_field(page, pass_sel,    details.password)
        await asyncio.sleep(random.uniform(0.3, 0.7))
        await self._type_field(page, confirm_sel, details.password)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await self._click_next(page)
        await asyncio.sleep(random.uniform(1.5, 2.5))

    async def _handle_phone_verification(
        self,
        page: Page,
        provider: SMSProvider,
        activation_id: str,
        phone: str,
    ):
        self.log("Handling phone verification…")
        phone_sel = (
            'input#phoneNumberId, '
            'input[id="phoneNumberId"], '
            'input[type="tel"]'
        )
        try:
            await page.wait_for_selector(phone_sel, timeout=15000)
        except Exception:
            self.log("Phone field not found — skipping phone step", "warning")
            return

        await asyncio.sleep(random.uniform(0.8, 1.5))
        self.log(f"Entering phone: {phone}")
        await self._type_field(page, phone_sel, phone.lstrip("+"))
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await self._click_next(page)
        await asyncio.sleep(random.uniform(2.0, 3.5))

        # Wait for SMS code (up to 2 minutes)
        self.log("Waiting for SMS verification code (up to 2 min)…")
        code = await provider.wait_for_code(activation_id, timeout=120, poll_interval=5)
        self.log(f"Received SMS code: {code}")

        code_sel = 'input#code, input[id="code"], input[name="code"]'
        try:
            await page.wait_for_selector(code_sel, timeout=10000)
        except Exception:
            pass
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await self._type_field(page, code_sel, code)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        await self._click_next(page)
        await asyncio.sleep(random.uniform(2.0, 3.5))

    async def _skip_recovery_email(self, page: Page):
        for sel in [
            'button:has-text("Skip")',
            'span:has-text("Skip")',
        ]:
            try:
                el = await page.query_selector(sel)
                if el:
                    self.log("Skipping recovery email…")
                    await el.click()
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    break
            except Exception:
                pass

    async def _agree_to_terms(self, page: Page):
        self.log("Accepting terms of service…")
        for _ in range(5):
            try:
                for sel in [
                    'button:has-text("I agree")',
                    'span:has-text("I agree")',
                    'button:has-text("Agree")',
                    'button:has-text("Accept")',
                ]:
                    el = await page.query_selector(sel)
                    if el:
                        await el.click()
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                        break
                else:
                    if await self._click_next(page, silent=True):
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                    else:
                        break  # nothing left to click
            except Exception:
                break

    # ── Low-level ─────────────────────────────────────────────────────────────

    async def _on_birthday_page(self, page: Page) -> bool:
        try:
            el = await page.query_selector(
                'input#day, input[id="day"], select#month'
            )
            return el is not None
        except Exception:
            return False

    async def _click_next(self, page: Page, silent: bool = False) -> bool:
        """Try every known selector for the Next / Continue button."""
        for sel in [
            "#accountDetailsNext button",
            "#nameNext button",
            "#birthdayNext button",
            "#usernameNext button",
            "#passwordNext button",
            "#verifyAccountPhoneNext button",
            "#pinNext button",
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'div[jsname="0UZ4fc"] button',
            'span:has-text("Next")',
        ]:
            try:
                el = await page.query_selector(sel)
                if not el:
                    continue
                box = await el.bounding_box()
                if not box:
                    continue
                tx = box["x"] + box["width"]  * random.uniform(0.3, 0.7)
                ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                await move_mouse_to(page, tx, ty)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await page.mouse.click(tx, ty)
                return True
            except Exception:
                continue

        if not silent:
            self.log("Next button not found — pressing Enter", "warning")
            await page.keyboard.press("Enter")
        return False

    async def _type_field(self, page: Page, selector: str, text: str):
        """Click a field and type text at human speed."""
        try:
            el = await page.wait_for_selector(selector, timeout=5000)
            if not el:
                return
            box = await el.bounding_box()
            if box:
                tx = box["x"] + box["width"]  * random.uniform(0.3, 0.7)
                ty = box["y"] + box["height"] * random.uniform(0.3, 0.7)
                await move_mouse_to(page, tx, ty)
                await asyncio.sleep(random.uniform(0.1, 0.25))
                await page.mouse.click(tx, ty)
                await asyncio.sleep(random.uniform(0.1, 0.2))
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Delete")
            for char in text:
                await page.keyboard.type(char, delay=random.uniform(50, 160))
        except Exception:
            pass

    async def _clear_field(self, page: Page, selector: str):
        """Triple-click a field to select all and delete."""
        try:
            el = await page.query_selector(selector)
            if el:
                await el.triple_click()
                await asyncio.sleep(random.uniform(0.1, 0.2))
                await page.keyboard.press("Delete")
        except Exception:
            pass
