import hmac
import hashlib
import time
import json
import httpx
from typing import Optional, Dict, Any

from app.core.config import settings


class MooGoldClient:
    def __init__(self):
        self.base_url = settings.MOOGOLD_BASE_URL.rstrip("/")
        self.partner_id = settings.MOOGOLD_PARTNER_ID
        self.secret_key = settings.MOOGOLD_SECRET_KEY
        self._client = httpx.AsyncClient(timeout=30.0)
    
    def _generate_auth(self, payload: dict, path: str) -> tuple[int, str]:
        timestamp = int(time.time())
        payload_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        string_to_sign = f"{payload_str}{timestamp}{path}"
        signature = hmac.new(
            self.secret_key.encode(),
            string_to_sign.encode(),
            hashlib.sha256
        ).hexdigest()
        return timestamp, signature
    
    def _get_basic_auth(self) -> str:
        import base64
        credentials = f"{self.partner_id}:{self.secret_key}"
        return base64.b64encode(credentials.encode()).decode()
    
    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict] = None
    ) -> dict:
        if settings.MOOGOLD_TEST_MODE:
            fake_id_source = (data or {}).get("partnerOrderId") or (data or {}).get("partner_order_id") or int(time.time())
            if "balance" in path:
                return {"status": True, "balance": "999999.00", "currency": "USD", "test_mode": True}
            if "list_product" in path:
                return []
            return {
                "status": True,
                "message": "MOOGOLD_TEST_MODE: fake response, no real request was sent",
                "order_id": f"TEST-{fake_id_source}",
                "data": {"path": path, "test_mode": True},
            }

        url = f"{self.base_url}/{path.lstrip('/')}"
        
        payload = {
            "path": path,
            **(data or {})
        }
        
        timestamp, signature = self._generate_auth(payload, path)
        
        headers = {
            "Authorization": f"Basic {self._get_basic_auth()}",
            "auth": signature,
            "timestamp": str(timestamp),
            "Content-Type": "application/json",
        }
        
        response = await self._client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    
    async def create_order(
        self,
        category: int,
        product_id: int,
        quantity: int,
        user_id: str,
        server: Optional[str] = None,
        partner_order_id: Optional[str] = None
    ) -> dict:
        data = {
            "data": {
                "category": category,
                "product-id": product_id,
                "quantity": quantity,
                "User ID": user_id,
            }
        }
        if server:
            data["data"]["Server"] = server
        if partner_order_id:
            data["partnerOrderId"] = partner_order_id
        
        return await self._request("POST", "order/create_order", data)
    
    async def get_order_detail(self, order_id: int) -> dict:
        return await self._request(
            "POST",
            "order/order_detail",
            {"order_id": order_id}
        )
    
    async def get_order_by_partner_id(self, partner_order_id: str) -> dict:
        return await self._request(
            "POST",
            "order/order_detail_partner_id",
            {"partner_order_id": partner_order_id}
        )
    
    async def get_transaction_history(
        self,
        start_date: str,
        end_date: str,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> dict:
        data = {
            "start_date": start_date,
            "end_date": end_date,
            "page": page,
            "limit": limit,
        }
        if status:
            data["status"] = status
        return await self._request("POST", "order/transaction_history", data)
    
    async def list_products(self, category_id: int) -> list:
        result = await self._request(
            "POST",
            "product/list_product",
            {"category_id": category_id}
        )
        return result if isinstance(result, list) else []
    
    async def get_product_detail(self, product_id: int) -> dict:
        return await self._request(
            "POST",
            "product/product_detail",
            {"product_id": product_id}
        )
    
    async def get_server_list(self, product_id: int) -> dict:
        return await self._request(
            "POST",
            "product/server_list",
            {"product_id": product_id}
        )
    
    async def validate_product(
        self,
        product_id: str,
        user_id: str,
        server: Optional[str] = None
    ) -> dict:
        data = {
            "data": {
                "product-id": product_id,
                "User ID": user_id,
            }
        }
        if server:
            data["data"]["Server"] = server
        return await self._request("POST", "product/validate", data)
    
    async def get_balance(self) -> dict:
        return await self._request("POST", "user/balance", {})
    
    async def reload_balance(self, amount: float, payment_method: str = "usdt-trc20-payment-gateway") -> dict:
        return await self._request(
            "POST",
            "user/reload_balance",
            {
                "payment_method": payment_method,
                "amount": str(amount),
            }
        )
    
    async def close(self):
        await self._client.aclose()


moogold_client = MooGoldClient()
