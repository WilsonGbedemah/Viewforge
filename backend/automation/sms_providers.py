"""
SMS verification provider integrations.

Supported providers:
  sms-activate — https://sms-activate.org  (recommended, largest inventory, global)
  5sim         — https://5sim.net          (alternative, cheap US/UK numbers)

Configure via .env:
  SMS_PROVIDER=sms-activate
  SMS_API_KEY=your_key_here
  SMS_DEFAULT_COUNTRY=us
"""
import asyncio
import os
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import httpx


class SMSProvider(ABC):

    @abstractmethod
    async def get_number(self, country: str) -> Tuple[str, str]:
        """Request a virtual number. Returns (activation_id, e164_phone_number)."""

    @abstractmethod
    async def get_code(self, activation_id: str) -> Optional[str]:
        """Check if an SMS code has arrived. Returns the 6-digit code or None."""

    @abstractmethod
    async def cancel(self, activation_id: str) -> None:
        """Release a number we no longer need (called on failure)."""

    @abstractmethod
    async def confirm(self, activation_id: str) -> None:
        """Mark a number as successfully used (called on success)."""

    async def wait_for_code(
        self,
        activation_id: str,
        timeout: int = 120,
        poll_interval: int = 5,
    ) -> str:
        """Poll until the SMS code arrives or timeout is reached."""
        elapsed = 0
        while elapsed < timeout:
            code = await self.get_code(activation_id)
            if code:
                return code
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        raise TimeoutError(f"SMS code not received within {timeout}s")


# ── 5sim ──────────────────────────────────────────────────────────────────────

class FiveSimProvider(SMSProvider):
    BASE = "https://5sim.net/v1"

    def __init__(self, api_key: str):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    # Known plain-text error strings returned by 5sim (not JSON)
    _PLAIN_ERRORS = {
        "no free phones":       "No phone numbers available for this country. Switch to 'us' in campaign settings.",
        "not enough product":   "No numbers in stock for this country/service. Switch to 'us' in campaign settings.",
        "not enough rating":    "Your 5sim account rating is too low to buy numbers. Complete more purchases to raise it.",
        "bad request":          "5sim rejected the request. Check the country code in campaign settings.",
        "no connection":        "5sim cannot connect to the carrier. Try again or switch country.",
    }

    def _parse_json(self, r) -> dict:
        """Parse JSON response, raising a clear error if the body is empty or not JSON."""
        body = r.text.strip()
        if not body:
            raise RuntimeError(
                f"5sim returned an empty response (HTTP {r.status_code}). "
                "Check that SMS_API_KEY is set correctly in Railway Variables "
                "and that your 5sim balance is above $0 at https://5sim.net"
            )
        # 5sim returns plain-text strings for known error conditions
        body_lower = body.lower()
        for key, friendly in self._PLAIN_ERRORS.items():
            if key in body_lower:
                raise RuntimeError(f"5sim error — {friendly}")
        try:
            return r.json()
        except Exception:
            raise RuntimeError(
                f"5sim returned non-JSON (HTTP {r.status_code}): {body[:300]}"
            )

    async def check_balance(self) -> float:
        """Return current account balance. Raises if unreachable or unauthorised."""
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{self.BASE}/user/profile", headers=self.headers)
            data = self._parse_json(r)
            return float(data.get("balance", 0))

    async def get_number(self, country: str) -> Tuple[str, str]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.BASE}/user/buy/activation/{country.lower()}/any/google",
                headers=self.headers,
            )
            r.raise_for_status()
            data = self._parse_json(r)
            activation_id = str(data["id"])
            phone = data["phone"]
            if not phone.startswith("+"):
                phone = "+" + phone
            return activation_id, phone

    async def get_code(self, activation_id: str) -> Optional[str]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.BASE}/user/check/{activation_id}",
                headers=self.headers,
            )
            r.raise_for_status()
            data = self._parse_json(r)
            sms_list = data.get("sms") or []
            if sms_list:
                return sms_list[-1].get("code")
            return None

    async def cancel(self, activation_id: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                await client.get(
                    f"{self.BASE}/user/cancel/{activation_id}",
                    headers=self.headers,
                )
            except Exception:
                pass

    async def confirm(self, activation_id: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                await client.get(
                    f"{self.BASE}/user/finish/{activation_id}",
                    headers=self.headers,
                )
            except Exception:
                pass


# ── sms-activate ──────────────────────────────────────────────────────────────

class SmsActivateProvider(SMSProvider):
    # Configurable via SMS_BASE_URL env var — defaults to the canonical endpoint.
    # smsactive.org is a website mirror only; the API lives at api.sms-activate.org.
    BASE = os.getenv(
        "SMS_BASE_URL",
        "https://api.sms-activate.org/stubs/handler_api.php",
    )

    # Country IDs for Google (service code "go") — most common ones
    COUNTRY_IDS = {
        "us": "12", "gb": "16", "uk": "16",
        "ca": "36", "au": "37", "de": "43",
        "fr": "78", "nl": "72", "any": "0",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _cid(self, country: str) -> str:
        return self.COUNTRY_IDS.get(country.lower(), "0")

    async def get_number(self, country: str) -> Tuple[str, str]:
        params = {
            "api_key": self.api_key,
            "action": "getNumber",
            "service": "go",
            "country": self._cid(country),
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self.BASE, params=params)
            r.raise_for_status()
            text = r.text.strip()
        # Response: "ACCESS_NUMBER:12345678:+15551234567"
        if not text.startswith("ACCESS_NUMBER:"):
            raise RuntimeError(f"sms-activate error: {text}")
        parts = text.split(":")
        activation_id = parts[1]
        phone = parts[2] if len(parts) > 2 else parts[1]
        if not phone.startswith("+"):
            phone = "+" + phone
        return activation_id, phone

    async def get_code(self, activation_id: str) -> Optional[str]:
        params = {
            "api_key": self.api_key,
            "action": "getStatus",
            "id": activation_id,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self.BASE, params=params)
            r.raise_for_status()
            text = r.text.strip()
        # Response: "STATUS_OK:123456" or "STATUS_WAIT_CODE"
        if text.startswith("STATUS_OK:"):
            return text.split(":")[1]
        return None

    async def cancel(self, activation_id: str) -> None:
        params = {
            "api_key": self.api_key,
            "action": "setStatus",
            "status": "8",  # 8 = cancel
            "id": activation_id,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                await client.get(self.BASE, params=params)
            except Exception:
                pass

    async def confirm(self, activation_id: str) -> None:
        params = {
            "api_key": self.api_key,
            "action": "setStatus",
            "status": "6",  # 6 = confirm received
            "id": activation_id,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                await client.get(self.BASE, params=params)
            except Exception:
                pass


# ── Manual (test) provider ────────────────────────────────────────────────────

class ManualSMSProvider(SMSProvider):
    """
    No-cost provider for testing.

    Instead of calling an API it pauses the automation and emits WebSocket
    events asking the operator to supply a real phone number and OTP code
    through the UI progress modal.

    Requires a creation_id and an asyncio.Queue that the HTTP endpoint
    writes into when the user submits input.
    """

    def __init__(self, creation_id: str, input_queue: asyncio.Queue, emit_fn):
        self.creation_id = creation_id
        self.queue       = input_queue
        self._emit       = emit_fn   # callable(msg, status, **extra)

    async def get_number(self, country: str) -> Tuple[str, str]:
        """Ask the UI for a real phone number. Returns ("manual", phone)."""
        self._emit(
            "Enter a phone number to use for verification",
            "waiting_phone",
            prompt_type="phone",
            hint=f"Use a real SIM card number for {country.upper()}. Google will send an SMS to it.",
        )
        # Wait for the UI to POST the phone number
        phone = await asyncio.wait_for(self.queue.get(), timeout=300)
        if not phone.startswith("+"):
            phone = "+" + phone
        return "manual", phone

    async def get_code(self, activation_id: str) -> Optional[str]:
        # Not used in manual mode — wait_for_code is overridden below
        return None

    async def wait_for_code(
        self,
        activation_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> str:
        """Ask the UI for the OTP code that arrived on the user's phone."""
        self._emit(
            "Check your phone for the SMS code and enter it below",
            "waiting_code",
            prompt_type="code",
        )
        code = await asyncio.wait_for(self.queue.get(), timeout=timeout)
        return code.strip()

    async def cancel(self, activation_id: str) -> None:
        pass  # nothing to cancel

    async def confirm(self, activation_id: str) -> None:
        pass  # nothing to confirm


# ── Factory ───────────────────────────────────────────────────────────────────

def get_sms_provider() -> Optional[SMSProvider]:
    """Return the configured SMS provider, or None if not configured."""
    provider_name = os.getenv("SMS_PROVIDER", "").lower().strip()
    api_key = os.getenv("SMS_API_KEY", "").strip()

    if not provider_name or not api_key:
        return None

    if provider_name == "5sim":
        return FiveSimProvider(api_key)
    if provider_name in ("sms-activate", "smsactivate", "sms_activate"):
        return SmsActivateProvider(api_key)

    return None
