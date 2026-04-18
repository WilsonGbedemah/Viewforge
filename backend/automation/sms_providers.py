"""
SMS verification provider integrations.

Supported providers:
  5sim         — https://5sim.net          (default)
  sms-activate — https://sms-activate.org  (larger inventory, good fallback)

─────────────────────────────────────────────────────────────────────────────
SINGLE PROVIDER (legacy, still works)
─────────────────────────────────────────────────────────────────────────────
  SMS_PROVIDER=5sim
  SMS_API_KEY=your_5sim_key

─────────────────────────────────────────────────────────────────────────────
MULTI-PROVIDER FALLBACK (recommended — never runs out of numbers)
─────────────────────────────────────────────────────────────────────────────
  SMS_PROVIDERS=5sim,sms-activate          # tried left-to-right
  SMS_API_KEY_5SIM=your_5sim_key
  SMS_API_KEY_SMS_ACTIVATE=your_sms_activate_key

  If 5sim has no numbers in stock it instantly tries sms-activate.
  If both are exhausted the provisioner retries the whole chain after a delay.
"""
import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import httpx

logger = logging.getLogger("viewforge.sms")

# Sentinel string embedded in RuntimeError when a provider has no numbers in
# stock.  Provisioner catches this and retries after a delay (or tries the
# next provider in the fallback chain) rather than aborting the account slot.
NO_FREE_PHONES = "NO_FREE_PHONES"


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

    # Plain-text errors 5sim returns instead of JSON
    _PLAIN_NO_STOCK = {"no free phones", "not enough product"}
    _PLAIN_ERRORS = {
        "not enough rating": "Your 5sim account rating is too low. Complete more purchases to raise it.",
        "bad request":       "5sim rejected the request. Check the country code in campaign settings.",
        "no connection":     "5sim cannot connect to the carrier. Try again in a minute.",
    }

    def __init__(self, api_key: str):
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    def _parse_json(self, r) -> dict:
        body = r.text.strip()
        if not body:
            raise RuntimeError(
                f"5sim returned an empty response (HTTP {r.status_code}). "
                "Check SMS_API_KEY is set correctly in Railway Variables "
                "and your 5sim balance is above $0 at https://5sim.net"
            )
        body_lower = body.lower()
        for key in self._PLAIN_NO_STOCK:
            if key in body_lower:
                raise RuntimeError(NO_FREE_PHONES)
        for key, friendly in self._PLAIN_ERRORS.items():
            if key in body_lower:
                raise RuntimeError(f"5sim error — {friendly}")
        try:
            return r.json()
        except Exception:
            raise RuntimeError(f"5sim returned non-JSON (HTTP {r.status_code}): {body[:300]}")

    async def check_balance(self) -> float:
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
                await client.get(f"{self.BASE}/user/cancel/{activation_id}", headers=self.headers)
            except Exception:
                pass

    async def confirm(self, activation_id: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                await client.get(f"{self.BASE}/user/finish/{activation_id}", headers=self.headers)
            except Exception:
                pass


# ── sms-activate ──────────────────────────────────────────────────────────────

class SmsActivateProvider(SMSProvider):
    BASE = os.getenv("SMS_BASE_URL", "https://api.sms-activate.org/stubs/handler_api.php")

    # Country IDs for the Google service ("go")
    COUNTRY_IDS = {
        "us": "12", "gb": "16", "uk": "16",
        "ca": "36", "au": "37", "de": "43",
        "fr": "78", "nl": "72", "any": "0",
    }

    # Response codes that mean "no numbers right now — try later"
    _NO_STOCK_CODES = {"NO_NUMBERS", "NO_NUMBERS_FILTERED"}

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _cid(self, country: str) -> str:
        return self.COUNTRY_IDS.get(country.lower(), "0")

    async def check_balance(self) -> float:
        params = {"api_key": self.api_key, "action": "getBalance"}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(self.BASE, params=params)
            r.raise_for_status()
            text = r.text.strip()
        # Response: "ACCESS_BALANCE:12.34"
        if text.startswith("ACCESS_BALANCE:"):
            return float(text.split(":")[1])
        raise RuntimeError(f"sms-activate balance error: {text}")

    async def get_number(self, country: str) -> Tuple[str, str]:
        params = {
            "api_key": self.api_key,
            "action":  "getNumber",
            "service": "go",
            "country": self._cid(country),
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self.BASE, params=params)
            r.raise_for_status()
            text = r.text.strip()
        if text in self._NO_STOCK_CODES:
            raise RuntimeError(NO_FREE_PHONES)
        if text == "NO_BALANCE":
            raise RuntimeError(
                "sms-activate balance is too low. Top up at https://sms-activate.org"
            )
        if not text.startswith("ACCESS_NUMBER:"):
            raise RuntimeError(f"sms-activate error: {text}")
        parts = text.split(":")
        activation_id = parts[1]
        phone = parts[2] if len(parts) > 2 else parts[1]
        if not phone.startswith("+"):
            phone = "+" + phone
        return activation_id, phone

    async def get_code(self, activation_id: str) -> Optional[str]:
        params = {"api_key": self.api_key, "action": "getStatus", "id": activation_id}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self.BASE, params=params)
            r.raise_for_status()
            text = r.text.strip()
        if text.startswith("STATUS_OK:"):
            return text.split(":")[1]
        return None

    async def cancel(self, activation_id: str) -> None:
        params = {"api_key": self.api_key, "action": "setStatus", "status": "8", "id": activation_id}
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                await client.get(self.BASE, params=params)
            except Exception:
                pass

    async def confirm(self, activation_id: str) -> None:
        params = {"api_key": self.api_key, "action": "setStatus", "status": "6", "id": activation_id}
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                await client.get(self.BASE, params=params)
            except Exception:
                pass


# ── Fallback chain ────────────────────────────────────────────────────────────

class FallbackSMSProvider(SMSProvider):
    """
    Wraps an ordered list of providers.  get_number() tries each in order;
    if one has no numbers in stock it immediately tries the next.
    All other calls (get_code, cancel, confirm) are routed back to whichever
    provider successfully issued the number (tracked via an index prefix in
    the activation_id).
    """

    def __init__(self, providers: List[SMSProvider], names: List[str]):
        self._providers = providers
        self._names     = names

    async def get_number(self, country: str) -> Tuple[str, str]:
        for i, (prov, name) in enumerate(zip(self._providers, self._names)):
            try:
                act_id, phone = await prov.get_number(country)
                logger.info("Got number from %s", name)
                return f"{i}:{act_id}", phone
            except RuntimeError as e:
                if NO_FREE_PHONES in str(e):
                    logger.warning("%s has no numbers in stock — trying next provider", name)
                    continue
                raise
        # All providers exhausted — signal provisioner to retry later
        raise RuntimeError(NO_FREE_PHONES)

    def _route(self, activation_id: str) -> Tuple[SMSProvider, str]:
        idx_str, real_id = activation_id.split(":", 1)
        return self._providers[int(idx_str)], real_id

    async def get_code(self, activation_id: str) -> Optional[str]:
        prov, real_id = self._route(activation_id)
        return await prov.get_code(real_id)

    async def cancel(self, activation_id: str) -> None:
        prov, real_id = self._route(activation_id)
        await prov.cancel(real_id)

    async def confirm(self, activation_id: str) -> None:
        prov, real_id = self._route(activation_id)
        await prov.confirm(real_id)

    async def check_balance(self) -> dict:
        """Returns {provider_name: balance_float} for providers that support it."""
        out = {}
        for prov, name in zip(self._providers, self._names):
            if hasattr(prov, "check_balance"):
                try:
                    out[name] = await prov.check_balance()
                except Exception as e:
                    out[name] = f"error: {e}"
        return out


# ── Manual (test) provider ────────────────────────────────────────────────────

class ManualSMSProvider(SMSProvider):
    """
    No-cost provider for testing.  Pauses automation and emits WebSocket
    events asking the operator to supply a real phone number and OTP via UI.
    """

    def __init__(self, creation_id: str, input_queue: asyncio.Queue, emit_fn):
        self.creation_id = creation_id
        self.queue       = input_queue
        self._emit       = emit_fn

    async def get_number(self, country: str) -> Tuple[str, str]:
        self._emit(
            "Enter a phone number to use for verification",
            "waiting_phone",
            prompt_type="phone",
            hint=f"Use a real SIM card number for {country.upper()}. Google will send an SMS to it.",
        )
        phone = await asyncio.wait_for(self.queue.get(), timeout=300)
        if not phone.startswith("+"):
            phone = "+" + phone
        return "manual", phone

    async def get_code(self, activation_id: str) -> Optional[str]:
        return None

    async def wait_for_code(self, activation_id: str, timeout: int = 300, poll_interval: int = 5) -> str:
        self._emit(
            "Check your phone for the SMS code and enter it below",
            "waiting_code",
            prompt_type="code",
        )
        code = await asyncio.wait_for(self.queue.get(), timeout=timeout)
        return code.strip()

    async def cancel(self, activation_id: str) -> None:
        pass

    async def confirm(self, activation_id: str) -> None:
        pass


# ── Factory ───────────────────────────────────────────────────────────────────

def _build_provider(name: str, api_key: str) -> Optional[SMSProvider]:
    name = name.lower().strip()
    if name == "5sim":
        return FiveSimProvider(api_key)
    if name in ("sms-activate", "smsactivate", "sms_activate"):
        return SmsActivateProvider(api_key)
    return None


def get_sms_provider() -> Optional[SMSProvider]:
    """
    Return the configured SMS provider (or fallback chain), or None if not set.

    Multi-provider (recommended):
      SMS_PROVIDERS=5sim,sms-activate
      SMS_API_KEY_5SIM=...
      SMS_API_KEY_SMS_ACTIVATE=...

    Single provider (legacy):
      SMS_PROVIDER=5sim
      SMS_API_KEY=...
    """
    # ── Multi-provider mode ────────────────────────────────────────────────────
    providers_str = os.getenv("SMS_PROVIDERS", "").strip()
    if providers_str:
        providers: List[SMSProvider] = []
        names: List[str] = []
        for p_name in [p.strip() for p in providers_str.split(",") if p.strip()]:
            # Look for SMS_API_KEY_5SIM, SMS_API_KEY_SMS_ACTIVATE, etc.
            env_key = f"SMS_API_KEY_{p_name.upper().replace('-', '_')}"
            api_key = os.getenv(env_key, "").strip()
            if not api_key:
                # Fallback: if only one provider, accept bare SMS_API_KEY
                api_key = os.getenv("SMS_API_KEY", "").strip() if len(providers_str.split(",")) == 1 else ""
            if not api_key:
                logger.warning("No API key found for SMS provider '%s' (set %s in Railway Variables)", p_name, env_key)
                continue
            prov = _build_provider(p_name, api_key)
            if prov:
                providers.append(prov)
                names.append(p_name)
        if not providers:
            return None
        if len(providers) == 1:
            return providers[0]
        return FallbackSMSProvider(providers, names)

    # ── Legacy single-provider mode ────────────────────────────────────────────
    provider_name = os.getenv("SMS_PROVIDER", "").lower().strip()
    api_key       = os.getenv("SMS_API_KEY", "").strip()
    if not provider_name or not api_key:
        return None
    return _build_provider(provider_name, api_key)
