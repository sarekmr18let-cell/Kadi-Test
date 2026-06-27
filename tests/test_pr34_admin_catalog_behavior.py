from types import SimpleNamespace
import asyncio
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / 'backend/app/services/admin_catalog.py'
spec = importlib.util.spec_from_file_location('admin_catalog_service', SERVICE_PATH)
admin_catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(admin_catalog)


def product(region_options=None, requires_region=False):
    return SimpleNamespace(region_options=json.dumps(region_options or []), requires_region=requires_region)


def test_price_only_patch_preserves_provider_mapping_and_meta():
    existing = SimpleNamespace(
        provider='gamedrops', provider_variation_id='gd-86-global', provider_price=1.25,
        provider_currency='USD', provider_meta={'region': 'global', 'tier': 'mlbb'}
    )
    payload = admin_catalog.prepare_variation_payload({'price': 31800}, product=product([{'code': 'global', 'label': 'Global'}]), existing=existing)
    assert payload == {'price': 31800}
    assert existing.provider_meta == {'region': 'global', 'tier': 'mlbb'}


def test_region_update_preserves_other_provider_meta_keys():
    existing = SimpleNamespace(provider='gamedrops', provider_variation_id='gd-ru', provider_meta={'region': 'global', 'tier': 'mlbb'})
    payload = admin_catalog.prepare_variation_payload({'region': 'ru'}, product=product([{'code': 'global', 'label': 'Global'}, {'code': 'ru', 'label': 'Россия'}]), existing=existing)
    assert payload == {'provider_meta': {'region': 'ru', 'tier': 'mlbb'}}


def test_create_gamedrops_variation_keeps_mapping_and_region():
    payload = admin_catalog.prepare_variation_payload({
        'name': '86 Diamonds', 'price': 31800, 'provider': 'gamedrops',
        'provider_variation_id': ' gd-86-global ', 'region': 'global'
    }, product=product([{'code': 'global', 'label': 'Global'}], requires_region=True), require_price=True)
    assert payload['provider'] == 'gamedrops'
    assert payload['provider_variation_id'] == 'gd-86-global'
    assert payload['provider_meta']['region'] == 'global'


def test_dynamic_region_options_are_product_specific():
    pubg = product([{'code': 'eu', 'label': 'Europe'}], requires_region=True)
    assert admin_catalog.prepare_variation_payload({'price': 1, 'region': 'eu'}, product=pubg, require_price=True)['provider_meta']['region'] == 'eu'
    with pytest.raises(admin_catalog.AdminCatalogValidationError):
        admin_catalog.prepare_variation_payload({'price': 1, 'region': 'global'}, product=pubg, require_price=True)


def test_product_without_regions_does_not_get_global_automatically():
    payload = admin_catalog.prepare_variation_payload({'price': 100, 'provider': 'manual'}, product=product(), require_price=True)
    assert 'provider_meta' not in payload


@pytest.mark.parametrize('payload', [{'price': 0}, {'price': None}])
def test_empty_or_zero_price_rejected(payload):
    with pytest.raises(admin_catalog.AdminCatalogValidationError):
        admin_catalog.prepare_variation_payload(payload, require_price=True)


def test_negative_cost_rejected():
    with pytest.raises(admin_catalog.AdminCatalogValidationError):
        admin_catalog.prepare_variation_payload({'price': 1, 'cost_price': -1}, require_price=True)


def test_frontend_utils_execute_production_code():
    js = r'''
    const utils = require('./webapp/js/admin-catalog-utils.js');
    function formatMoney(v,c){ return `${v} ${c}`; }
    if (utils.normalizeAdminNumber('31 800') !== 31800) process.exit(1);
    if (utils.normalizeAdminNumber('31\u00A0800') !== 31800) process.exit(2);
    let rejected=false; try { utils.normalizeAdminNumber('', {min: 0.000001}); } catch(e) { rejected=true; }
    if (!rejected) process.exit(3);
    const range = utils.getAdminProductPriceRange({variations:[{price:50000,is_active:true},{price:31800,is_active:true},{price:1,is_active:false}]}, {formatMoney, noActiveText:'No active'});
    if (range !== '31800 UZS – 50000 UZS') process.exit(4);
    const tabs = utils.buildRegionTabs({region_options:[{code:'global',label:'Global'}, {code:'ru', label:'Россия'}]}, 'Все');
    if (tabs.length !== 3 || tabs[1].code !== 'global' || tabs[2].label !== 'Россия') process.exit(5);
    if (!utils.variationMatchesRegion({provider_meta:{region:'ru'}}, 'ru')) process.exit(6);
    if (utils.variationMatchesRegion({provider_meta:{region:'global'}}, 'ru')) process.exit(7);
    '''
    subprocess.run(['node', '-e', js], cwd=ROOT, check=True)


class FakeResult:
    def __init__(self, item): self.item = item
    def scalar_one_or_none(self): return self.item


class FakeDb:
    def __init__(self, item): self.item = item
    async def execute(self, query): return FakeResult(self.item)



def test_manual_to_gamedrops_with_id_but_without_region_is_rejected():
    existing = SimpleNamespace(provider='manual', provider_variation_id=None, provider_meta={})
    with pytest.raises(admin_catalog.AdminCatalogValidationError):
        admin_catalog.prepare_variation_payload(
            {'provider': 'gamedrops', 'provider_variation_id': 'gd-new'},
            product=product([{'code': 'global', 'label': 'Global'}], requires_region=True),
            existing=existing,
        )


def test_manual_to_gamedrops_without_id_is_rejected():
    existing = SimpleNamespace(provider='manual', provider_variation_id=None, provider_meta={'region': 'global'})
    with pytest.raises(admin_catalog.AdminCatalogValidationError):
        admin_catalog.prepare_variation_payload(
            {'provider': 'gamedrops'},
            product=product([{'code': 'global', 'label': 'Global'}], requires_region=True),
            existing=existing,
        )


def test_correct_gamedrops_price_only_patch_still_passes():
    existing = SimpleNamespace(provider='gamedrops', provider_variation_id='gd-ok', provider_meta={'region': 'ru', 'keep': 'yes'})
    payload = admin_catalog.prepare_variation_payload(
        {'price': 42000},
        product=product([{'code': 'global', 'label': 'Global'}, {'code': 'ru', 'label': 'Россия'}], requires_region=True),
        existing=existing,
    )
    assert payload == {'price': 42000}


def test_duplicate_mapping_production_helper_rejects_other_and_allows_current():
    other = SimpleNamespace(id=22)
    with pytest.raises(admin_catalog.AdminCatalogValidationError):
        admin_catalog.assert_unique_provider_variation_mapping(other, exclude_variation_id=11)
    assert admin_catalog.assert_unique_provider_variation_mapping(other, exclude_variation_id=22) is None


def test_category_update_without_moogold_id_preserves_existing_value():
    category = SimpleNamespace(name='Old', slug='old', icon='🎮', sort_order=1, moogold_id=777)
    admin_catalog.apply_category_update(category, {'name': 'New', 'slug': 'new'})
    assert category.name == 'New'
    assert category.slug == 'new'
    assert category.moogold_id == 777


def test_uncategorized_category_has_no_management_actions():
    source = (ROOT / 'webapp/js/app.js').read_text(encoding='utf-8')
    assert "c.id === '__none__' ? ''" in source
    assert "disableCategory('__none__')" not in source
    assert "showCategoryModal('__none__')" not in source
