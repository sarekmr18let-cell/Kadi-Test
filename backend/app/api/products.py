from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
import json

from app.core.database import get_db
from app.models.models import Product, Category
from app.schemas.schemas import (
    ProductResponse,
    ProductListItem,
    CategoryResponse,
)

router = APIRouter()


def product_to_list_item(product: Product, category_slug: str | None = None) -> ProductListItem:
    min_price = min(
        [v.price for v in product.variations if v.is_active],
        default=0.0,
    )
    return ProductListItem(
        id=product.id,
        name=product.name,
        image_url=product.image_url,
        min_price=min_price,
        category_id=product.category_id,
        category_slug=category_slug or (product.category.slug if product.category else ""),
        target_type=product.target_type or "game_id",
        requires_target_id=bool(product.requires_target_id),
        requires_server_id=bool(product.requires_server_id),
        requires_region=bool(product.requires_region),
    )


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category)
        .where(Category.is_active == True)
        .order_by(Category.sort_order)
    )
    return result.scalars().all()


@router.get("", response_model=List[ProductListItem])
async def list_products(
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if search and len(search) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query too long (max 100 characters)",
        )

    query = (
        select(Product)
        .options(selectinload(Product.variations), selectinload(Product.category))
        .where(Product.is_active == True)
    )

    if category_id:
        query = query.where(Product.category_id == category_id)

    if search:
        query = query.where(Product.name.ilike(f"%{search}%"))

    result = await db.execute(query.order_by(Product.sort_order))
    products = result.scalars().all()
    return [product_to_list_item(product) for product in products]


# Keep this route before /{product_id}; otherwise /category/{slug} can be captured by /{product_id}.
@router.get("/category/{slug}", response_model=List[ProductListItem])
async def get_products_by_category(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Category).where(Category.slug == slug, Category.is_active == True)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    result = await db.execute(
        select(Product)
        .options(selectinload(Product.variations), selectinload(Product.category))
        .where(
            Product.category_id == category.id,
            Product.is_active == True,
        )
        .order_by(Product.sort_order)
    )
    products = result.scalars().all()
    return [product_to_list_item(product, slug) for product in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.variations), selectinload(Product.category))
        .where(Product.id == product_id, Product.is_active == True)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
