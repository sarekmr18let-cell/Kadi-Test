from pathlib import Path
from types import SimpleNamespace
import importlib.util
import subprocess
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalog_visibility', ROOT / 'backend/app/services/catalog_visibility.py')
catalog_visibility = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog_visibility)


def product(category=None, is_active=True, availability_status='available'):
    return SimpleNamespace(category=category, is_active=is_active, availability_status=availability_status)


def test_active_category_product_is_public():
    assert catalog_visibility.is_public_product_visible(product(SimpleNamespace(is_active=True))) is True


def test_disabled_category_product_hidden_from_public_and_checkout():
    disabled = product(SimpleNamespace(is_active=False))
    assert catalog_visibility.is_public_product_visible(disabled) is False


def test_uncategorized_product_remains_public_when_active():
    assert catalog_visibility.is_public_product_visible(product(None)) is True


def test_hidden_or_inactive_product_not_public():
    assert catalog_visibility.is_public_product_visible(product(None, is_active=False)) is False
    assert catalog_visibility.is_public_product_visible(product(None, availability_status='hidden')) is False


def test_public_routes_and_orders_use_visibility_helper():
    products_source = (ROOT / 'backend/app/api/products.py').read_text(encoding='utf-8')
    orders_source = (ROOT / 'backend/app/api/orders.py').read_text(encoding='utf-8')
    admin_source = (ROOT / 'backend/app/api/admin.py').read_text(encoding='utf-8')
    assert 'is_public_product_visible' in products_source
    assert 'is_public_product_visible(v.product)' in orders_source
    assert 'is_public_product_visible' not in admin_source[admin_source.index('@router.get("/products"'):admin_source.index('@router.post("/products")')]


def test_region_required_translations_are_dynamic():
    script = r'''
const fs = require('fs');
const vm = require('vm');
const sandbox = { window: {}, document: { documentElement: {}, querySelectorAll: () => [], getElementById: () => null }, localStorage: { getItem: () => null, setItem: () => {} }, CustomEvent: function CustomEvent() {} };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync('webapp/js/i18n.js', 'utf8'), sandbox);
const dict = sandbox.window.I18N.dict;
const vals = [dict.ru.admin_region_required, dict.en.admin_region_required, dict.uz.admin_region_required];
if (vals[0] !== 'Выберите допустимый регион товара') process.exit(1);
if (vals[1] !== 'Select a valid product region') process.exit(2);
if (vals[2] !== 'Mahsulot uchun mavjud regionni tanlang') process.exit(3);
if (vals.some(v => /global|ru/i.test(v))) process.exit(4);
'''
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True)
