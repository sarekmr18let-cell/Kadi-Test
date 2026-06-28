(function (root) {
  function normalizeAdminNumber(raw, { allowEmpty = false, min = null } = {}) {
    const text = String(raw ?? '').replace(/[\s\u00A0]+/g, '');
    if (!text && allowEmpty) return null;
    if (!text) throw new Error('admin_invalid_number');
    const value = Number(text);
    if (!Number.isFinite(value)) throw new Error('admin_invalid_number');
    if (min !== null && value < min) throw new Error('admin_invalid_number');
    return value;
  }

  function getAdminProductPriceRange(product = {}, { formatMoney = (v, c) => `${v} ${c}`, noActiveText = 'admin_no_active_variation_prices' } = {}) {
    const prices = (product.variations || [])
      .filter(v => v && v.is_active !== false && Number.isFinite(Number(v.price)) && Number(v.price) > 0)
      .map(v => Number(v.price))
      .sort((a, b) => a - b);
    if (!prices.length) return noActiveText;
    const min = prices[0];
    const max = prices[prices.length - 1];
    return min === max ? formatMoney(min, 'UZS') : `${formatMoney(min, 'UZS')} – ${formatMoney(max, 'UZS')}`;
  }

  function getAdminVariationRegion(variation = {}) {
    return variation?.provider_meta?.region || variation?.region || '';
  }

  function getProductRegionOptions(product = {}) {
    return Array.isArray(product.region_options) ? product.region_options.filter(r => r && r.code) : [];
  }

  function buildRegionTabs(product = {}, allLabel = 'All') {
    const options = getProductRegionOptions(product);
    if (!options.length) return [];
    return [{ code: 'all', label: allLabel }, ...options.map(r => ({ code: String(r.code), label: String(r.label || r.code) }))];
  }

  function variationMatchesRegion(variation = {}, region = 'all') {
    if (!region || region === 'all') return true;
    return getAdminVariationRegion(variation) === region;
  }

  const api = { normalizeAdminNumber, getAdminProductPriceRange, getAdminVariationRegion, getProductRegionOptions, buildRegionTabs, variationMatchesRegion };
  root.AdminCatalogUtils = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
