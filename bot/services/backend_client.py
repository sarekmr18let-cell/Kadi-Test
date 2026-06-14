import httpx
from typing import Optional
import asyncio
import os


class BackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.internal_bot_secret = os.getenv("INTERNAL_BOT_SECRET", "")
        self.p2p_webhook_secret = os.getenv("P2P_WEBHOOK_SECRET", self.internal_bot_secret)
        self.client = httpx.AsyncClient(timeout=30.0)

    def _internal_headers(self) -> dict:
        return {"X-Bot-Secret": self.internal_bot_secret}

    async def _request(
        self,
        method: str,
        path: str,
        json: dict = None,
        headers: dict = None,
        retries: int = 3
    ):
        url = f"{self.base_url}/{path.lstrip('/')}"
        last_error = None

        for attempt in range(retries):
            try:
                response = await self.client.request(method, url, json=json, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Don't retry on 4xx client errors (except 429 rate limit)
                if e.response.status_code < 500 and e.response.status_code != 429:
                    raise
                last_error = e
            except httpx.RequestError as e:
                last_error = e

            if attempt < retries - 1:
                wait_time = min(2 ** attempt, 30)  # Exponential backoff capped at 30s
                await asyncio.sleep(wait_time)

        # All retries exhausted
        raise last_error if last_error else Exception("Request failed after all retries")

    async def get_profile(self, telegram_id: int):
        """Get user profile by telegram_id (bot uses internal endpoint)."""
        return await self._request(
            "GET",
            f"api/bot/profile/{telegram_id}",
            headers=self._internal_headers(),
        )

    async def get_orders(self, telegram_id: int):
        """Get user orders."""
        return await self._request(
            "GET",
            f"api/bot/orders/{telegram_id}",
            headers=self._internal_headers(),
        )

    async def get_balance(self, telegram_id: int):
        """Get user balance."""
        return await self._request(
            "GET",
            f"api/bot/balance/{telegram_id}",
            headers=self._internal_headers(),
        )

    async def register_referral(self, telegram_id: int, referrer_id: int):
        """Register referral."""
        return await self._request(
            "POST",
            "api/bot/referral",
            json={
                "telegram_id": telegram_id,
                "referrer_id": referrer_id,
            },
            headers=self._internal_headers(),
        )
    async def send_p2p_incoming(
        self,
        raw_text: str,
        source: str = "telegram_business_humo",
        external_id: str | None = None,
    ):
        """Send a raw bank-bot notification to backend P2P parser."""
        payload = {
            "source": source,
            "raw_text": raw_text,
        }
        if external_id:
            payload["external_id"] = external_id

        return await self._request(
            "POST",
            "api/payments/p2p/incoming",
            json=payload,
            headers={"X-P2P-Secret": self.p2p_webhook_secret},
        )

