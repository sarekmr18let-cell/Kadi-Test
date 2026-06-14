from fastapi import APIRouter, Depends, HTTPException
from app.core.security import get_current_admin
from app.services.moogold import moogold_client
from app.schemas.schemas import MooGoldCreateOrderRequest

router = APIRouter()


@router.post("/order")
async def proxy_create_order(
    request: MooGoldCreateOrderRequest,
    admin: dict = Depends(get_current_admin)
):
    """Proxy order creation to MooGold (admin only)."""
    result = await moogold_client.create_order(
        category=request.category,
        product_id=request.product_id,
        quantity=request.quantity,
        user_id=request.user_id,
        server=request.server,
        partner_order_id=request.partner_order_id,
    )
    return result


@router.post("/order-detail")
async def proxy_order_detail(
    order_id: int,
    admin: dict = Depends(get_current_admin)
):
    """Get MooGold order detail (admin only)."""
    if order_id <= 0:
        raise HTTPException(status_code=400, detail="order_id must be greater than 0")
    result = await moogold_client.get_order_detail(order_id)
    return result


@router.post("/products")
async def proxy_list_products(
    category_id: int,
    admin: dict = Depends(get_current_admin)
):
    """List MooGold products (admin only)."""
    if category_id <= 0:
        raise HTTPException(status_code=400, detail="category_id must be greater than 0")
    result = await moogold_client.list_products(category_id)
    return result


@router.post("/product-detail")
async def proxy_product_detail(
    product_id: int,
    admin: dict = Depends(get_current_admin)
):
    """Get MooGold product detail (admin only)."""
    if product_id <= 0:
        raise HTTPException(status_code=400, detail="product_id must be greater than 0")
    result = await moogold_client.get_product_detail(product_id)
    return result


@router.post("/balance")
async def proxy_balance(admin: dict = Depends(get_current_admin)):
    """Get MooGold wallet balance (admin only)."""
    result = await moogold_client.get_balance()
    return result
