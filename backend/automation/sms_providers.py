"""
SMS verification provider integrations.

Supported providers:
  5sim         — https://5sim.net          (recommended, cheap US/UK numbers)
  sms-activate — https://sms-activate.org  (large inventory, global)

Configure via .env:
  SMS_PROVIDER=5sim
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

    async def get_number(self, country: str) -> Tuple[str, str]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.BASE}/user/buy/activation/{country.lower()}/any/google",
                headers=self.headers,
            )
            r.raise_for_status()
            data = r.json()
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
            data = r.json()
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
    BASE = "https://api.sms-activate.org/stubs/handler_api.php"

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
