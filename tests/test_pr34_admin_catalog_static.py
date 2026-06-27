from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_admin_number_parser_accepts_regular_and_nbsp_spaces():
    source = read('webapp/js/app.js')
    assert 'function normalizeAdminNumber' in source
    assert "replace(/[\\s\\u00A0]+/g, '')" in source
    assert 'Number.isFinite' in source


def test_variation_save_is_single_guarded_patch_and_preserves_provider_mapping():
    source = read('webapp/js/app.js')
    body = source[source.index('async function saveVariation'):source.index('async function deleteVariation')]
    assert "if (btn?.disabled) return" in body
    assert "await api(variationId ? 'PATCH' : 'POST'" in body
    assert body.count('await api(') == 1
    assert 'provider_price' not in body
    assert 'provider_meta' not in body
    assert 'provider_variation_id' in body


def test_backend_patch_uses_exclude_unset_and_does_not_clear_provider_fields():
    source = read('backend/app/api/admin.py')
    assert '@router.patch("/variations/{variation_id}"' in source
    assert 'model_dump(exclude_unset=True)' in source
    update_body = source[source.index('async def update_product_variation'):source.index('@router.patch("/variations/{variation_id}"')]
    assert 'model_dump(exclude_unset=True)' in update_body
    assert '_prepare_variation_payload' in update_body


def test_admin_catalog_hierarchy_and_gamedrops_provider_label():
    source = read('webapp/js/app.js')
    assert 'renderAdminCategories' in source
    assert 'selectAdminCategory' in source
    assert 'renderAdminProductDetail' in source
    assert "if (provider === 'gamedrops') return 'GameDrops'" in source
    assert 'MooGold variation:' not in source[source.index('function renderAdminVariationRow'):source.index('function selectAdminCategory')]


def test_ru_uz_en_admin_keys_present():
    source = read('webapp/js/i18n.js')
    for key in ['admin_catalog_search', 'admin_provider_price', 'admin_cost_price', 'admin_profit', 'admin_margin', 'admin_variation_saved', 'admin_provider_variation_required', 'admin_no_active_variation_prices']:
        assert source.count(key) >= 3


def test_category_product_variation_disable_routes_exist():
    source = read('backend/app/api/admin.py')
    for route in [
        '@router.post("/categories")', '@router.put("/categories/{category_id}"', '@router.delete("/categories/{category_id}"',
        '@router.post("/products")', '@router.put("/products/{product_id}"', '@router.delete("/products/{product_id}"',
        '@router.post("/products/{product_id}/variations"', '@router.patch("/variations/{variation_id}"', '@router.delete("/variations/{variation_id}"',
    ]:
        assert route in source
