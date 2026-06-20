from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.models import ProductVariation
from app.services.gamedrops import GameDropsClient, GameDropsError, GameDropsNotConfigured


router = APIRouter()


def normalize_provider(value: Optional[str]) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )


def is_gamedrops_provider(value: Optional[str]) -> bool:
    return normalize_provider(value) in {"gamedrops", "gamesdrop", "gamedrop"}


def extract_gamedrops_nickname(data: dict[str, Any]) -> Optional[str]:
    candidates = [
        data.get("gameUserLogin"),
        data.get("nickname"),
        data.get("name"),
        data.get("username"),
        data.get("player_name"),
        data.get("playerName"),
    ]

    nested = data.get("data")
    if isinstance(nested, dict):
        candidates.extend(
            [
                nested.get("gameUserLogin"),
                nested.get("nickname"),
                nested.get("name"),
                nested.get("username"),
                nested.get("player_name"),
                nested.get("playerName"),
            ]
        )

    for candidate in candidates:
        if candidate:
            nickname = str(candidate).strip()
            if nickname:
                return nickname

    return None


def is_unsupported_gamedrops_error(exc: GameDropsError) -> bool:
    message = str(exc).lower()
    unsupported_markers = (
        "unsupported",
        "not supported",
        "not available",
        "verification unavailable",
        "не поддерж",
        "недоступ",
    )
    return any(marker in message for marker in unsupported_markers)


class VerifyMLBBRequest(BaseModel):
    variation_id: int = Field(..., description="KADI product_variations.id")
    user_id: str = Field(..., min_length=3, max_length=64)
    server_id: str = Field(..., min_length=1, max_length=64)


class VerifyGameDropsRequest(BaseModel):
    variation_id: int = Field(..., description="KADI product_variations.id")
    user_id: str = Field(..., min_length=1, max_length=64)
    server_id: Optional[str] = Field(default=None, max_length=64)
    region: Optional[str] = Field(default=None, max_length=100)


class VerifyMLBBResponse(BaseModel):
    valid: bool
    status: str
    nickname: Optional[str] = None
    variation_id: int
    provider_variation_id: Optional[str] = None
    message: Optional[str] = None
    raw: dict[str, Any] = {}


class VerifyGameDropsResponse(VerifyMLBBResponse):
    supported: bool = True


async def get_active_variation(
    db: AsyncSession,
    variation_id: int,
) -> Optional[ProductVariation]:
    result = await db.execute(
        select(ProductVariation)
        .options(selectinload(ProductVariation.product))
        .where(
            ProductVariation.id == variation_id,
            ProductVariation.is_active == True,
        )
    )
    return result.scalar_one_or_none()


def unsupported_response(
    payload: VerifyGameDropsRequest,
    message: str,
    variation: Optional[ProductVariation] = None,
) -> VerifyGameDropsResponse:
    return VerifyGameDropsResponse(
        supported=False,
        valid=False,
        status="UNSUPPORTED",
        nickname=None,
        variation_id=variation.id if variation else payload.variation_id,
        provider_variation_id=getattr(variation, "provider_variation_id", None),
        message=message,
        raw={},
    )


async def verify_gamedrops_payload(
    payload: VerifyGameDropsRequest,
    db: AsyncSession,
    *,
    strict_errors: bool = False,
) -> VerifyGameDropsResponse:
    variation = await get_active_variation(db, payload.variation_id)

    if not variation:
        if strict_errors:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пакет не найден или отключён",
            )
        return unsupported_response(payload, "Пакет не найден или отключён")

    product_provider = getattr(getattr(variation, "product", None), "provider", None)

    if not (
        is_gamedrops_provider(variation.provider)
        or is_gamedrops_provider(product_provider)
    ):
        if strict_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для этого пакета GameDrops-проверка недоступна",
            )
        return unsupported_response(
            payload,
            "Для этого пакета GameDrops-проверка недоступна",
            variation,
        )

    if not variation.provider_variation_id:
        if strict_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="У пакета не настроен GameDrops ID",
            )
        return unsupported_response(
            payload,
            "У пакета не настроен GameDrops ID",
            variation,
        )

    client = GameDropsClient()

    try:
        data = await client.check_game_data(
            offer_id=variation.provider_variation_id,
            game_user_id=payload.user_id,
            game_server_id=payload.server_id,
        )
    except GameDropsNotConfigured:
        if strict_errors:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="GameDrops API token не настроен",
            )
        return unsupported_response(
            payload,
            "GameDrops API token не настроен",
            variation,
        )
    except GameDropsError as exc:
        if not strict_errors and is_unsupported_gamedrops_error(exc):
            return unsupported_response(
                payload,
                "GameDrops-проверка для этого пакета недоступна",
                variation,
            )

        if strict_errors:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ошибка GameDrops: {exc}",
            )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка GameDrops: {exc}",
        )
    finally:
        await client.close()

    provider_status = (
        str(data.get("status") or "").upper() if isinstance(data, dict) else ""
    )
    nickname = extract_gamedrops_nickname(data) if isinstance(data, dict) else None
    valid = provider_status == "VALID"

    return VerifyGameDropsResponse(
        supported=True,
        valid=valid,
        status=provider_status or "UNKNOWN",
        nickname=nickname,
        variation_id=variation.id,
        provider_variation_id=variation.provider_variation_id,
        message=None if valid else data.get("message") or "Неверный User ID или Server ID",
        raw=data if isinstance(data, dict) else {},
    )


@router.post("/gamedrops", response_model=VerifyGameDropsResponse)
async def verify_gamedrops_account(
    payload: VerifyGameDropsRequest,
    db: AsyncSession = Depends(get_db),
):
    return await verify_gamedrops_payload(payload, db, strict_errors=False)


@router.post("/mlbb", response_model=VerifyMLBBResponse)
async def verify_mlbb_account(
    payload: VerifyMLBBRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await verify_gamedrops_payload(
        VerifyGameDropsRequest(
            variation_id=payload.variation_id,
            user_id=payload.user_id,
            server_id=payload.server_id,
        ),
        db,
        strict_errors=True,
    )

    return VerifyMLBBResponse(
        valid=result.valid,
        status=result.status,
        nickname=result.nickname,
        variation_id=result.variation_id,
        provider_variation_id=result.provider_variation_id,
        message=result.message,
        raw=result.raw,
    )
