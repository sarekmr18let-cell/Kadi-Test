from typing import Any


def is_public_product_visible(product: Any) -> bool:
    if not product:
        return False
    if getattr(product, "is_active", True) is not True:
        return False
    if getattr(product, "availability_status", "available") == "hidden":
        return False
    category = getattr(product, "category", None)
    if category is not None and getattr(category, "is_active", True) is not True:
        return False
    return True
