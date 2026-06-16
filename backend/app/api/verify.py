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


class VerifyMLBBRequest(BaseModel):
    variation_id: int = Field(..., description="KADI product_variations.id")
    user_id: str = Field(..., min_length=3, max_length=64)
    server_id: str = Field(..., min_length=1, max_length=64)


class VerifyMLBBResponse(BaseModel):
    valid: bool
    status: str
    nickname: Optional[str] = None
    variation_id: int
    provider_variation_id: Optional[str] = None
    message: Optional[str] = None
    raw: dict[str, Any] = {}


@router.post("/mlbb", response_model=VerifyMLBBResponse)
async def verify_mlbb_account(
    payload: VerifyMLBBRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProductVariation)
        .options(selectinload(ProductVariation.product))
        .where(
            ProductVariation.id == payload.variation_id,
            ProductVariation.is_active == True,
        )
    )
    variation = result.scalar_one_or_none()

    if not variation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пакет не найден или отключён",
        )

    if variation.provider != "gamedrops":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для этого пакета GameDrops-проверка недоступна",
        )

    if not variation.provider_variation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У пакета не настроен GameDrops ID",
        )

    client = GameDropsClient()

    try:
        data = await client.check_game_data(
            offer_id=variation.provider_variation_id,
            game_user_id=payload.user_id,
            game_server_id=payload.server_id,
        )
    except GameDropsNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GameDrops API token не настроен",
        )
    except GameDropsError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ошибка GameDrops: {exc}",
        )
    finally:
        await client.close()

    provider_status = str(data.get("status") or "").upper()
    nickname = (
        data.get("gameUserLogin")
        or data.get("nickname")
        or data.get("name")
        or data.get("username")
    )

    valid = provider_status == "VALID"

    return VerifyMLBBResponse(
        valid=valid,
        status=provider_status or "UNKNOWN",
        nickname=str(nickname) if nickname else None,
        variation_id=variation.id,
        provider_variation_id=variation.provider_variation_id,
        message=None if valid else data.get("message") or "Неверный User ID или Server ID",
        raw=data if isinstance(data, dict) else {},
    )
