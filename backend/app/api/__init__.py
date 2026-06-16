from .auth import router as auth
from .products import router as products
from .orders import router as orders
from .payments import router as payments
from .users import router as users
from .admin import router as admin
from .moogold_proxy import router as moogold_proxy
from .webhook import router as webhook

__all__ = ["auth", "products", "orders", "payments", "users", "admin", "moogold_proxy", "webhook", "verify"]

from .verify import router as verify
