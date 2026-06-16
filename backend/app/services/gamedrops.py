import httpx
from typing import Any, Optional

from app.core.config import settings


class GameDropsError(Exception):
    """Base GameDrops error."""


class GameDropsNotConfigured(GameDropsError):
    """Raised when GameDrops token is missing."""


class GameDropsClient:
    """
    Safe async client for GameDrops Partner API.

    Base URL:
      https://partner.gamesdrop.io

    Auth:
      Authorization: <GAMEDROPS_API_TOKEN>
    """

    def __init__(self):
        self.base_url = settings.GAMEDROPS_BASE_URL.rstrip("/")
        self.token = settings.GAMEDROPS_API_TOKEN.strip()
        self._client = httpx.AsyncClient(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise GameDropsNotConfigured("GAMEDROPS_API_TOKEN is not configured")

        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=payload or {},
            )
            response.raise_for_status()

            data = response.json()
            if isinstance(data, dict):
                return data

            return {"raw": data}

        except GameDropsNotConfigured:
            raise
        except httpx.HTTPStatusError as exc:
            try:
                error_body = exc.response.json()
            except Exception:
                error_body = exc.response.text

            raise GameDropsError(
                f"GameDrops HTTP {exc.response.status_code}: {error_body}"
            ) from exc
        except httpx.RequestError as exc:
            raise GameDropsError(f"GameDrops request failed: {exc}") from exc
        except Exception as exc:
            raise GameDropsError(f"GameDrops unexpected error: {exc}") from exc

    async def get_balance(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/offers/balance")

    async def sync_offers(self) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/offers/sync")

    async def find_offer(self, offer_id: int | str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/offers/find-one",
            {"offerId": int(offer_id)},
        )

    async def get_servers(self, offer_id: int | str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/offers/servers",
            {"offerId": int(offer_id)},
        )

    async def check_game_data(
        self,
        offer_id: int | str,
        game_user_id: str,
        game_server_id: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "offerId": int(offer_id),
            "gameUserId": str(game_user_id).strip(),
        }

        if game_server_id:
            payload["gameServerId"] = str(game_server_id).strip()

        return await self._request(
            "POST",
            "/api/v1/offers/check-game-data",
            payload,
        )

    async def create_order(
        self,
        offer_id: int | str,
        price: float,
        transaction_id: str,
        game_user_id: str,
        game_server_id: Optional[str] = None,
        email: Optional[str] = None,
    ) -> dict[str, Any]:
        customer: dict[str, Any] = {
            "gameUserId": str(game_user_id).strip(),
        }

        if game_server_id:
            customer["gameServerId"] = str(game_server_id).strip()

        if email:
            customer["email"] = email

        payload = {
            "offerId": int(offer_id),
            "price": float(price),
            "transactionId": str(transaction_id),
            "customer": customer,
        }

        return await self._request(
            "POST",
            "/api/v1/offers/create-order",
            payload,
        )

    async def get_order_status(self, transaction_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/offers/order-status",
            {"transactionId": str(transaction_id)},
        )

    async def close(self):
        await self._client.aclose()


gamedrops_client = GameDropsClient()
