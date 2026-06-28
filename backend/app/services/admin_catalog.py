import json
import math
from typing import Any, Optional


class AdminCatalogValidationError(ValueError):
    pass


ALLOWED_VARIATION_PROVIDERS = {"manual", "gamedrops", "moogold"}


def normalize_variation_provider(provider: Optional[str]) -> str:
    value = (provider or "manual").strip().lower()
    if value not in ALLOWED_VARIATION_PROVIDERS:
        raise AdminCatalogValidationError("Invalid provider")
    return value


def normalize_provider_variation_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def product_region_options(product: Any) -> list[dict[str, str]]:
    raw = getattr(product, "region_options", None)
    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        return []
    options = []
    for item in raw:
        if isinstance(item, dict) and item.get("code"):
            code = str(item["code"]).strip()
            if code:
                options.append({"code": code, "label": str(item.get("label") or code)})
    return options


def allowed_region_codes(product: Any) -> set[str]:
    return {item["code"] for item in product_region_options(product)}


def normalize_variation_region(region: Optional[str], product: Any = None, *, required: bool = False) -> Optional[str]:
    if region is None:
        if required:
            raise AdminCatalogValidationError("Region is required")
        return None
    value = str(region).strip()
    if not value:
        if required:
            raise AdminCatalogValidationError("Region is required")
        return None
    codes = allowed_region_codes(product) if product is not None else set()
    if codes and value not in codes:
        raise AdminCatalogValidationError("Invalid region")
    return value


def validate_variation_numbers(payload: dict, *, require_price: bool = False) -> None:
    if require_price and ("price" not in payload or payload.get("price") is None):
        raise AdminCatalogValidationError("Price is required")
    if "price" in payload:
        price = payload.get("price")
        if price is None or not math.isfinite(float(price)) or float(price) <= 0:
            raise AdminCatalogValidationError("Price must be greater than 0")
    if "cost_price" in payload and payload.get("cost_price") is not None:
        cost = float(payload["cost_price"])
        if not math.isfinite(cost) or cost < 0:
            raise AdminCatalogValidationError("Cost price must be non-negative")
    if "provider_price" in payload and payload.get("provider_price") is not None:
        provider_price = float(payload["provider_price"])
        if not math.isfinite(provider_price) or provider_price < 0:
            raise AdminCatalogValidationError("Provider price must be non-negative")


def prepare_variation_payload(
    payload: dict,
    *,
    product: Any = None,
    existing: Any = None,
    require_price: bool = False,
) -> dict:
    payload = dict(payload)
    region_supplied = "region" in payload
    region_value = payload.pop("region", None)
    provider = normalize_variation_provider(payload.get("provider") or getattr(existing, "provider", None))
    if "provider" in payload:
        payload["provider"] = provider
    if "provider_variation_id" in payload:
        payload["provider_variation_id"] = normalize_provider_variation_id(payload.get("provider_variation_id"))
    validate_variation_numbers(payload, require_price=require_price)
    if "sort_order" in payload and payload["sort_order"] is not None:
        payload["sort_order"] = int(payload["sort_order"])
    provider_variation_id = payload.get("provider_variation_id") if "provider_variation_id" in payload else getattr(existing, "provider_variation_id", None)
    base_meta = dict(getattr(existing, "provider_meta", None) or {})
    incoming_meta = payload.pop("provider_meta", None)
    if isinstance(incoming_meta, dict):
        base_meta.update(incoming_meta)
    requires_region = bool(getattr(product, "requires_region", False))
    if region_supplied:
        normalized = normalize_variation_region(region_value, product, required=requires_region or provider == "gamedrops")
        if normalized:
            base_meta["region"] = normalized
        else:
            base_meta.pop("region", None)
    elif require_price and (requires_region or provider == "gamedrops"):
        normalize_variation_region(base_meta.get("region"), product, required=True)
    if provider == "gamedrops":
        if not provider_variation_id:
            raise AdminCatalogValidationError("provider_variation_id is required for GameDrops")
        region = normalize_variation_region(base_meta.get("region"), product, required=True)
        if region:
            base_meta["region"] = region
            if not region_supplied and incoming_meta is None and (payload.get("provider") == "gamedrops"):
                payload["provider_meta"] = base_meta
    if region_supplied or incoming_meta is not None:
        payload["provider_meta"] = base_meta
    return payload


def assert_unique_provider_variation_mapping(conflicting_variation: Any, *, exclude_variation_id: Optional[int] = None) -> None:
    if conflicting_variation is None:
        return
    if exclude_variation_id is not None and getattr(conflicting_variation, "id", None) == exclude_variation_id:
        return
    raise AdminCatalogValidationError("GameDrops provider_variation_id is already linked to another variation")


def apply_category_update(existing: Any, payload: dict) -> Any:
    for key, value in payload.items():
        setattr(existing, key, value)
    return existing
