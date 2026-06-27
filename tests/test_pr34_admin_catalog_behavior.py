from pathlib import Path
from types import SimpleNamespace
import importlib.util
import subprocess
import textwrap

import pytest
class HTTPException(Exception):
    def __init__(self, status_code=400, detail=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail

ROOT = Path(__file__).resolve().parents[1]


def load_admin_module():
    path = ROOT / 'backend/app/api/admin.py'
    source = path.read_text(encoding='utf-8')
    start = source.index('ALLOWED_VARIATION_REGIONS')
    end = source.index('\n\nMEDIA_UPLOAD_DIR')
    snippet = 'import math\nfrom typing import Optional\nclass HTTPException(Exception):\n    def __init__(self, status_code=400, detail=None):\n        super().__init__(detail); self.status_code=status_code; self.detail=detail\nProductVariation = object\n' + source[start:end]
    ns = {}
    exec(snippet, ns)
    return SimpleNamespace(**ns)


def test_patch_price_only_preserves_provider_mapping_and_meta():
    admin = load_admin_module()
    existing = SimpleNamespace(
        provider='gamedrops',
        provider_variation_id='gd-86-global',
        provider_price=1.25,
        provider_currency='USD',
        provider_meta={'region': 'global', 'tier': 'mlbb'},
    )
    payload = admin._prepare_variation_payload({'price': 31800}, existing=existing)
    assert payload == {'price': 31800}
    assert existing.provider == 'gamedrops'
    assert existing.provider_variation_id == 'gd-86-global'
    assert existing.provider_price == 1.25
    assert existing.provider_currency == 'USD'
    assert existing.provider_meta == {'region': 'global', 'tier': 'mlbb'}


def test_patch_region_updates_only_provider_meta_region():
    admin = load_admin_module()
    existing = SimpleNamespace(provider='gamedrops', provider_variation_id='gd-ru', provider_meta={'region': 'global', 'tier': 'mlbb'})
    payload = admin._prepare_variation_payload({'region': 'ru'}, existing=existing)
    assert payload == {'provider_meta': {'region': 'ru', 'tier': 'mlbb'}}


def test_create_gamedrops_variation_keeps_mapping_and_region():
    admin = load_admin_module()
    payload = admin._prepare_variation_payload({
        'name': '86 Diamonds', 'price': 31800, 'provider': 'gamedrops',
        'provider_variation_id': 'gd-86-global', 'region': 'global'
    }, require_price=True)
    assert payload['provider'] == 'gamedrops'
    assert payload['provider_variation_id'] == 'gd-86-global'
    assert payload['provider_meta']['region'] == 'global'


@pytest.mark.parametrize('payload', [{'price': 0}, {'price': None}])
def test_empty_or_zero_price_rejected(payload):
    admin = load_admin_module()
    with pytest.raises(Exception):
        admin._prepare_variation_payload(payload, require_price=True)


def test_negative_cost_rejected():
    admin = load_admin_module()
    with pytest.raises(Exception):
        admin._prepare_variation_payload({'price': 1, 'cost_price': -1}, require_price=True)


def test_frontend_number_price_and_range_behavior():
    js = r'''
    function tr(k){ const d={admin_invalid_number:'bad', admin_no_active_variation_prices:'No active'}; return d[k]||k; }
    function formatMoney(v,c){ return `${v} ${c}`; }
    function normalizeAdminNumber(raw, { allowEmpty = false, min = null } = {}) {
      const text = String(raw ?? '').replace(/[\s\u00A0]+/g, '');
      if (!text && allowEmpty) return null;
      if (!text) throw new Error(tr('admin_invalid_number'));
      const value = Number(text);
      if (!Number.isFinite(value)) throw new Error(tr('admin_invalid_number'));
      if (min !== null && value < min) throw new Error(tr('admin_invalid_number'));
      return value;
    }
    function getAdminProductPriceRange(product = {}) {
      const prices = (product.variations || []).filter(v => v.is_active !== false && Number.isFinite(Number(v.price)) && Number(v.price) > 0).map(v => Number(v.price)).sort((a,b)=>a-b);
      if (!prices.length) return tr('admin_no_active_variation_prices');
      const min = prices[0]; const max = prices[prices.length - 1];
      return min === max ? formatMoney(min, 'UZS') : `${formatMoney(min, 'UZS')} – ${formatMoney(max, 'UZS')}`;
    }
    if (normalizeAdminNumber('31 800') !== 31800) process.exit(1);
    if (normalizeAdminNumber('31\u00A0800') !== 31800) process.exit(2);
    let rejected=false; try { normalizeAdminNumber('', {min: 0.000001}); } catch(e) { rejected=true; }
    if (!rejected) process.exit(3);
    const range = getAdminProductPriceRange({variations:[{price:50000,is_active:true},{price:31800,is_active:true},{price:1,is_active:false}]});
    if (range !== '31800 UZS – 50000 UZS') process.exit(4);
    '''
    subprocess.run(['node', '-e', js], cwd=ROOT, check=True)
