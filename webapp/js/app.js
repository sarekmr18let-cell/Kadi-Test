/**
 * KADI Mini App
 * Telegram WebApp + FastAPI backend integration
 */

// ===== Configuration =====
const API_BASE = window.location.origin.includes('localhost') 
    ? 'http://localhost:8000/api' 
    : `${window.location.origin}/api`;


// ===== i18n helpers =====
const tr = (key, params = {}) => window.I18N?.t(key, params) || key;
const applyTranslations = (root = document) => window.I18N?.apply(root);

function initLanguageSwitcher() {
    const toggle = document.getElementById('language-toggle');
    const current = document.getElementById('language-current');
    const menu = document.getElementById('language-menu');
    const options = menu ? Array.from(menu.querySelectorAll('[data-lang]')) : [];
    const selector = document.getElementById('language-select');

    const getCurrentLang = () => window.I18N?.getLang?.() || 'ru';
    const setCurrentLabel = (lang = getCurrentLang()) => {
        const normalized = String(lang || 'ru').toLowerCase();
        const label = normalized.toUpperCase();

        if (current) current.textContent = label;
        if (selector) selector.value = normalized;
        options.forEach((option) => {
            const isActive = option.dataset.lang === normalized;
            option.classList.toggle('active', isActive);
            option.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
    };
    const closeMenu = () => {
        if (!menu || !toggle) return;
        menu.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
    };

    setCurrentLabel();

    if (toggle && menu) {
        toggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = menu.classList.toggle('open');
            toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });

        options.forEach((option) => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                const lang = option.dataset.lang;
                if (!lang) return;
                window.I18N?.setLang(lang);
                setCurrentLabel(lang);
                closeMenu();
            });
        });

        document.addEventListener('click', closeMenu);
    }

    if (selector) {
        selector.addEventListener('change', (e) => window.I18N?.setLang(e.target.value));
    }

    window.addEventListener('languageChanged', () => {
        setCurrentLabel();
        applyTranslations(document);
        refreshCurrentPageText();
        if (tg && tg.MainButton) tg.MainButton.hide();
    });
}

function refreshCurrentPageText() {
    try {
        if (state.currentPage === 'home') loadHomePage();
        if (state.currentPage === 'catalog') loadCatalogPage();
        if (state.currentPage === 'cart') loadCartPage();
        if (state.currentPage === 'checkout') loadОплатаPage();
        if (state.currentPage === 'orders') loadOrdersPage();
        if (state.currentPage === 'profile') loadProfilePage();
        if (state.currentPage === 'admin') loadAdminPage();
    } catch (e) { console.warn('Failed to refresh translations:', e); }
}

// ===== State =====
const state = {
    user: null,
    token: null,
    cart: [],
    categories: [],
    products: [],
    orders: [],
    topups: [],
    historyTab: "orders",
    paymentMethods: [],
    promo: null,
    currentPage: 'home',
    telegramUser: null,
};

// Safe localStorage initialization
try {
    state.token = localStorage.getItem('access_token');
    const cartRaw = localStorage.getItem('cart');
    state.cart = cartRaw ? JSON.parse(cartRaw) : [];
} catch (e) {
    console.warn('localStorage unavailable or corrupted:', e);
    state.token = null;
    state.cart = [];
}

// ===== Telegram WebApp =====
let tg = null;

function initTelegram() {
    if (window.Telegram?.WebApp) {
        tg = window.Telegram.WebApp;
        tg.ready();
        tg.expand();
        
        // Set theme
        const theme = tg.themeParams;
        if (theme) {
            document.documentElement.style.setProperty('--bg-primary', theme.bg_color || '#0a0a1a');
            document.documentElement.style.setProperty('--text-primary', theme.text_color || '#f8fafc');
        }
        
        // Back button handler
        tg.BackButton.onClick(() => {
            if (state.currentPage === 'product' || state.currentPage === 'checkout' || state.currentPage === 'order-detail') {
                navigateTo('catalog');
            } else if (state.currentPage === 'admin') {
                navigateTo('profile');
            } else {
                navigateTo('home');
            }
        });
        
        // Use in-app buttons for cart/product/checkout; keep Telegram SDK but hide its MainButton.
        if (tg.MainButton) tg.MainButton.hide();
        
        state.telegramUser = tg.initDataUnsafe?.user;
        
        // Authenticate with backend
        authenticate();
    } else {
        // Not in Telegram - dev mode
        console.log('Not running in Telegram WebApp');
        showToast('warning', tr('dev_mode'));
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('main-content').classList.remove('hidden');
        loadHomePage();
    }
}

// ===== API Client =====
async function api(method, path, body = null) {
    const url = `${API_BASE}${path}`;
    const headers = {
        'Content-Type': 'application/json',
    };
    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }
    
    const options = { method, headers };
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    try {
        const response = await fetch(url, options);
        if (response.status === 401) {
            clearAuth();
            authenticate();
            return null;
        }
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || tr('request_failed'));
        }
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast('error', error.message);
        throw error;
    }
}

// ===== Auth =====
async function authenticate() {
    if (!tg?.initData) {
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('main-content').classList.remove('hidden');
        return;
    }
    
    try {
        const result = await api('POST', '/auth/telegram', {
            init_data: tg.initData,
        });
        
        if (result) {
            state.token = result.access_token;
            safeSet('access_token', result.access_token);
            safeSet('refresh_token', result.refresh_token);
            
            // Get user profile
            const profile = await api('GET', '/auth/me');
            state.user = profile;
    applyTelegramAvatarPhoto(profile);
            
            // Show admin button if admin
            if (profile?.is_admin) {
                document.getElementById('admin-panel-btn').classList.remove('hidden');
            }
            
            document.getElementById('loading-screen').classList.add('hidden');
            document.getElementById('main-content').classList.remove('hidden');
            
            loadHomePage();
            updateCartBadge();
        }
    } catch (error) {
        console.error('Auth error:', error);
        document.getElementById('loading-screen').classList.add('hidden');
        document.getElementById('main-content').classList.remove('hidden');
    }
}

// ===== Navigation =====
function navigateTo(page, data = null) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    
    // Show target page
    const targetPage = document.getElementById(`page-${page}`);
    if (targetPage) {
        targetPage.classList.add('active');
    }
    
    // Update nav
    const navItem = document.querySelector(`.nav-item[data-page="${page}"]`);
    if (navItem) {
        navItem.classList.add('active');
    }
    
    state.currentPage = page;
    document.body.dataset.currentPage = page;
    
    // Update Telegram buttons
    if (tg) {
        if (page === 'home') {
            tg.BackButton.hide();
        } else {
            tg.BackButton.show();
        }
        
        if (tg.MainButton) tg.MainButton.hide();
    }
    
    // Load page data
    switch (page) {
        case 'home':
            loadHomePage();
            break;
        case 'catalog':
            loadCatalogPage();
            break;
        case 'cart':
            loadCartPage();
            break;
        case 'checkout':
            loadОплатаPage();
            break;
        case 'orders':
            loadOrdersPage();
            break;
        case 'profile':
            loadProfilePage();
            break;
        case 'admin':
            loadAdminPage();
            break;
    }
    
    // Scroll to top
    window.scrollTo(0, 0);
}


async function updateHeaderBalance() {
    const el = document.getElementById('header-balance');
    if (!el || !state.token) return;
    try {
        const balance = await api('GET', '/users/balance');
        const formatted = formatMoney(balance?.balance || 0, 'UZS');
        el.textContent = formatted;
        const homeBalance = document.getElementById('home-balance-value');
        if (homeBalance) homeBalance.textContent = formatted;
    } catch (error) {
        // Header balance must never block the UI.
    }
}

function productFallbackVisual(name = 'KADI') {
    return `<div class="kadi-product-fallback" aria-label="${escapeHtml(name || 'KADI')}">
        <span class="kadi-product-fallback-mark">K</span>
        <span class="kadi-product-fallback-name">KADI</span>
    </div>`;
}

function productVisual(name, imageUrl = null) {
    const src = String(imageUrl || '').trim();
    const fallback = productFallbackVisual(name);

    if (src) {
        return `<div class="kadi-product-visual">
            <img class="kadi-product-img" src="${escapeHtml(src)}" alt="KADI" loading="lazy">
            <div class="kadi-product-fallback-wrap hidden">${fallback}</div>
        </div>`;
    }

    return fallback;
}


function getProductDetailImageUrl(product = {}) {
    const name = String(product.name || '').toLowerCase();
    if (name.includes('mobile legends') || name.includes('mlbb')) {
        return '/assets/products/mobile-legends-next-icon-512.webp';
    }
    return product.image_url || null;
}

function variationThumbnailVisual(product = {}, variation = {}) {
    const src = String(
        variation.image_url ||
        variation.image ||
        variation.icon ||
        variation.thumbnail_url ||
        getProductDetailImageUrl(product) ||
        ''
    ).trim();

    if (src) {
        return `<div class="variation-thumb">
            <img src="${escapeHtml(src)}" alt="" loading="lazy">
        </div>`;
    }

    return `<div class="variation-thumb variation-thumb-fallback">
        ${productFallbackVisual(product.name || variation.name || 'KADI')}
    </div>`;
}

function hydrateProductVisuals(root = document) {
    root.querySelectorAll('.kadi-product-visual').forEach(visual => {
        const img = visual.querySelector('.kadi-product-img');
        const fallback = visual.querySelector('.kadi-product-fallback-wrap');
        if (!img || !fallback) return;

        const showFallback = () => {
            img.classList.add('hidden');
            fallback.classList.remove('hidden');
        };

        img.addEventListener('error', showFallback, { once: true });

        if (img.complete && img.naturalWidth === 0) {
            showFallback();
        }
    });
}

function productBadge(name) {
    const n = String(name || '').toLowerCase();
    if (n.includes('telegram') || n.includes('stars') || n.includes('premium')) return 'Telegram';
    if (n.includes('mobile') || n.includes('legend') || n.includes('mlbb')) return 'MLBB';
    if (n.includes('pubg')) return 'PUBG';
    if (n.includes('free')) return 'Free Fire';
    return 'Game';
}

// ===== Home Page =====
async function loadHomePage() {
    try {
        updateHeaderBalance();
        const [categories, products] = await Promise.all([
            api('GET', '/products/categories'),
            api('GET', '/products'),
        ]);

        state.categories = categories || [];
        state.products = products || [];

        renderCategories(state.categories);
    } catch (error) {
        console.error('Home page error:', error);
    }
}

function renderCategories(categories) {
    const grid = document.getElementById('categories-grid');
    if (!grid || !categories) return;

    const icons = {
        'telegram': '⭐',
        'games': '🎮',
        'game': '🎮',
        'gift-cards': '🎁',
        'streaming': '📺',
        'music': '🎵',
        'premium': '💎',
    };

    const categoryIconVisual = (cat) => {
        const rawIcon = String(cat.icon || '').trim();
        const fallback = icons[cat.slug] || '🎮';
        const value = rawIcon || fallback;
        const isImage = value.startsWith('/') || value.startsWith('http://') || value.startsWith('https://');

        if (isImage) {
            return `<img src="${escapeHtml(value)}" alt="${escapeHtml(cat.name)}" loading="lazy" style="width:64px;height:64px;object-fit:cover;border-radius:16px;display:block;margin:0 auto 2px;box-shadow:0 0 18px rgba(6,182,212,.22);">`;
        }

        return escapeHtml(value);
    };
    
    grid.innerHTML = categories.map(cat => `
        <div class="category-card" data-category="${cat.id}">
            <div class="icon">${categoryIconVisual(cat)}</div>
            <div class="name">${escapeHtml(cat.name)}</div>
            <div class="category-hint">${tr('open')}</div>
        </div>
    `).join('');
    
    grid.querySelectorAll('.category-card').forEach(card => {
        card.addEventListener('click', () => {
            const categoryId = Number(card.dataset.category);
            const categoryProducts = state.products.filter(
                product => Number(product.category_id) === categoryId
            );

            if (categoryProducts.length === 1) {
                openProductDetail(categoryProducts[0].id);
                return;
            }

            navigateTo('catalog');
            filterCatalogByCategory(categoryId);
        });
    });
}

function renderPopularProducts(products) {
    const container = document.getElementById('popular-products');
    if (!container || !products) return;
    
    container.innerHTML = products.map(p => `
        <div class="product-card" data-id="${p.id}">
            <div class="image">${productVisual(p.name, p.image_url)}</div>
            <div class="info">
                <div class="product-badge">${productBadge(p.name)}</div>
                <div class="name">${escapeHtml(p.name)}</div>
                <div class="price">${tr('from')} ${formatMoney(p.min_price, 'UZS')}</div>
            </div>
        </div>
    `).join('');
    
    hydrateProductVisuals(container);

    container.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('click', () => {
            openProductDetail(parseInt(card.dataset.id));
        });
    });
}

// ===== Catalog Page =====
async function loadCatalogPage() {
    try {
        // Load categories for tabs
        const categories = await api('GET', '/products/categories');
        renderCategoryTabs(categories);
        
        // Load all products
        const products = await api('GET', '/products');
        renderCatalogProducts(products);
    } catch (error) {
        console.error('Catalog error:', error);
    }
}

function renderCategoryTabs(categories) {
    const tabs = document.getElementById('category-tabs');
    if (!tabs || !categories) return;
    
    tabs.innerHTML = `
        <button class="tab active" data-category="all">${tr('all')}</button>
        ${categories.map(cat => `
            <button class="tab" data-category="${cat.id}">${escapeHtml(cat.name)}</button>
        `).join('')}
    `;
    
    tabs.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const catId = tab.dataset.category;
            if (catId === 'all') {
                renderCatalogProducts(state.products);
            } else {
                filterCatalogByCategory(parseInt(catId));
            }
        });
    });
}

function filterCatalogByCategory(categoryId) {
    const filtered = state.products.filter(p => Number(p.category_id) === Number(categoryId));
    renderCatalogProducts(filtered);
}

function renderCatalogProducts(products) {
    const grid = document.getElementById('catalog-products');
    if (!grid) return;
    
    if (!products || products.length === 0) {
        grid.innerHTML = `<div class="text-center" style="padding: 40px; color: var(--text-muted);">${tr('products_not_found')}</div>`;
        return;
    }
    
    grid.innerHTML = products.map(p => `
        <div class="product-card" data-id="${p.id}">
            <div class="image">${productVisual(p.name, p.image_url)}</div>
            <div class="info">
                <div class="product-badge">${productBadge(p.name)}</div>
                <div class="name">${escapeHtml(p.name)}</div>
                <div class="price">${tr('from')} ${formatMoney(p.min_price, 'UZS')}</div>
            </div>
        </div>
    `).join('');
    
    hydrateProductVisuals(grid);

    grid.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('click', () => {
            openProductDetail(parseInt(card.dataset.id));
        });
    });
}

// ===== Product Detail =====
async function openProductDetail(productId) {
    const product = state.products.find(p => p.id === productId);
    if (!product) return;
    
    // Get full product details
    try {
        const details = await api('GET', `/products/${productId}`);
        renderProductDetail(details);
        navigateTo('product');
    } catch (error) {
        showToast('error', tr('failed_load_product'));
    }
}

function renderProductDetail(product) {
    const content = document.getElementById('product-detail-content');
    if (!content) return;
    state.currentProductDetail = product;

    const allVariations = product.variations || [];
    const regions = Array.isArray(product.region_options) ? product.region_options : [];
    const firstRegion = regions[0]?.code || '';

    const targetTypePlaceholder = product.target_type === 'telegram_username'
        ? tr('target_username_placeholder')
        : tr('target_id_placeholder');

    function getVariationRegion(variation) {
        const meta = variation.provider_meta || {};
        return String(meta.region || '').toLowerCase();
    }

    function getFilteredVariations(regionCode) {
        const hasRegionMeta = allVariations.some(v => !!getVariationRegion(v));

        if (!product.requires_region || !hasRegionMeta) {
            return allVariations;
        }

        const code = String(regionCode || '').toLowerCase();

        if (!code) {
            return [];
        }

        return allVariations.filter(v => getVariationRegion(v) === code);
    }

    function getProductVerificationKey() {
        const name = String(product.name || '').toLowerCase();
        const meta = product.provider_meta || {};
        const providerName = String(meta.game || meta.game_name || meta.slug || meta.code || '').toLowerCase();
        const source = `${name} ${providerName}`;

        if (source.includes('mobile legends') || source.includes('mlbb')) return 'mlbb';
        if (source.includes('pubg')) return 'pubg';
        if (source.includes('free fire')) return 'free_fire';
        if (source.includes('genshin')) return 'genshin';
        if (source.includes('magic chess')) return 'magic_chess';
        if (source.includes('honor of kings')) return 'honor_of_kings';

        return 'generic';
    }

    function normalizeProvider(value) {
        return String(value || '').trim().toLowerCase().replace(/[\s_-]+/g, '');
    }

    function isGameDropsProvider(value) {
        return ['gamedrops', 'gamesdrop', 'gamedrop'].includes(normalizeProvider(value));
    }

    function hasProviderOfferId(variation) {
        return !!String(variation?.provider_variation_id || '').trim();
    }

    function hasAccountRequirements() {
        return !!(product.requires_target_id || product.requires_server_id || product.requires_region);
    }

    function isStrictVerificationProduct() {
        const mode = String(product.provider_meta?.verification_mode || '').trim().toLowerCase();
        if (mode === 'strict') return true;
        if (mode === 'fallback' || mode === 'fallback_friendly') return false;

        return getProductVerificationKey() === 'mlbb';
    }

    function shouldAttemptProviderVerification(variation) {
        return !!(
            variation &&
            (isGameDropsProvider(variation.provider) || isGameDropsProvider(product.provider)) &&
            hasProviderOfferId(variation) &&
            product.requires_target_id &&
            hasAccountRequirements()
        );
    }

    function supportsRealVerification(variation) {
        return shouldAttemptProviderVerification(variation);
    }

    function canFallbackAfterUnsupported() {
        return !isStrictVerificationProduct();
    }

    function requiresStrictVerification() {
        return isStrictVerificationProduct() && hasAccountRequirements();
    }

    function canUseFallbackVerification() {
        return canFallbackAfterUnsupported() && hasAccountRequirements();
    }

    content.innerHTML = `
        <div class="product-compact-hero">
            <div class="product-compact-cover">
                ${productVisual(product.name, getProductDetailImageUrl(product))}
            </div>
            <div class="product-compact-copy">
                <div class="product-compact-kicker">Top-up checkout</div>
                <h1 class="product-name">${escapeHtml(product.name)}</h1>
                <p class="product-description">${escapeHtml(product.description || tr('default_description'))}</p>
            </div>
        </div>

        <div class="product-requirements">
            <div class="product-block-title">Данные аккаунта</div>
            ${product.input_help_text ? `<div class="requirement-help">${escapeHtml(product.input_help_text)}</div>` : ''}
            ${(product.requires_target_id || product.requires_server_id) ? `
                <div id="last-account-chip" class="last-account-chip hidden"></div>
            ` : ''}
            ${product.requires_target_id ? `
                <div class="form-group">
                    <label>${escapeHtml(product.target_id_label || tr('player_id_label'))}</label>
                    <input type="text" id="product-target-id" placeholder="${escapeHtml(targetTypePlaceholder)}">
                </div>
            ` : ''}
            ${product.requires_server_id ? `
                <div class="form-group">
                    <label>${escapeHtml(product.target_server_label || 'Server ID')}</label>
                    <input type="text" id="product-target-server" placeholder="${tr('enter_server_id')}">
                </div>
            ` : ''}
            ${product.requires_region ? `
                <div class="form-group">
                    <label>${escapeHtml(product.target_region_label || tr('target_region'))}</label>
                    <div class="region-chips" id="product-region-chips">
                        ${regions.map((r, i) => `
                            <button type="button" class="region-chip ${i === 0 ? 'selected' : ''}" data-code="${escapeHtml(r.code)}" data-label="${escapeHtml(r.label)}">
                                ${escapeHtml(r.label)}
                            </button>
                        `).join('') || '<div class="requirement-help">Регионы не настроены админом</div>'}
                    </div>
                </div>
            ` : ''}

            ${(product.requires_target_id || product.requires_server_id || product.requires_region) ? `
                ${hasAccountRequirements() ? `
                    <button type="button" class="btn-secondary" id="verify-mlbb-btn" style="width:100%; margin-top:10px;">
                        🔍 Проверить ID
                    </button>
                ` : ''}
                <div id="verify-mlbb-status" class="requirement-help" style="margin-top:10px;">
                    ${isStrictVerificationProduct() ? 'Сначала выберите пакет и проверьте User ID / Server ID.' : 'Введите ID'}
                </div>
            ` : ''}
        </div>

        <h3 class="product-section-title">${tr('choose_package')}</h3>
        <div class="variation-group-tabs hidden" id="variation-group-tabs"></div>
        <div class="variations-list" id="product-variations-list"></div>

        <div class="quantity-selector">
            <button id="qty-minus">−</button>
            <div class="value" id="qty-value">1</div>
            <button id="qty-plus">+</button>
        </div>

        <button class="btn-primary btn-glow" id="add-to-cart-btn" disabled>
            ${tr('add_to_cart')}
        </button>

        <div class="product-sticky-bar hidden" id="product-sticky-bar">
            <div class="product-sticky-info">
                <span id="sticky-variation-name">${tr('choose_package')}</span>
                <strong id="sticky-variation-price">—</strong>
            </div>
            <button class="btn-primary" id="sticky-add-to-cart-btn" disabled>${tr('choose_package')}</button>
        </div>
    `;

    hydrateProductVisuals(content);

    let selectedVariation = null;
    let selectedVariationGroup = '';
    let selectedRegion = firstRegion;
    let selectedRegionLabel = regions[0]?.label || '';
    let quantity = 1;
    let verificationState = 'idle';
    let verifiedTarget = null;
    let verifyDebounceTimer = null;
    let verifyRequestSeq = 0;
    const AUTO_VERIFY_DELAY = 800;

    const variationsList = content.querySelector('#product-variations-list');
    const variationGroupTabs = content.querySelector('#variation-group-tabs');
    const addButton = content.querySelector('#add-to-cart-btn');
    const verifyButton = content.querySelector('#verify-mlbb-btn');
    const verifyStatus = content.querySelector('#verify-mlbb-status');
    const targetIdInput = content.querySelector('#product-target-id');
    const targetServerInput = content.querySelector('#product-target-server');

    const lastAccountChip = content.querySelector('#last-account-chip');
    const stickyBar = content.querySelector('#product-sticky-bar');
    const stickyName = content.querySelector('#sticky-variation-name');
    const stickyPrice = content.querySelector('#sticky-variation-price');
    const stickyAddButton = content.querySelector('#sticky-add-to-cart-btn');
    const lastAccountKey = `kadi:last-account:${product.id}`;

    function readLastAccount() {
        try { return JSON.parse(localStorage.getItem(lastAccountKey) || 'null'); } catch (_) { return null; }
    }

    function saveLastAccount() {
        if (!product.requires_target_id && !product.requires_server_id && !product.requires_region) return;
        const data = {
            product_id: product.id,
            target_id: targetIdInput?.value.trim() || '',
            target_server: targetServerInput?.value.trim() || '',
            target_region: selectedRegion || '',
            target_region_label: selectedRegionLabel || '',
            verified_target_name: verifiedTarget?.nickname || '',
            verification_status: verificationState,
        };
        if (!data.target_id && !data.target_server) return;
        try { localStorage.setItem(lastAccountKey, JSON.stringify(data)); } catch (_) {}
    }

    function clearLastAccount() {
        try { localStorage.removeItem(lastAccountKey); } catch (_) {}
        if (lastAccountChip) lastAccountChip.classList.add('hidden');
    }

    function renderLastAccountChip(saved) {
        if (!lastAccountChip || !saved || (!saved.target_id && !saved.target_server)) return;
        const title = saved.verified_target_name || 'Аккаунт';
        const target = [saved.target_id, saved.target_server].filter(Boolean).join(' / ');
        lastAccountChip.classList.remove('hidden');
        lastAccountChip.innerHTML = `
            <span>Последний аккаунт: <b>${escapeHtml(title)}</b> · ${escapeHtml(target)}</span>
            <button type="button" id="clear-last-account-btn">Очистить</button>
        `;
        lastAccountChip.querySelector('#clear-last-account-btn')?.addEventListener('click', () => {
            clearLastAccount();
            if (targetIdInput) targetIdInput.value = '';
            if (targetServerInput) targetServerInput.value = '';
            resetVerification('Аккаунт очищен. Введите ID заново.');
        });
    }

    function applyLastAccount() {
        const saved = readLastAccount();
        if (!saved || Number(saved.product_id) !== Number(product.id)) return;

        if (targetIdInput && saved.target_id) targetIdInput.value = saved.target_id;
        if (targetServerInput && saved.target_server) targetServerInput.value = saved.target_server;

        let regionChanged = false;
        if (product.requires_region && saved.target_region) {
            regionChanged = selectedRegion !== saved.target_region;
            selectedRegion = saved.target_region;
            selectedRegionLabel = saved.target_region_label || saved.target_region;
            content.querySelectorAll('.region-chip').forEach(chip => {
                chip.classList.toggle('selected', chip.dataset.code === selectedRegion);
            });
        }

        if (regionChanged) renderVariationList();
        renderLastAccountChip(saved);
        scheduleAutoVerification('Сохранённый аккаунт найден. Проверяем ID...');
    }

    function parseAccountNumbers(text) {
        return String(text || '').match(/\d+/g) || [];
    }

    function handleAccountPaste(event, activeInput) {
        const pasted = event.clipboardData?.getData('text') || '';
        const nums = parseAccountNumbers(pasted);
        if (nums.length >= 2 && targetIdInput && targetServerInput) {
            event.preventDefault();
            targetIdInput.value = nums[0];
            targetServerInput.value = nums[1];
            scheduleAutoVerification(supportsRealVerification(selectedVariation) ? 'ID и Server ID вставлены. Проверяем...' : 'ID и Server ID вставлены. Проверяем данные...');
            return;
        }
        if (nums.length === 1 && activeInput) {
            event.preventDefault();
            activeInput.value = nums[0];
            scheduleAutoVerification('Введите ID');
        }
    }


    function getVerificationInputValues() {
        return {
            targetId: targetIdInput?.value.trim() || '',
            targetServer: targetServerInput?.value.trim() || '',
            targetRegion: selectedRegion || '',
        };
    }

    function getMissingRequirement(values = getVerificationInputValues()) {
        if (product.requires_target_id && !values.targetId) {
            return { field: 'target_id', message: 'Введите ID' };
        }
        if (product.requires_server_id && !values.targetServer) {
            return { field: 'target_server', message: 'Введите Server ID' };
        }
        if (product.requires_region && !values.targetRegion) {
            return { field: 'target_region', message: 'Выберите сервер' };
        }
        return null;
    }

    function hasCompleteVerificationInputs() {
        return !getMissingRequirement();
    }

    function isTargetIdFormatValid(targetId) {
        const value = String(targetId || '').trim();
        if (!value) return false;

        const key = getProductVerificationKey();
        if (key === 'genshin') return /^\d{6,12}$/.test(value);
        if (['pubg', 'free_fire', 'honor_of_kings', 'magic_chess'].includes(key)) return /^[A-Za-z0-9_-]{3,32}$/.test(value);

        return value.length >= 3;
    }

    function renderVerificationStatus(status, options = {}) {
        verificationState = status;

        if (!verifyStatus) return;

        verifyStatus.style.color = '';
        verifyStatus.classList.remove('verification-status-success', 'verification-status-error', 'verification-status-muted');

        if (status === 'checking') {
            verifyStatus.textContent = 'Проверяем ID...';
            verifyStatus.classList.add('verification-status-muted');
            return;
        }

        if (status === 'verified') {
            verifyStatus.textContent = `✅ Игрок найден: ${options.nickname || 'аккаунт найден'}`;
            verifyStatus.style.color = '#22c55e';
            verifyStatus.classList.add('verification-status-success');
            return;
        }

        if (status === 'accepted_without_nickname') {
            verifyStatus.innerHTML = `
                <div class="verification-status-main">✅ ID принят</div>
                <div class="verification-status-hint">Проверка никнейма недоступна</div>
            `;
            verifyStatus.style.color = '#22c55e';
            verifyStatus.classList.add('verification-status-success');
            return;
        }

        if (status === 'error') {
            verifyStatus.textContent = options.message || 'Проверьте данные';
            verifyStatus.style.color = '#ef4444';
            verifyStatus.classList.add('verification-status-error');
            return;
        }

        verifyStatus.textContent = options.message || '';
        verifyStatus.classList.add('verification-status-muted');
    }

    function resetVerification(message = 'Введите ID') {
        verifyRequestSeq += 1;
        verifiedTarget = null;
        renderVerificationStatus('idle', { message });
        updateAddButtonState();
    }

    function clearAutoVerificationTimer() {
        if (verifyDebounceTimer) {
            clearTimeout(verifyDebounceTimer);
            verifyDebounceTimer = null;
        }
    }

    function acceptFallbackVerification() {
        const values = getVerificationInputValues();
        verifiedTarget = {
            nickname: '',
            status: 'accepted_without_nickname',
            supported: false,
            raw: {
                verification_status: 'accepted_without_nickname',
                message: 'Проверка никнейма недоступна',
                target_id: values.targetId || null,
                target_server: values.targetServer || null,
                target_region: values.targetRegion || null,
            },
        };
        renderVerificationStatus('accepted_without_nickname');
        saveLastAccount();
        renderLastAccountChip(readLastAccount());
        updateAddButtonState();
    }

    function validateFallbackVerification({ showErrors = false } = {}) {
        const values = getVerificationInputValues();
        const missing = getMissingRequirement(values);

        if (missing) {
            verifiedTarget = null;
            renderVerificationStatus(showErrors ? 'error' : 'idle', { message: missing.message });
            updateAddButtonState();
            return false;
        }

        if (product.requires_target_id && !isTargetIdFormatValid(values.targetId)) {
            verifiedTarget = null;
            renderVerificationStatus(showErrors ? 'error' : 'idle', { message: 'Введите ID' });
            updateAddButtonState();
            return false;
        }

        acceptFallbackVerification();
        return true;
    }

    function canAutoVerifySelectedVariation() {
        return !!selectedVariation && (supportsRealVerification(selectedVariation) || canUseFallbackVerification());
    }

    function scheduleAutoVerification(message = 'Введите ID') {
        clearAutoVerificationTimer();
        resetVerification(message);

        if (!selectedVariation) return;

        if (supportsRealVerification(selectedVariation)) {
            const missing = getMissingRequirement();
            if (missing) {
                renderVerificationStatus('idle', { message: missing.message });
                return;
            }

            verifyDebounceTimer = setTimeout(() => {
                verifyDebounceTimer = null;
                runIdVerification({ silent: true });
            }, AUTO_VERIFY_DELAY);
            return;
        }

        if (canUseFallbackVerification()) {
            validateFallbackVerification({ showErrors: false });
        }
    }

    function updateAddButtonState() {
        const hasVariation = !!selectedVariation;
        const inStock = hasVariation && selectedVariation.stock_status === 'instock';
        const missing = getMissingRequirement();
        const needsRealVerification = hasVariation && (supportsRealVerification(selectedVariation) || requiresStrictVerification());
        const needsFallback = hasVariation && !needsRealVerification && canUseFallbackVerification();
        const verificationAccepted = verificationState === 'verified' || verificationState === 'accepted_without_nickname';
        const blockedByVerification = (needsRealVerification || needsFallback) && !verificationAccepted;
        const disabled = !inStock || !!missing || verificationState === 'checking' || blockedByVerification;

        let text = tr('add_to_cart');
        if (!hasVariation) text = tr('choose_package');
        else if (!inStock) text = tr('out_of_stock');
        else if (missing) text = missing.message;
        else if (verificationState === 'checking') text = 'Проверяем ID...';
        else if (blockedByVerification) text = needsRealVerification ? 'Сначала проверьте ID' : 'Введите ID';

        addButton.disabled = disabled;
        addButton.textContent = text;

        if (stickyAddButton) {
            stickyAddButton.disabled = disabled;
            stickyAddButton.textContent = text;
        }
        if (stickyName) stickyName.textContent = selectedVariation?.name || tr('choose_package');
        if (stickyPrice) stickyPrice.textContent = selectedVariation ? formatMoney(selectedVariation.price, 'UZS') : '—';
        if (stickyBar) stickyBar.classList.toggle('hidden', !hasVariation);
    }


    // KADI_PRODUCT_GROUP_TABS_JS_START
    function getVariationGroupLabel(variation) {
        const meta = variation?.provider_meta || {};
        const productName = String(product?.name || '').toLowerCase();
        const variationName = String(variation?.name || '').toLowerCase();

        let group = String(
            meta.group ||
            meta.group_name ||
            meta.category ||
            meta.type ||
            ''
        ).trim();

        if (productName.includes('pubg')) {
            if (group === 'Prime' || group === 'Prime Plus' || group === 'Packs' || group === 'Наборы') {
                return 'Наборы';
            }
            if (!group) {
                return variationName.includes('uc') ? 'UC' : 'Наборы';
            }
            return group;
        }

        if (productName.includes('free fire')) {
            if (!group) {
                if (variationName.includes('diamond')) return 'Алмазы';
                if (variationName.includes('level')) return 'Уровни BP';
                return 'Пропуски';
            }

            if (group.toLowerCase().includes('diamond')) return 'Алмазы';
            if (group.toLowerCase().includes('level')) return 'Уровни BP';

            return group;
        }

        return group || 'Пакеты';
    }

    function getVariationGroupRank(group) {
        const productName = String(product?.name || '').toLowerCase();

        if (productName.includes('pubg')) {
            const order = ['UC', 'Наборы'];
            const index = order.indexOf(group);
            return index >= 0 ? index : 99;
        }

        if (productName.includes('free fire')) {
            const order = ['Алмазы', 'Пропуски', 'Уровни BP'];
            const index = order.indexOf(group);
            return index >= 0 ? index : 99;
        }

        if (productName.includes('genshin')) {
            const order = ['Genesis Crystals', 'Welkin Moon', 'Chronal Nexus'];
            const index = order.indexOf(group);
            return index >= 0 ? index : 99;
        }

        if (productName.includes('magic chess')) {
            const order = ['Diamonds', 'Cards', 'Packs'];
            const index = order.indexOf(group);
            return index >= 0 ? index : 99;
        }

        if (productName.includes('honor of kings')) {
            const order = ['Tokens', 'Cards', 'Packs'];
            const index = order.indexOf(group);
            return index >= 0 ? index : 99;
        }

        return 99;
    }

    function getVariationSortValue(variation) {
        const meta = variation?.provider_meta || {};
        const raw = meta.sort_order ?? variation?.sort_order ?? variation?.id ?? 999999;
        const value = Number(raw);
        return Number.isFinite(value) ? value : 999999;
    }

    function getAvailableVariationGroups(variations) {
        const groups = [];
        const seen = new Set();

        variations.forEach(variation => {
            const group = getVariationGroupLabel(variation);
            if (!seen.has(group)) {
                seen.add(group);
                groups.push(group);
            }
        });

        return groups.sort((a, b) => {
            const rankA = getVariationGroupRank(a);
            const rankB = getVariationGroupRank(b);
            if (rankA !== rankB) return rankA - rankB;
            return a.localeCompare(b);
        });
    }

    function renderVariationGroupTabs(groups) {
        if (!variationGroupTabs) return;

        if (!groups.length || groups.length <= 1) {
            variationGroupTabs.classList.add('hidden');
            variationGroupTabs.innerHTML = '';
            return;
        }

        variationGroupTabs.classList.remove('hidden');
        variationGroupTabs.innerHTML = groups.map(group => `
            <button type="button" class="variation-group-chip ${group === selectedVariationGroup ? 'selected' : ''}" data-group="${escapeHtml(group)}">
                ${escapeHtml(group)}
            </button>
        `).join('');

        variationGroupTabs.querySelectorAll('.variation-group-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                const nextGroup = chip.dataset.group || '';
                if (!nextGroup || nextGroup === selectedVariationGroup) return;

                selectedVariationGroup = nextGroup;
                renderVariationList();
            });
        });
    }
    // KADI_PRODUCT_GROUP_TABS_JS_END

    function renderVariationList() {
        const allFilteredVariations = getFilteredVariations(selectedRegion);
        const groups = getAvailableVariationGroups(allFilteredVariations);

        if (!allFilteredVariations.length) {
            selectedVariation = null;
            selectedVariationGroup = '';
            renderVariationGroupTabs([]);
            variationsList.innerHTML = `
                <div class="requirement-help" style="padding: 14px;">
                    Для выбранного региона пока нет доступных пакетов.
                </div>
            `;
            resetVerification('Для выбранного региона нет пакетов.');
            return;
        }

        if (!selectedVariationGroup || !groups.includes(selectedVariationGroup)) {
            selectedVariationGroup = groups[0] || '';
        }

        renderVariationGroupTabs(groups);

        const filteredVariations = allFilteredVariations
            .filter(v => !selectedVariationGroup || getVariationGroupLabel(v) === selectedVariationGroup)
            .sort((a, b) => getVariationSortValue(a) - getVariationSortValue(b));

        const hasStock = filteredVariations.some(v => v.stock_status === 'instock');

        if (!filteredVariations.length) {
            selectedVariation = null;
            variationsList.innerHTML = `
                <div class="requirement-help" style="padding: 14px;">
                    В этом разделе пока нет доступных пакетов.
                </div>
            `;
            resetVerification('В этом разделе нет пакетов.');
            return;
        }

        variationsList.innerHTML = filteredVariations.map((v, i) => `
            <div class="variation-item ${i === 0 ? 'selected' : ''}" data-id="${v.id}" data-price="${escapeHtml(v.price)}">
                ${variationThumbnailVisual(product, v)}
                <div class="info">
                    <div class="name">${escapeHtml(v.name)}</div>
                    <div class="stock">${v.stock_status === 'instock' ? tr('in_stock') : tr('out_of_stock')}</div>
                </div>
                <div class="price">${formatMoney(v.price, 'UZS')}</div>
            </div>
        `).join('');

        selectedVariation = filteredVariations[0] || null;

        variationsList.querySelectorAll('.variation-item').forEach(item => {
            item.addEventListener('click', () => {
                variationsList.querySelectorAll('.variation-item').forEach(i => i.classList.remove('selected'));
                item.classList.add('selected');
                selectedVariation = filteredVariations.find(v => v.id === parseInt(item.dataset.id));
                scheduleAutoVerification(supportsRealVerification(selectedVariation) ? 'Пакет изменён. Проверяем ID...' : 'Пакет изменён. Проверяем данные...');
            });
        });

        if (!hasStock) {
            addButton.disabled = true;
            addButton.textContent = tr('out_of_stock');
        } else {
            scheduleAutoVerification('Введите ID');
        }
    }

    content.querySelectorAll('.region-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            content.querySelectorAll('.region-chip').forEach(c => c.classList.remove('selected'));
            chip.classList.add('selected');
            selectedRegion = chip.dataset.code || '';
            selectedRegionLabel = chip.dataset.label || '';
            renderVariationList();
            scheduleAutoVerification(
                hasCompleteVerificationInputs()
                    ? (supportsRealVerification(selectedVariation) ? 'Регион изменён. Проверяем ID...' : 'Регион изменён. Проверяем данные...')
                    : 'Выберите сервер'
            );
        });
    });

    if (targetIdInput) {
        targetIdInput.addEventListener('input', () => scheduleAutoVerification('Введите ID'));
        targetIdInput.addEventListener('paste', (e) => handleAccountPaste(e, targetIdInput));
    }

    if (targetServerInput) {
        targetServerInput.addEventListener('input', () => scheduleAutoVerification('Введите Server ID'));
        targetServerInput.addEventListener('paste', (e) => handleAccountPaste(e, targetServerInput));
    }


    function getVerifiedNickname(result = {}) {
        const candidates = [
            result.nickname,
            result.gameUserLogin,
            result.username,
            result.player_name,
            result.playerName,
            result.name,
            result.data?.nickname,
            result.data?.gameUserLogin,
            result.data?.username,
            result.data?.player_name,
            result.data?.playerName,
            result.data?.name,
            result.raw?.nickname,
            result.raw?.gameUserLogin,
            result.raw?.username,
            result.raw?.player_name,
            result.raw?.playerName,
            result.raw?.name,
            result.raw?.data?.nickname,
            result.raw?.data?.gameUserLogin,
            result.raw?.data?.username,
            result.raw?.data?.player_name,
            result.raw?.data?.playerName,
            result.raw?.data?.name,
        ];

        return String(candidates.find(value => value) || '').trim();
    }

    async function runIdVerification({ silent = false } = {}) {
        clearAutoVerificationTimer();

        if (!selectedVariation) {
            if (!silent) showToast('error', 'Сначала выберите пакет');
            return;
        }

        if (!supportsRealVerification(selectedVariation)) {
            if (requiresStrictVerification()) {
                verifiedTarget = null;
                renderVerificationStatus('error', { message: 'Для этого пакета GameDrops-проверка недоступна' });
                updateAddButtonState();
                if (!silent) showToast('error', 'Для этого пакета GameDrops-проверка недоступна');
                return;
            }

            validateFallbackVerification({ showErrors: !silent });
            return;
        }

        const { targetId, targetServer } = getVerificationInputValues();
        const missing = getMissingRequirement();

        if (missing) {
            resetVerification(missing.message);
            if (!silent) showToast('error', missing.message);
            return;
        }

        const requestSeq = ++verifyRequestSeq;

        if (verifyButton) {
            verifyButton.disabled = true;
            verifyButton.textContent = 'Проверяем...';
        }
        if (verifyStatus) {
            renderVerificationStatus('checking');
            verifyStatus.style.color = '';
        }
        updateAddButtonState();

        try {
            const requestPayload = {
                variation_id: selectedVariation.id,
                user_id: targetId,
            };

            if (targetServer) requestPayload.server_id = targetServer;
            if (selectedRegion) requestPayload.region = selectedRegion;

            const result = await api('POST', '/verify/gamedrops', requestPayload);

            if (requestSeq !== verifyRequestSeq) return;

            if (result?.valid) {
                const nickname = getVerifiedNickname(result);
                verifiedTarget = {
                    nickname,
                    status: result.status || 'VALID',
                    supported: result.supported !== false,
                    raw: result.raw || {},
                };

                if (nickname) {
                    verificationState = 'verified';
                    renderVerificationStatus('verified', { nickname });
                    if (!silent) showToast('success', `ID подтверждён: ${nickname}`);
                } else if (isStrictVerificationProduct()) {
                    verificationState = 'verified';
                    renderVerificationStatus('verified', { nickname: 'аккаунт найден' });
                    if (!silent) showToast('success', 'ID подтверждён');
                } else {
                    acceptFallbackVerification();
                    return;
                }

                saveLastAccount();
                renderLastAccountChip(readLastAccount());
            } else if (
                result?.supported === false &&
                String(result?.status || '').toUpperCase() === 'UNSUPPORTED' &&
                canFallbackAfterUnsupported()
            ) {
                acceptFallbackVerification();
            } else {
                verifiedTarget = null;
                const message = result?.message || 'ID не найден / проверьте данные';
                renderVerificationStatus('error', { message });

                if (!silent) showToast('error', message);
            }
        } catch (error) {
            if (requestSeq !== verifyRequestSeq) return;

            verifiedTarget = null;
            renderVerificationStatus('error', { message: 'Ошибка проверки. Попробуйте ещё раз.' });
            if (!silent) showToast('error', 'Ошибка проверки. Попробуйте ещё раз.');
        } finally {
            if (requestSeq === verifyRequestSeq) {
                if (verifyButton) {
                    verifyButton.disabled = false;
                    verifyButton.textContent = '🔍 Проверить ID';
                }
                updateAddButtonState();
            }
        }
    }

    if (verifyButton) {
        verifyButton.addEventListener('click', () => runIdVerification({ silent: false }));
    }

    let qtyValue = document.getElementById('qty-value');
    document.getElementById('qty-minus').addEventListener('click', () => {
        if (quantity > 1) {
            quantity--;
            qtyValue.textContent = quantity;
        }
    });
    document.getElementById('qty-plus').addEventListener('click', () => {
        if (quantity < 10) {
            quantity++;
            qtyValue.textContent = quantity;
        }
    });

    document.getElementById('add-to-cart-btn').addEventListener('click', () => {
        if (!selectedVariation || selectedVariation.stock_status !== 'instock') return;

        const targetId = targetIdInput?.value.trim() || '';
        const targetServer = targetServerInput?.value.trim() || '';

        if (product.requires_target_id && !targetId) {
            showToast('error', `${product.target_id_label || 'User ID'} ${tr('required')}`);
            return;
        }
        if (product.requires_server_id && !targetServer) {
            showToast('error', `${product.target_server_label || 'Server ID'} ${tr('required')}`);
            return;
        }
        if (product.requires_region && !selectedRegion) {
            showToast('error', `${product.target_region_label || tr('target_region')} ${tr('required')}`);
            return;
        }

        if (requiresStrictVerification() && verificationState !== 'verified') {
            showToast('error', 'Дождитесь успешной проверки ID');
            return;
        }

        if (!isStrictVerificationProduct() && supportsRealVerification(selectedVariation) && !['verified', 'accepted_without_nickname'].includes(verificationState)) {
            showToast('error', 'Дождитесь проверки ID');
            return;
        }

        if (!supportsRealVerification(selectedVariation) && canUseFallbackVerification() && verificationState !== 'accepted_without_nickname') {
            if (!validateFallbackVerification({ showErrors: true })) {
                showToast('error', getMissingRequirement()?.message || 'Введите ID');
                return;
            }
        }

        saveLastAccount();
        addToCart({
            variation_id: selectedVariation.id,
            product_id: product.id,
            product_name: product.name,
            product_image_url: product.image_url || null,
            name: `${product.name} - ${selectedVariation.name}`,
            price: selectedVariation.price,
            quantity: quantity,
            target_id: targetId || null,
            target_server: targetServer || null,
            target_region: selectedRegion || null,
            target_region_label: selectedRegionLabel || null,
            verified_target_name: verifiedTarget?.nickname || null,
            verified_target_payload: verifiedTarget ? { ...verifiedTarget, verification_status: verificationState } : null,
            verification_status: verificationState,
            requirements: {
                target_type: product.target_type || 'game_id',
                requires_target_id: !!product.requires_target_id,
                requires_server_id: !!product.requires_server_id,
                requires_region: !!product.requires_region,
                target_id_label: product.target_id_label || tr('player_id_label'),
                target_server_label: product.target_server_label || 'Server ID',
                target_region_label: product.target_region_label || tr('target_region'),
            },
        });
    });

    stickyAddButton?.addEventListener('click', () => addButton.click());

    renderVariationList();
    applyLastAccount();
}

function getCartTargetInfo() {
    const first = state.cart[0] || {};
    return {
        target_id: first.target_id || '',
        target_server: first.target_server || '',
        target_region: first.target_region || '',
        target_region_label: first.target_region_label || '',
        verified_target_name: first.verified_target_name || '',
        requirements: first.requirements || {},
    };
}


function setTextIfExists(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setVisibleIfExists(id, isVisible) {
    const el = document.getElementById(id);
    if (el) el.style.display = isVisible ? '' : 'none';
}

function getCheckoutTotals() {
    const subtotal = state.cart.reduce((sum, item) => sum + (Number(item.price || 0) * Number(item.quantity || 0)), 0);
    const discount = Number(state.promo?.discount_amount || 0);
    const total = Math.max(0, subtotal - discount);
    const itemsCount = state.cart.reduce((sum, item) => sum + Number(item.quantity || 0), 0);

    return { subtotal, discount, total, itemsCount };
}

function updateCheckoutAmounts(balanceValue = null) {
    const { subtotal, discount, total, itemsCount } = getCheckoutTotals();
    const itemsLabel = tr('items_count', { count: itemsCount });

    setTextIfExists('checkout-items-count', itemsLabel);
    setTextIfExists('checkout-items-count-legacy', String(itemsCount));
    setTextIfExists('checkout-order-count', itemsLabel);

    setTextIfExists('checkout-subtotal', formatMoney(subtotal, 'UZS'));
    setTextIfExists('checkout-subtotal-legacy', formatMoney(subtotal, 'UZS'));

    setTextIfExists('checkout-discount', discount ? `-${formatMoney(discount, 'UZS')}` : formatMoney(0, 'UZS'));
    setTextIfExists('checkout-discount-legacy', formatMoney(discount, 'UZS'));

    setTextIfExists('checkout-total', formatMoney(total, 'UZS'));
    setTextIfExists('checkout-total-inline', formatMoney(total, 'UZS'));
    setTextIfExists('checkout-total-legacy', formatMoney(total, 'UZS'));

    setVisibleIfExists('checkout-discount-row', discount > 0);
    setVisibleIfExists('checkout-pay-grid', discount > 0);

    const placeBtn = document.getElementById('place-order-btn');
    if (placeBtn) {
        if (balanceValue !== null && Number(balanceValue || 0) < total) {
            placeBtn.textContent = tr('not_enough_topup');
        } else {
            placeBtn.textContent = tr('pay_amount', { amount: formatMoney(total, 'UZS') });
        }
    }
}

function updateCheckoutBalanceState(balanceValue = null) {
    const { total } = getCheckoutTotals();

    if (balanceValue === null || Number.isNaN(Number(balanceValue))) {
        setTextIfExists('checkout-balance-status', tr('checking'));
        setTextIfExists('checkout-balance-after', '—');
        return;
    }

    const balance = Number(balanceValue || 0);
    setTextIfExists('checkout-balance', formatMoney(balance, 'UZS'));

    if (balance >= total) {
        setTextIfExists('checkout-balance-status', tr('enough_balance'));
        setTextIfExists('checkout-balance-hint', tr('balance_after_payment'));
        setTextIfExists('checkout-balance-after', formatMoney(balance - total, 'UZS'));
    } else {
        setTextIfExists('checkout-balance-status', tr('not_enough_balance_short'));
        setTextIfExists('checkout-balance-hint', tr('topup_balance_before_buy'));
        setTextIfExists('checkout-balance-after', `-${formatMoney(total - balance, 'UZS')}`);
    }

    updateCheckoutAmounts(balance);
}

function renderCheckoutOrderItems() {
    const container = document.getElementById('checkout-order-items');
    if (!container) return;

    container.innerHTML = state.cart.map(item => {
        const productName = item.product_name || item.name || tr('product');
        const variationName = typeof getCartVariationName === 'function' ? getCartVariationName(item) : (item.name || '');
        const itemTotal = Number(item.price || 0) * Number(item.quantity || 0);

        return `
            <div class="checkout-order-item">
                <div>
                    <strong>${escapeHtml(productName)}</strong>
                    ${variationName ? `<span>${escapeHtml(variationName)}</span>` : ''}
                </div>
                <em>x${escapeHtml(item.quantity || 1)}</em>
                <b>${formatMoney(itemTotal, 'UZS')}</b>
            </div>
        `;
    }).join('');
}


function renderCartTargetSummary(item) {
    const bits = [];
    if (item.target_id) bits.push(`${escapeHtml(item.requirements?.target_id_label || 'ID')}: ${escapeHtml(item.target_id)}`);
    if (item.target_server) bits.push(`${escapeHtml(item.requirements?.target_server_label || 'Server')}: ${escapeHtml(item.target_server)}`);
    if (item.target_region_label || item.target_region) bits.push(`${escapeHtml(item.requirements?.target_region_label || tr('target_region'))}: ${escapeHtml(item.target_region_label || item.target_region)}`);
    return bits.length ? `<div class="meta target-summary">${bits.join(' • ')}</div>` : '';
}


function getCartItemImageUrl(item = {}) {
    const direct = String(item.image_url || item.variation_image_url || item.product_image_url || '').trim();
    if (direct) return direct;

    const label = String(`${item.product_name || ''} ${item.name || ''} ${item.variation_name || ''}`).toLowerCase();

    if (
        label.includes('mobile legends') ||
        label.includes('mlbb') ||
        label.includes('diamonds') ||
        label.includes('diamond')
    ) {
        return '/assets/products/mlbb-cart-icon.svg';
    }

    return null;
}


function getCartVariationName(item = {}) {
    const productName = String(item.product_name || '').trim();
    const fullName = String(item.name || '').trim();

    if (!fullName) return '';
    if (productName && fullName.toLowerCase().startsWith(`${productName.toLowerCase()} - `)) {
        return fullName.slice(productName.length + 3).trim();
    }
    if (productName && fullName.toLowerCase() === productName.toLowerCase()) return '';

    return fullName;
}

function renderCartMetaRow(label, value, extraClass = '') {
    const text = String(value || '').trim();
    if (!text) return '';
    return `<div class="cart-line ${extraClass}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(text)}</strong></div>`;
}


function isMlbbCartItem(item = {}, productName = '') {
    const label = String(`${item.product_name || ''} ${item.name || ''} ${item.variation_name || ''} ${productName || ''}`).toLowerCase();
    return label.includes('mobile legends') || label.includes('mlbb') || label.includes('diamonds') || label.includes('diamond');
}

function cartProductVisual(item = {}, productName = '', imageUrl = '') {
    if (isMlbbCartItem(item, productName)) {
        return `
            <div class="image cart-mlbb-icon" aria-label="MLBB Diamonds">
                <svg viewBox="0 0 64 64" aria-hidden="true">
                    <defs>
                        <linearGradient id="cartMlbbBg" x1="0" y1="0" x2="1" y2="1">
                            <stop offset="0%" stop-color="#35d7ff"/>
                            <stop offset="52%" stop-color="#5b5fff"/>
                            <stop offset="100%" stop-color="#10152f"/>
                        </linearGradient>
                        <linearGradient id="cartDiamond" x1="0" y1="0" x2="1" y2="1">
                            <stop offset="0%" stop-color="#ffffff"/>
                            <stop offset="40%" stop-color="#67e8f9"/>
                            <stop offset="100%" stop-color="#8b5cf6"/>
                        </linearGradient>
                    </defs>
                    <rect x="1" y="1" width="62" height="62" rx="17" fill="url(#cartMlbbBg)"/>
                    <path d="M18 24 L26 14 H39 L47 24 L32 48 Z" fill="url(#cartDiamond)" stroke="rgba(255,255,255,.75)" stroke-width="2"/>
                    <path d="M18 24 H47 M26 14 L32 48 M39 14 L32 48" stroke="rgba(6,18,45,.38)" stroke-width="1.7"/>
                    <text x="32" y="57" text-anchor="middle" font-size="10" font-weight="900" font-family="Arial, sans-serif" fill="#ffffff">MLBB</text>
                </svg>
            </div>
        `;
    }

    return `${cartProductVisual(item, productName, imageUrl)}`;
}


function formatCartItemsCount(items = []) {
    const positions = items.length;
    const quantity = items.reduce((sum, item) => sum + Number(item.quantity || 0), 0);
    return tr('cart_items_summary', { positions, quantity });
}

// ===== Cart =====
function addToCart(item) {
    const first = state.cart[0];
    if (first && Number(first.product_id) !== Number(item.product_id)) {
        showToast('error', tr('one_product_order'));
        return;
    }

    const sameTarget = (a, b) =>
        (a.target_id || '') === (b.target_id || '') &&
        (a.target_server || '') === (b.target_server || '') &&
        (a.target_region || '') === (b.target_region || '');

    const existing = state.cart.find(i => i.variation_id === item.variation_id && sameTarget(i, item));
    if (existing) {
        existing.quantity = Math.min(10, existing.quantity + item.quantity);
    } else {
        state.cart.push(item);
    }
    saveCart();
    updateCartBadge();
    showToast('success', tr('added_to_cart'));
    
    if (tg?.HapticFeedback) {
        tg.HapticFeedback.notificationOccurred('success');
    }
}

function removeFromCart(variationId) {
    state.cart = state.cart.filter(i => i.variation_id !== variationId);
    saveCart();
    updateCartBadge();
    loadCartPage();
}

// ===== Safe HTML helper =====
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const str = String(text);
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Tagged template literal for safe HTML
function html(strings, ...values) {
    return strings.reduce((result, str, i) => {
        const val = values[i] !== undefined ? escapeHtml(values[i]) : '';
        return result + str + val;
    }, '');
}

// ===== Safe localStorage =====
function safeSet(key, value) {
    try { localStorage.setItem(key, value); } catch (e) { console.warn('localStorage set failed:', e); }
}

function safeGet(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
}

function safeRemove(key) {
    try { localStorage.removeItem(key); } catch (e) { /* silent */ }
}

function saveCart() {
    try { localStorage.setItem('cart', JSON.stringify(state.cart)); } catch (e) { console.warn('Cart save failed:', e); }
}

function clearAuth() {
    safeRemove('access_token');
    safeRemove('refresh_token');
    state.token = null;
    state.user = null;
}

function updateCartBadge() {
    const badge = document.getElementById('cart-badge');
    if (badge) {
        const count = state.cart.reduce((sum, item) => sum + item.quantity, 0);
        badge.textContent = count;
        badge.classList.toggle('hidden', count === 0);
    }
}

function loadCartPage() {
    const container = document.getElementById('cart-items');
    const summary = document.getElementById('cart-summary');
    
    if (state.cart.length === 0) {
        container.innerHTML = `
            <div class="empty-cart">
                <div class="empty-icon">🛒</div>
                <p>${tr('empty_cart')}</p>
                <button class="btn-primary" onclick="navigateTo('home')">${tr('home')}</button>
            </div>
        `;
        summary.classList.add('hidden');
        return;
    }
    
    const subtotal = state.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const discount = state.promo?.discount_amount || 0;
    const total = Math.max(0, subtotal - discount);
    const itemsCountLabel = formatCartItemsCount(state.cart);
    
    container.innerHTML = state.cart.map(item => {
        const imageUrl = getCartItemImageUrl(item);
        const productName = item.product_name || item.name || tr('product');
        const variationName = getCartVariationName(item);
        const targetIdLabel = item.requirements?.target_id_label || 'ID';
        const serverLabel = item.requirements?.target_server_label || 'Server';
        const targetLine = [item.target_id, item.target_server ? `${serverLabel}: ${item.target_server}` : ''].filter(Boolean).join(' • ');
        const regionLabel = item.requirements?.target_region_label || tr('target_region');
        const regionLine = item.target_region_label || item.target_region || '';
        const itemTotal = Number(item.price || 0) * Number(item.quantity || 0);

        return `
            <div class="cart-item cart-checkout-item">
                <div class="cart-item-media">
                    <div class="image cart-real-image">
                        ${imageUrl
                            ? `${productVisual(productName, imageUrl)}`
                            : productVisual(productName, imageUrl)
                        }
                    </div>
                    <span class="cart-qty-badge">x${escapeHtml(item.quantity)}</span>
                </div>

                <div class="details cart-item-details">
                    <div class="cart-item-heading">
                        <div>
                            <div class="name cart-product-name">${escapeHtml(productName)}</div>
                            ${variationName ? `<div class="cart-variation-name">${escapeHtml(variationName)}</div>` : ''}
                        </div>
                        <button class="remove-btn cart-remove-btn" type="button" aria-label="Удалить" data-id="${item.variation_id}">
                            <span aria-hidden="true">×</span>
                        </button>
                    </div>

                    <div class="cart-meta-grid">
                        ${renderCartMetaRow(targetIdLabel, targetLine)}
                        ${renderCartMetaRow(tr('player'), item.verified_target_name, 'is-verified')}
                        ${renderCartMetaRow(regionLabel, regionLine)}
                    </div>

                    <div class="cart-item-footer">
                        <span>${tr('subtotal')}</span>
                        <div class="price">${formatMoney(itemTotal, 'UZS')}</div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    hydrateProductVisuals(container);

    container.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', () => removeFromCart(parseInt(btn.dataset.id)));
    });
    
    summary.innerHTML = `
        <div class="cart-summary-head">
            <div>
                <div class="cart-summary-kicker">${tr('checkout')}</div>
                <h2>${tr('total')}</h2>
            </div>
            <span id="cart-items-count" class="cart-summary-count">${itemsCountLabel}</span>
        </div>
        <div class="summary-row cart-summary-subtotal">
            <span>${tr('subtotal')}</span>
            <span id="cart-subtotal">0 UZS</span>
        </div>
        <div class="summary-row cart-summary-discount">
            <span>${tr('discount')}</span>
            <span id="cart-discount">0 UZS</span>
        </div>
        <div class="summary-row total cart-summary-total">
            <span>${tr('total')}</span>
            <span id="cart-total">0 UZS</span>
        </div>
        <button class="btn-primary btn-glow checkout-btn" id="checkout-btn">
            <span>${tr('proceed_checkout')}</span>
        </button>
    `;
    summary.classList.add('cart-checkout-summary');
    summary.classList.remove('hidden');
    document.getElementById('cart-subtotal').textContent = formatMoney(subtotal, 'UZS');
    document.getElementById('cart-discount').textContent = formatMoney(discount, 'UZS');
    const cartItemsCountEl = document.getElementById('cart-items-count');
    if (cartItemsCountEl) cartItemsCountEl.textContent = itemsCountLabel;
    document.getElementById('cart-total').textContent = formatMoney(total, 'UZS');
    
    document.getElementById('checkout-btn').addEventListener('click', () => {
        navigateTo('checkout');
    });
}


function formatMoney(amount, currency = 'UZS') {
    const n = Number(amount || 0);
    if (currency === 'UZS') {
        return `${Math.round(n).toLocaleString('ru-RU')} UZS`;
    }
    return `$${n.toFixed(2)}`;
}

function secondsLeftUntil(expiresAt) {
        return getTopupSecondsLeft({ expires_at: expiresAt });
    }

function renderP2PSession(session) {
    if (!session) return '<div class="payment-box error">No active payment session</div>';
    const card = session.card || {};
    const secondsLeft = secondsLeftUntil(session.expires_at);
    const minutes = Math.floor(secondsLeft / 60);
    const seconds = secondsLeft % 60;
    return `
        <div class="payment-instructions p2p-box">
            <h3>${tr('p2p_payment')}</h3>
            <div class="amount">${formatMoney(session.assigned_amount, 'UZS')}</div>
            <div class="details">
                <p><strong>Pay exact amount:</strong> ${formatMoney(session.assigned_amount, 'UZS')}</p>
                <p><strong>${tr('card')}</strong> <span id="p2p-card-number">${escapeHtml(card.card_number || '')}</span></p>
                <p><strong>Владелец:</strong> ${escapeHtml(card.card_holder || '-')}</p>
                <p><strong>Банк:</strong> ${escapeHtml(card.bank_name || card.name || '-')}</p>
                <p><strong>Система:</strong> ${escapeHtml(card.payment_system || '-')}</p>
                <p><strong>${tr('time_left')}</strong> <span class="timer">${minutes}:${String(seconds).padStart(2, '0')}</span></p>
                <p style="color: var(--text-muted); font-size: 13px;">After transfer the system will confirm payment automatically when bank notification arrives.</p>
            </div>
            <div class="action-buttons">
                <button class="btn-secondary" onclick="copyText('${escapeHtml(card.card_number || '')}')">${tr('copy_card')}</button>
                <button class="btn-secondary" onclick="copyText('${Math.round(Number(session.assigned_amount || 0))}')">${tr('copy_amount')}</button>
            </div>
        </div>
    `;
}

async function copyText(text) {
    try {
        await navigator.clipboard.writeText(String(text));
        showToast('success', tr('copied'));
    } catch (e) {
        showToast('error', tr('copy_failed'));
    }
}

// ===== Оплата =====
async function loadОплатаPage() {
    if (!state.cart.length) {
        navigateTo('cart');
        return;
    }

    updateCheckoutAmounts();
    renderCheckoutOrderItems();

    const targetInfo = getCartTargetInfo();
    const targetIdEl = document.getElementById('target-id');
    const targetServerEl = document.getElementById('target-server');

    if (targetIdEl && targetInfo.target_id) targetIdEl.value = targetInfo.target_id;
    if (targetServerEl && targetInfo.target_server) targetServerEl.value = targetInfo.target_server;

    const targetIdLabel = targetInfo.requirements?.target_id_label || 'ID';
    const targetServerLabel = targetInfo.requirements?.target_server_label || 'Server ID';
    const targetRegionLabel = targetInfo.requirements?.target_region_label || tr('target_region');
    const targetRegion = targetInfo.target_region_label || targetInfo.target_region || '';

    setTextIfExists('checkout-recipient-title', targetInfo.verified_target_name || tr('player_account'));
    setTextIfExists('checkout-recipient-status', targetInfo.verified_target_name ? tr('verified') : tr('order_details'));
    setTextIfExists('checkout-target-name', targetInfo.verified_target_name || '—');
    setTextIfExists('checkout-target-id-text', targetInfo.target_id || '—');
    setTextIfExists('checkout-target-server-text', targetInfo.target_server || '—');
    setTextIfExists('checkout-target-region-text', targetRegion || '—');
    setTextIfExists('checkout-order-title', state.cart[0]?.product_name || tr('products'));

    setVisibleIfExists('checkout-nickname-row', !!targetInfo.verified_target_name);
    setVisibleIfExists('server-field', !!targetInfo.target_server || !!targetInfo.requirements?.requires_server_id);
    setVisibleIfExists('checkout-region-row', !!targetRegion || !!targetInfo.requirements?.requires_region);

    const targetIdText = document.querySelector('#checkout-target-id-text')?.previousElementSibling;
    const targetServerText = document.querySelector('#checkout-target-server-text')?.previousElementSibling;
    const targetRegionText = document.querySelector('#checkout-target-region-text')?.previousElementSibling;

    if (targetIdText) targetIdText.textContent = 'ID';
    if (targetServerText) targetServerText.textContent = targetServerLabel;
    if (targetRegionText) targetRegionText.textContent = targetRegionLabel;

    try {
        const balance = await api('GET', '/users/balance');
        updateCheckoutBalanceState(Number(balance?.balance || 0));
    } catch (error) {
        setTextIfExists('checkout-balance-status', tr('balance_load_failed'));
        setTextIfExists('checkout-balance-after', '—');
    }

    document.getElementById('apply-promo')?.addEventListener('click', applyPromo);
    document.getElementById('place-order-btn')?.addEventListener('click', placeOrder);
    document.getElementById('checkout-back')?.addEventListener('click', () => navigateTo('cart'));
}


function renderPaymentMethods(methods) {
    // Legacy helper kept for compatibility. Wallet balance is now the main flow.
    const container = document.getElementById('payment-methods');
    if (!container || !methods) return;
    container.innerHTML = '';
}

async function applyPromo() {
    const code = document.getElementById('promo-code')?.value.trim() || '';
    if (!code) return;

    const subtotal = getCheckoutTotals().subtotal;

    try {
        const result = await api('POST', '/orders/apply-promo', {
            code: code,
            order_amount: subtotal,
        });

        const msgEl = document.getElementById('promo-message');
        if (!msgEl) return;

        if (result.is_valid) {
            state.promo = result;
            msgEl.textContent = `✓ ${result.message} (-${formatMoney(result.discount_amount, 'UZS')})`;
            msgEl.className = 'promo-message success';

            try {
                const balance = await api('GET', '/users/balance');
                updateCheckoutBalanceState(Number(balance?.balance || 0));
            } catch (_) {
                updateCheckoutAmounts();
            }
        } else {
            msgEl.textContent = `✗ ${result.message}`;
            msgEl.className = 'promo-message error';
        }
    } catch (error) {
        showToast('error', tr('invalid_promo'));
    }
}


async function placeOrder() {
    const targetInfo = getCartTargetInfo();
    const targetId = targetInfo.target_id || document.getElementById('target-id').value.trim();
    if (targetInfo.requirements?.requires_target_id && !targetId) {
        showToast('error', tr('enter_user_id'));
        return;
    }

    const targetServer = targetInfo.target_server || document.getElementById('target-server').value.trim();
    const targetРегион = targetInfo.target_region || null;

    const items = state.cart.map(item => ({
        variation_id: item.variation_id,
        quantity: item.quantity,
    }));

    try {
        const result = await api('POST', '/orders', {
            items: items,
            target_id: targetId || null,
            target_server: targetServer || null,
            target_region: targetРегион || null,
            promo_code: state.promo?.code || null,
        });

        if (result) {
            // Clear cart
            state.cart = [];
            state.promo = null;
            saveCart();
            updateCartBadge();

            // Show confirmation
            showOrderConfirmation(result);

            if (tg?.HapticFeedback) {
                tg.HapticFeedback.notificationOccurred('success');
            }
        }
    } catch (error) {
        if ((error.message || '').toLowerCase().includes('insufficient balance')) {
            showToast('error', tr('not_enough_balance'));
            navigateTo('profile');
            return;
        }
        showToast('error', error.message || tr('failed_place_order'));
    }
}

function showOrderConfirmation(order) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-sheet">
            <div class="modal-header">
                <h2>${tr('order_paid')}</h2>
                <button class="modal-close">&times;</button>
            </div>
            <div style="text-align: center; padding: 20px 0;">
                <div style="font-size: 48px; margin-bottom: 16px;">🚀</div>
                <h3 style="font-size: 20px; margin-bottom: 8px;">${tr('order')} #${escapeHtml(order.order_number)}</h3>
                <p style="color: var(--text-secondary); margin-bottom: 20px;">${tr('paid_from_balance')} <strong style="color: var(--neon-green);">${formatMoney(order.total_amount, 'UZS')}</strong></p>
                <div class="payment-instructions" style="text-align: left;">
                    <h3>${tr('auto_delivery')}</h3>
                    <p>${tr('order_sent_to_admin_hint')}</p>
                    <p>${tr('track_status_hint')}</p>
                </div>
                <button class="btn-primary" style="margin-top: 16px;" onclick="closeModal()">${tr('view_my_orders')}</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', closeModal);
    modal.querySelector('.btn-primary').addEventListener('click', () => {
        closeModal();
        navigateTo('orders');
    });
}

function closeModal() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.remove());
}

// ===== Orders =====

// KADI_HISTORY_TWO_TABS_JS_V1_START
function getHistoryStatusLabel(status, type = 'order') {
    const s = String(status || '').toLowerCase();

    const orderLabels = {
        paid: tr('paid'),
        completed: tr('completed'),
        done: tr('completed'),
        pending: tr('pending'),
        awaiting_payment: tr('pending'),
        checking: tr('checking'),
        payment_submitted: tr('checking'),
        failed: tr('failed'),
        cancelled: tr('cancelled'),
        refunded: tr('refunded'),
        processing: tr('processing')
    };

    const topupLabels = {
        paid: tr('topup_paid'),
        completed: tr('topup_paid'),
        done: tr('topup_paid'),
        pending: tr('pending'),
        awaiting_payment: tr('pending'),
        checking: tr('checking'),
        payment_submitted: tr('checking'),
        failed: tr('failed'),
        cancelled: tr('cancelled'),
        expired: tr('expired'),
        rejected: tr('rejected')
    };

    const labels = type === 'topup' ? topupLabels : orderLabels;
    return labels[s] || String(status || '—').replace(/_/g, ' ');
}

function getHistoryStatusClass(status) {
    return String(status || 'pending').toLowerCase().replace(/[^a-z0-9_-]/g, '');
}

function getHistoryDate(value) {
    try {
        return new Date(value || Date.now()).toLocaleDateString();
    } catch (e) {
        return '';
    }
}

function getTopupAmount(topup) {
    return topup.amount || topup.amount_uzs || topup.total_amount || topup.value || 0;
}

function getOrderItemsLabel(count) {
    const n = Number(count || 0);
    if (n % 10 === 1 && n % 100 !== 11) return `${n} товар`;
    if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return `${n} товара`;
    return `${n} товаров`;
}

function getOrderFirstItem(order = {}) {
    return Array.isArray(order.items) && order.items.length ? order.items[0] : null;
}

function getOrderVariationName(order = {}) {
    const item = getOrderFirstItem(order);
    if (!item) return '';

    return String(
        item.variation?.name ||
        item.variation_name ||
        item.name ||
        ''
    ).trim();
}

function getOrderProductName(order = {}) {
    const item = getOrderFirstItem(order);
    const variationName = getOrderVariationName(order);

    const productName = String(
        item?.product_name ||
        item?.product?.name ||
        order.product_name ||
        order.product?.name ||
        ''
    ).trim();

    if (productName) return productName;
    if (/diamonds?/i.test(variationName)) return 'MLBB Diamonds';
    if (/weekly|недель/i.test(variationName)) return 'MLBB Weekly Pass';

    return 'Покупка';
}

function getOrderPackageLine(order = {}, count = 0, date = '') {
    const parts = [];
    const variationName = getOrderVariationName(order);

    if (variationName) parts.push(variationName);
    if (Number(count || 0) > 1) parts.push(getOrderItemsLabel(count));
    if (date) parts.push(date);

    return parts.join(' • ');
}

function getOrderDisplayNumber(order = {}) {
    const value = order.order_number || order.id || '';
    return value ? `#${value}` : '';
}


function getOrderHistoryIcon(order = {}, type = 'order') {
    if (type === 'topup') {
        return `
            <div class="history-card-icon history-card-icon-topup" aria-hidden="true">
                <svg viewBox="0 0 48 48">
                    <rect x="1" y="1" width="46" height="46" rx="15"></rect>
                    <path d="M24 14v20M14 24h20"></path>
                </svg>
            </div>
        `;
    }

    const productName = typeof getOrderProductName === 'function' ? getOrderProductName(order) : '';
    const variationName = typeof getOrderVariationName === 'function' ? getOrderVariationName(order) : '';
    const label = `${productName} ${variationName}`.toLowerCase();

    if (label.includes('diamond') || label.includes('mlbb') || label.includes('mobile legends')) {
        return `
            <div class="history-card-icon history-card-icon-mlbb" aria-hidden="true">
                <svg viewBox="0 0 48 48">
                    <defs>
                        <linearGradient id="historyMlbbBg" x1="0" y1="0" x2="1" y2="1">
                            <stop offset="0%" stop-color="#36d9ff"/>
                            <stop offset="55%" stop-color="#6766ff"/>
                            <stop offset="100%" stop-color="#111633"/>
                        </linearGradient>
                        <linearGradient id="historyDiamond" x1="0" y1="0" x2="1" y2="1">
                            <stop offset="0%" stop-color="#ffffff"/>
                            <stop offset="42%" stop-color="#67e8f9"/>
                            <stop offset="100%" stop-color="#a855f7"/>
                        </linearGradient>
                    </defs>
                    <rect x="1" y="1" width="46" height="46" rx="15" fill="url(#historyMlbbBg)"></rect>
                    <path d="M13 19l6-8h10l6 8-11 17z" fill="url(#historyDiamond)" stroke="rgba(255,255,255,.78)" stroke-width="1.7"></path>
                    <path d="M13 19h22M19 11l5 25M29 11l-5 25" stroke="rgba(8,14,36,.38)" stroke-width="1.35"></path>
                </svg>
            </div>
        `;
    }

    return `
        <div class="history-card-icon history-card-icon-default" aria-hidden="true">
            <span>K</span>
        </div>
    `;
}

// KADI_HISTORY_TWO_TABS_JS_V1_END

async function loadOrdersPage() {
    const ordersResult = await Promise.allSettled([
        api('GET', '/orders/my'),
        api('GET', '/payments/topups/my')
    ]);

    const ordersResponse = ordersResult[0];
    const topupsResponse = ordersResult[1];

    state.orders = ordersResponse.status === 'fulfilled' && Array.isArray(ordersResponse.value)
        ? ordersResponse.value
        : [];

    state.topups = topupsResponse.status === 'fulfilled' && Array.isArray(topupsResponse.value)
        ? topupsResponse.value
        : [];

    state.historyTab = state.historyTab || 'orders';

    renderOrders(state.historyTab);

    document.querySelectorAll('[data-history-tab]').forEach(btn => {
        if (btn.dataset.bound === '1') return;
        btn.dataset.bound = '1';

        btn.addEventListener('click', () => {
            state.historyTab = btn.dataset.historyTab || 'orders';

            document.querySelectorAll('[data-history-tab]').forEach(b => {
                const active = b === btn;
                b.classList.toggle('active', active);
                b.setAttribute('aria-selected', active ? 'true' : 'false');
            });

            renderOrders(state.historyTab);
        });
    });
}

function renderOrders(tabOrOrders = 'orders', filter = null) {
    const container = document.getElementById('orders-list');
    if (!container) return;

    const tab = tabOrOrders === 'topups' || tabOrOrders === 'orders'
        ? tabOrOrders
        : (state.historyTab || 'orders');

    state.historyTab = tab;

    document.querySelectorAll('[data-history-tab]').forEach(btn => {
        const active = btn.dataset.historyTab === tab;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    if (tab === 'topups') {
        const topups = state.topups || [];

        if (!topups.length) {
            container.innerHTML = `<div class="text-center history-empty">${tr('no_topups')}</div>`;
            return;
        }

        container.innerHTML = topups.map(topup => {
            const status = getHistoryStatusClass(topup.status);
            const amount = getTopupAmount(topup);
            const date = getHistoryDate(topup.created_at || topup.paid_at || topup.expires_at);

            return `
                <div class="order-card history-card topup-card">
                    <div class="history-card-main history-card-main-with-icon">
                        ${getOrderHistoryIcon(topup, 'topup')}
                        <div class="history-card-copy">
                            <div class="history-card-title">${tr('balance_topup')}</div>
                            <div class="items history-card-subtitle">${escapeHtml(date || '—')}</div>
                        </div>
                        <div class="total">${formatMoney(amount, 'UZS')}</div>
                    </div>
                    <div class="history-card-meta">
                        <div class="history-card-order-id">#${escapeHtml(topup.id || '')}</div>
                        <div class="status status-${status}">${escapeHtml(getHistoryStatusLabel(topup.status, 'topup'))}</div>
                    </div>
                </div>
            `;
        }).join('');

        return;
    }

    const orders = state.orders || [];

    if (!orders.length) {
        container.innerHTML = `<div class="text-center history-empty">${tr('no_orders')}</div>`;
        return;
    }

    container.innerHTML = orders.map(order => {
        const status = getHistoryStatusClass(order.status);
        const count = order.items?.length || 0;
        const date = getHistoryDate(order.created_at);
        const productName = getOrderProductName(order);
        const packageLine = getOrderPackageLine(order, count, date);
        const orderNumber = getOrderDisplayNumber(order);

        return `
            <div class="order-card history-card" data-id="${order.id}">
                <div class="history-card-main history-card-main-with-icon">
                    ${getOrderHistoryIcon(order, 'order')}
                    <div class="history-card-copy">
                        <div class="history-card-title">${escapeHtml(productName)}</div>
                        <div class="items history-card-subtitle">${escapeHtml(packageLine)}</div>
                    </div>
                    <div class="total">${formatMoney(order.total_amount || 0, 'UZS')}</div>
                </div>
                <div class="history-card-meta">
                    <div class="history-card-order-id">${escapeHtml(orderNumber)}</div>
                    <div class="status status-${status}">${escapeHtml(getHistoryStatusLabel(order.status, 'order'))}</div>
                </div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('.order-card[data-id]').forEach(card => {
        card.addEventListener('click', () => {
            openOrderDetail(parseInt(card.dataset.id));
        });
    });
}

async function openOrderDetail(orderId) {
    const order = state.orders.find(o => o.id === orderId);
    if (!order) return;

    const content = document.getElementById('order-detail-content');
    const firstItem = getOrderFirstItem(order) || {};
    const statusClass = getHistoryStatusClass(order.status);
    const statusLabel = getHistoryStatusLabel(order.status, 'order');
    const orderNumber = getOrderDisplayNumber(order);
    const productName = getOrderProductName(order);
    const variationName = getOrderVariationName(order);
    const quantity = Number(firstItem.quantity || firstItem.qty || 0);
    const unitPrice = Number(firstItem.unit_price || firstItem.price || firstItem.variation?.price || 0);
    const itemTotal = Number(
        firstItem.total_price ??
        firstItem.total_amount ??
        (unitPrice && quantity ? unitPrice * quantity : 0)
    );
    const discountAmount = Number(order.discount_amount || 0);
    const totalAmount = Number(order.total_amount || 0);
    const subtotalAmount = Number(order.subtotal_amount || (totalAmount + discountAmount));
    const createdAt = order.created_at ? new Date(order.created_at).toLocaleString() : '—';

    const recipient = {
        nickname: order.verified_target_name ||
            order.target_name ||
            order.player_name ||
            firstItem.verified_target_name ||
            firstItem.target_name ||
            '',
        targetId: order.target_id ||
            order.game_id ||
            firstItem.target_id ||
            firstItem.game_id ||
            '',
        targetServer: order.target_server ||
            order.server_id ||
            firstItem.target_server ||
            firstItem.server_id ||
            '',
        targetRegion: order.target_region_label ||
            order.target_region ||
            firstItem.target_region_label ||
            firstItem.target_region ||
            ''
    };

    const hasRecipient = Object.values(recipient).some(Boolean);

    const renderDetailRow = (label, value, extraClass = '') => value ? `
        <div class="order-detail-info-row ${extraClass}">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    ` : '';

    let p2pSession = null;
    if (order.status === 'awaiting_payment' || order.status === 'payment_submitted') {
        try {
            p2pSession = await api('POST', `/payments/p2p/session/${order.id}`);
        } catch (e) {
            console.error('P2P session load error:', e);
        }
    }

    content.innerHTML = `
        <div class="order-detail-shell">
            <section class="order-detail-card order-detail-header-card">
                <div class="order-detail-header-copy">
                    <div class="order-detail-kicker">${tr('order_details')}</div>
                    <h1>${tr('order_number_title', { number: escapeHtml(orderNumber || `#${order.id || ''}`) })}</h1>
                    <div class="order-detail-date">${escapeHtml(createdAt)}</div>
                </div>
                <div class="status status-${statusClass} order-detail-status">${escapeHtml(statusLabel)}</div>
            </section>

            <section class="order-detail-card order-detail-product-card">
                <div class="order-detail-product-main">
                    ${getOrderHistoryIcon(order, 'order')}
                    <div class="order-detail-product-copy">
                        <div class="order-detail-product-title">${escapeHtml(productName)}</div>
                        ${variationName ? `<div class="order-detail-product-subtitle">${escapeHtml(variationName)}</div>` : ''}
                    </div>
                </div>

                <div class="order-detail-product-meta">
                    ${quantity ? `
                        <div class="order-detail-info-row">
                            <span>${tr('quantity')}</span>
                            <strong>${escapeHtml(String(quantity))}</strong>
                        </div>
                    ` : ''}
                    ${unitPrice ? `
                        <div class="order-detail-info-row">
                            <span>${tr('price')}</span>
                            <strong>${formatMoney(unitPrice, 'UZS')}</strong>
                        </div>
                    ` : ''}
                    <div class="order-detail-info-row order-detail-info-row-total">
                        <span>${tr('item_subtotal')}</span>
                        <strong>${formatMoney(itemTotal || totalAmount, 'UZS')}</strong>
                    </div>
                </div>
            </section>

            ${hasRecipient ? `
                <section class="order-detail-card order-detail-recipient-card">
                    <div class="order-detail-section-title">${tr('recipient')}</div>
                    <div class="order-detail-recipient-list">
                        ${renderDetailRow(tr('player'), recipient.nickname, 'is-verified')}
                        ${renderDetailRow('User ID / Game ID', recipient.targetId)}
                        ${renderDetailRow('Server ID', recipient.targetServer)}
                        ${renderDetailRow(tr('target_region'), recipient.targetRegion)}
                    </div>
                </section>
            ` : ''}

            ${(order.status === 'awaiting_payment' || order.status === 'payment_submitted') ? `
                <div class="order-detail-payment-block">
                    ${p2pSession ? renderP2PSession(p2pSession) : `
                    <div class="payment-instructions">
                        <h3>${tr('complete_payment')}</h3>
                        <div class="amount">${formatMoney(order.total_amount, 'UZS')}</div>
                        <div class="details">
                            <p>${tr('payment_card_missing')}</p>
                            <p><strong>${tr('order_label')}:</strong> ${escapeHtml(order.order_number || order.id || '')}</p>
                        </div>
                    </div>`}
                    <div class="action-buttons">
                        <button class="btn-primary" id="check-payment-btn">${tr('check_payment')}</button>
                        <button class="btn-secondary" id="mark-paid-btn">${tr('manual_check')}</button>
                    </div>
                </div>
            ` : ''}

            <section class="order-detail-card order-detail-summary-card">
                <div class="order-detail-section-title">${tr('payment')}</div>
                <div class="order-detail-info-row">
                    <span>${tr('amount')}</span>
                    <strong>${formatMoney(subtotalAmount, 'UZS')}</strong>
                </div>
                ${discountAmount > 0 ? `
                    <div class="order-detail-info-row order-detail-discount-row">
                        <span>${tr('discount')}</span>
                        <strong>-${formatMoney(discountAmount, 'UZS')}</strong>
                    </div>
                ` : ''}
                <div class="order-detail-info-row order-detail-grand-total">
                    <span>${tr('total')}</span>
                    <strong>${formatMoney(totalAmount, 'UZS')}</strong>
                </div>
            </section>
        </div>
    `;

    document.getElementById('order-detail-back').addEventListener('click', () => navigateTo('orders'));

    const checkPaymentBtn = document.getElementById('check-payment-btn');
    if (checkPaymentBtn) {
        checkPaymentBtn.addEventListener('click', async () => {
            showToast('info', tr('checking_payment_status'));
            await loadOrdersPage();
        });
    }

    const markPaidBtn = document.getElementById('mark-paid-btn');
    if (markPaidBtn) {
        markPaidBtn.addEventListener('click', async () => {
            try {
                markPaidBtn.disabled = true;
                markPaidBtn.textContent = tr('sending');

                await api('POST', `/payments/p2p/submit/${order.id}`, {});
                showToast('success', tr('payment_sent_for_check'));
                await loadOrdersPage();
                await openOrderDetail(order.id);
            } catch (e) {
                console.error('Manual payment submit error:', e);
                showToast('error', e.message || tr('error'));
            } finally {
                markPaidBtn.disabled = false;
                markPaidBtn.textContent = tr('manual_check');
            }
        });
    }

    navigateTo('order-detail');
}

// ===== Profile / Wallet =====

// KADI_PROFILE_AVATAR_PHOTO_V1
function getTelegramPhotoUrl() {
    try {
        const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
        return tgUser?.photo_url || '';
    } catch (e) {
        return '';
    }
}

function applyTelegramAvatarPhoto(profile = {}) {
    const photoUrl = profile.photo_url || profile.photoUrl || getTelegramPhotoUrl();

    if (!photoUrl) return;

    document.querySelectorAll('.profile-avatar, .user-avatar, .avatar, #profile-avatar').forEach(el => {
        el.classList.add('has-photo');
        el.style.backgroundImage = `url("${photoUrl}")`;
        el.style.backgroundSize = 'cover';
        el.style.backgroundPosition = 'center';
        el.style.backgroundRepeat = 'no-repeat';

        const icon = el.querySelector('svg, img, span, i');
        if (icon) icon.style.display = 'none';

        if (el.textContent && el.children.length === 0) {
            el.textContent = '';
        }
    });
}

async function loadProfilePage() {
    try {
        const profile = await api('GET', '/users/profile');
        const balance = await api('GET', '/users/balance');

        document.getElementById('profile-name').textContent = profile.first_name || 'User';
        document.getElementById('profile-username').textContent = profile.username ? `@${escapeHtml(profile.username)}` : `ID: ${escapeHtml(profile.telegram_id)}`;
    // KADI_PROFILE_ID_TOPUP_V1
    const profileTelegramIdEl = document.getElementById('profile-telegram-id');
    if (profileTelegramIdEl) {
        const telegramId = profile.telegram_id || profile.id || state.telegramUser?.id || '';
        profileTelegramIdEl.textContent = telegramId ? `ID: ${telegramId}` : 'ID: —';
    }
        document.getElementById('profile-balance').textContent = formatMoney(balance.balance, 'UZS');
        document.getElementById('profile-orders').textContent = profile.orders_count || 0;
        document.getElementById('profile-spent').textContent = formatMoney(profile.total_spent || 0, 'UZS');
        const headerBalanceEl = document.getElementById('header-balance');
        if (headerBalanceEl) headerBalanceEl.textContent = formatMoney(balance.balance || 0, 'UZS');

        document.getElementById('create-topup-btn')?.addEventListener('click', createBalanceTopup);
    const profileTopupBtn = document.getElementById('profile-topup-btn');
    if (profileTopupBtn && !profileTopupBtn.dataset.bound) {
        profileTopupBtn.dataset.bound = '1';
        profileTopupBtn.addEventListener('click', createBalanceTopup);
    }
        await loadActiveTopupBox();

        // Show admin panel if admin
        if (profile.is_admin) {
            document.getElementById('admin-panel-btn').classList.remove('hidden');
        }
    } catch (error) {
        console.error('Profile error:', error);
    }
}

function renderTopupBox(topup) {
    if (!topup) return '';
    const card = topup.card || {};
    const secondsLeft = secondsLeftUntil(topup.expires_at);
    const minutes = Math.floor(secondsLeft / 60);
    const seconds = secondsLeft % 60;
    return `
        <div class="payment-instructions p2p-box" style="margin-top: 14px;">
            <h3>${tr('active_topup')}</h3>
            <div class="amount">${formatMoney(topup.amount, 'UZS')}</div>
            <div class="details">
                <p><strong>Сумма перевода:</strong> ${formatMoney(topup.amount, 'UZS')}</p>
                <p><strong>${tr('card')}</strong> <span id="topup-card-number">${escapeHtml(card.card_number || '')}</span></p>
                <p><strong>Владелец:</strong> ${escapeHtml(card.card_holder || '-')}</p>
                <p><strong>Банк:</strong> ${escapeHtml(card.bank_name || card.name || '-')}</p>
                <p><strong>Система:</strong> ${escapeHtml(card.payment_system || '-')}</p>
                <p><strong>${tr('time_left')}</strong> <span class="timer">${minutes}:${String(seconds).padStart(2, '0')}</span></p>
                <p style="color: var(--text-muted); font-size: 13px;">Карта зарезервирована только за вами на время таймера. После уведомления HUMO баланс пополнится автоматически.</p>
            </div>
            <div class="action-buttons">
                <button class="btn-secondary" onclick="copyText('${escapeHtml(card.card_number || '')}')">${tr('copy_card')}</button>
                <button class="btn-secondary" onclick="copyText('${Math.round(Number(topup.amount || 0))}')">${tr('copy_amount')}</button>
                
                <button class="btn-primary kadi-paid-btn" onclick="confirmBalanceTopupPaid(${topup.id})">Я оплатил</button>
                <button class="btn-secondary" onclick="cancelBalanceTopup(${topup.id})">${tr('cancel')}</button>
            </div>
        </div>
    `;
}

async function loadActiveTopupBox() {
    const box = document.getElementById('active-topup-box');
    if (!box) return;
    try {
        const topups = await api('GET', '/payments/topups/my');
        const topup = (topups || []).find(t => t.status === 'pending');
        box.innerHTML = topup
            ? renderTopupBox(topup)
            : `<p style="color: var(--text-muted); font-size: 13px; margin-top: 10px;">${tr('no_active_topup')}</p>`;
    } catch (error) {
        box.innerHTML = `<p style="color: var(--text-muted); font-size: 13px; margin-top: 10px;">${tr('topup_load_failed')}</p>`;
    }
}

async function createBalanceTopup() {
    const input = document.getElementById('topup-amount');
    const amount = Number(input?.value || 0);
    if (!amount || amount <= 0) {
        showToast('error', tr('enter_topup_amount'));
        return;
    }

    try {
        const topup = await api('POST', '/payments/topups', { amount });
        showToast('success', tr('card_reserved'));
        document.getElementById('active-topup-box').innerHTML = renderTopupBox(topup);
    } catch (error) {
        showToast('error', error.message || 'Не удалось создать пополнение');
    }
}

async function cancelBalanceTopup(topupId) {
    try {
        await api('POST', `/payments/topups/${topupId}/cancel`);
        showToast('success', 'Пополнение отменено');
        await loadActiveTopupBox();
    } catch (error) {
        showToast('error', error.message || 'Could not cancel top-up');
    }
}

// ===== Admin Panel =====
async function loadAdminPage() {
    if (!state.user?.is_admin) {
        showToast('error', 'Access denied');
        navigateTo('profile');
        return;
    }

    try {
        const stats = await api('GET', '/admin/dashboard');
        document.getElementById('admin-stat-users').textContent = stats.total_users;
        document.getElementById('admin-stat-orders').textContent = stats.total_orders;
        document.getElementById('admin-stat-revenue').textContent = formatMoney(stats.total_revenue, 'UZS');
        document.getElementById('admin-stat-pending').textContent = stats.pending_orders;
    } catch (error) {
        console.error('Admin stats error:', error);
    }

    if (!state.adminEventsBound) {
        document.querySelectorAll('.admin-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                document.querySelectorAll('.admin-content').forEach(c => c.classList.remove('active'));
                document.getElementById(`admin-${tab.dataset.tab}`).classList.add('active');

                if (tab.dataset.tab === 'orders') loadAdminOrders();
                if (tab.dataset.tab === 'products') loadAdminProducts();
                if (tab.dataset.tab === 'users') loadAdminUsers();
                if (tab.dataset.tab === 'p2p') loadAdminP2PCards();
                if (tab.dataset.tab === 'system') loadAdminSystemCheck();
            });
        });

        document.getElementById('admin-back')?.addEventListener('click', () => navigateTo('profile'));
        document.getElementById('admin-order-status')?.addEventListener('change', loadAdminOrders);
        document.getElementById('add-category-btn')?.addEventListener('click', showAddCategoryModal);
        document.getElementById('add-product-btn')?.addEventListener('click', () => showProductModal());
        document.getElementById('refresh-products-btn')?.addEventListener('click', loadAdminProducts);
        document.getElementById('add-p2p-card-btn')?.addEventListener('click', showAddP2PCardModal);
        document.getElementById('refresh-p2p-cards-btn')?.addEventListener('click', loadAdminP2PCards);
        document.getElementById('run-system-check-btn')?.addEventListener('click', loadAdminSystemCheck);
        document.getElementById('parse-humo-test-btn')?.addEventListener('click', showP2PParseTestModal);
        document.getElementById('process-humo-test-btn')?.addEventListener('click', showP2PProcessTestModal);
        state.adminEventsBound = true;
    }
}

async function loadAdminOrders() {
    try {
        const status = document.getElementById('admin-order-status')?.value || '';
        const path = status ? `/admin/orders?status=${encodeURIComponent(status)}` : '/admin/orders';
        const orders = await api('GET', path);
        const container = document.getElementById('admin-orders-list');

        container.innerHTML = orders?.map(order => `
            <div class="admin-order-item">
                <div class="header">
                    <div>
                        <strong>#${escapeHtml(order.order_number)}</strong>
                        <div style="font-size: 12px; color: var(--text-muted);">User ID: ${escapeHtml(order.user_id || '-')}</div>
                    </div>
                    <div class="status status-${order.status}">${escapeHtml(order.status)}</div>
                </div>
                <div>Total: ${formatMoney(order.total_amount, 'UZS')}</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">
                    Target: ${escapeHtml(order.target_id || '-')} ${order.target_server ? ` / ${escapeHtml(order.target_server)}` : ''}
                </div>
                <div class="admin-mini-list">
                    ${order.items?.map(item => `
                        <div class="admin-mini-row">
                            <span>${escapeHtml(item.variation?.name || tr('product'))}</span>
                            <span>${formatMoney(item.total_price, 'UZS')}</span>
                        </div>
                    `).join('') || ''}
                </div>
                <div class="actions">
                    ${(order.status === 'payment_submitted' || order.status === 'awaiting_payment') ? `
                        <button onclick="updateOrderStatus(${order.id}, 'paid')">Confirm Paid</button>
                    ` : ''}
                    ${(order.status === 'paid' || order.status === 'processing') ? `
                        <button onclick="fulfillOrder(${order.id})">Send MooGold</button>
                    ` : ''}
                    ${order.status === 'processing' ? `
                        <button onclick="updateOrderStatus(${order.id}, 'completed')">Complete</button>
                    ` : ''}
                    ${order.status !== 'completed' && order.status !== 'cancelled' ? `
                        <button onclick="updateOrderStatus(${order.id}, 'cancelled')">Отменить</button>
                    ` : ''}
                </div>
            </div>
        `).join('') || '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No orders</div>';
    } catch (error) {
        console.error('Admin orders error:', error);
        showToast('error', 'Failed to load admin orders');
    }
}

async function updateOrderStatus(orderId, status) {
    try {
        const result = await api('POST', `/admin/orders/${orderId}/status`, { status });
        showToast('success', result?.moogold_queued ? `Order ${status}, MooGold queued` : `Order ${status}`);
        loadAdminOrders();
    } catch (error) {
        showToast('error', 'Failed to update order');
    }
}

async function fulfillOrder(orderId) {
    try {
        await api('POST', `/admin/orders/${orderId}/fulfill`);
        showToast('success', 'MooGold fulfillment queued');
        loadAdminOrders();
    } catch (error) {
        showToast('error', error.message || 'Failed to queue MooGold');
    }
}

async function loadAdminProducts() {
    try {
        const [products, categories] = await Promise.all([
            api('GET', '/admin/products'),
            api('GET', '/admin/categories'),
        ]);
        state.adminProducts = products || [];
        state.adminCategories = categories || [];
        const container = document.getElementById('admin-products-list');

        container.innerHTML = state.adminProducts?.map(p => `
            <div class="admin-order-item">
                <div class="header">
                    <div>
                        <strong>${escapeHtml(p.name)}</strong>
                        <div style="font-size: 12px; color: var(--text-muted);">
                            ${escapeHtml(p.category?.name || 'No category')} • Product MooGold ID: ${escapeHtml(p.moogold_id || '-')}<br>
                            Requirements: ${p.requires_target_id ? escapeHtml(p.target_id_label || 'ID') : 'no ID'}${p.requires_server_id ? ' • ' + escapeHtml(p.target_server_label || 'Server') : ''}${p.requires_region ? ' • ' + escapeHtml(p.target_region_label || 'Регион') : ''}
                        </div>
                    </div>
                    <div class="status ${p.is_active ? 'status-completed' : 'status-cancelled'}">${p.is_active ? 'active' : 'off'}</div>
                </div>
                ${p.description ? `<div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 8px;">${escapeHtml(p.description)}</div>` : ''}
                <div class="admin-variation-list">
                    ${(p.variations || []).map(v => `
                        <div class="admin-variation-row">
                            <div>
                                <strong>${escapeHtml(v.name)}</strong>
                                <div style="font-size: 12px; color: var(--text-muted);">
                                    ${escapeHtml(v.stock_status)} • MooGold variation: ${escapeHtml(v.moogold_variation_id || '-')}
                                </div>
                            </div>
                            <div style="text-align: right;">
                                <div style="color: var(--neon-green);">${formatMoney(v.price, 'UZS')}</div>
                                <div class="inline-actions">
                                    <button onclick="showVariationModal(${p.id}, ${v.id})">Edit</button>
                                    <button onclick="deleteVariation(${v.id})">Off</button>
                                </div>
                            </div>
                        </div>
                    `).join('') || '<div style="color: var(--text-muted); font-size: 13px;">No variations yet. Add 86/172/257 etc.</div>'}
                </div>
                <div class="actions">
                    <button onclick="showProductModal(${p.id})">Edit Product</button>
                    <button onclick="showVariationModal(${p.id})">+ Variation</button>
                    <button style="color: var(--neon-red);" onclick="deleteProduct(${p.id})">Disable</button>
                </div>
            </div>
        `).join('') || '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No products</div>';
    } catch (error) {
        console.error('Admin products error:', error);
        showToast('error', 'Failed to load products');
    }
}

function categoryOptions(selectedId = null) {
    return (state.adminCategories || []).map(c => `
        <option value="${c.id}" ${Number(selectedId) === Number(c.id) ? 'selected' : ''}>${escapeHtml(c.name)}</option>
    `).join('');
}

function regionOptionsToLines(options = []) {
    if (!Array.isArray(options)) return '';
    return options.map(r => `${r.code}=${r.label}`).join('\n');
}

function parseРегионOptionsFromLines(text) {
    return String(text || '')
        .split('\n')
        .map(line => line.trim())
        .filter(Boolean)
        .map(line => {
            const idx = line.indexOf('=');
            if (idx === -1) return { code: line.toLowerCase().replace(/[^a-z0-9_]+/g, '_'), label: line };
            return {
                code: line.slice(0, idx).trim(),
                label: line.slice(idx + 1).trim(),
            };
        })
        .filter(r => r.code && r.label);
}

function showAddCategoryModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-sheet">
            <div class="modal-header">
                <h2>📁 Add Category</h2>
                <button class="modal-close">&times;</button>
            </div>
            <div class="form-section admin-form">
                <label>Name</label>
                <input id="cat-name" placeholder="Mobile Legends" />
                <label>Slug</label>
                <input id="cat-slug" placeholder="mobile-legends" />
                <label>Icon</label>
                <input id="cat-icon" placeholder="🎮" />
                <label>Sort order</label>
                <input id="cat-sort" inputmode="numeric" value="0" />
                <button class="btn-primary" id="save-category-btn">Save Category</button>
            </div>
        </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', closeModal);
    modal.querySelector('#cat-name').addEventListener('input', (e) => {
        const slug = e.target.value.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
        if (!document.getElementById('cat-slug').value) document.getElementById('cat-slug').value = slug;
    });
    modal.querySelector('#save-category-btn').addEventListener('click', saveCategory);
}

async function saveCategory() {
    try {
        const payload = {
            name: document.getElementById('cat-name').value.trim(),
            slug: document.getElementById('cat-slug').value.trim(),
            icon: document.getElementById('cat-icon').value.trim() || null,
            sort_order: Number(document.getElementById('cat-sort').value || 0),
        };
        await api('POST', '/admin/categories', payload);
        closeModal();
        showToast('success', 'Category saved');
        loadAdminProducts();
    } catch (error) {
        showToast('error', error.message || 'Failed to save category');
    }
}

function showProductModal(productId = null) {
    const product = productId ? (state.adminProducts || []).find(p => p.id === productId) : null;
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-sheet">
            <div class="modal-header">
                <h2>${product ? '✏️ Edit Product' : '➕ Add Product'}</h2>
                <button class="modal-close">&times;</button>
            </div>
            <div class="form-section admin-form">
                <label>Name</label>
                <input id="product-name" placeholder="Mobile Legends" value="${escapeHtml(product?.name || '')}" />
                <label>Category</label>
                <select id="product-category">${categoryOptions(product?.category_id)}</select>
                <label>Description</label>
                <textarea id="product-description" placeholder="Short product description">${escapeHtml(product?.description || '')}</textarea>
                <label>Image URL</label>
                <input id="product-image" placeholder="https://..." value="${escapeHtml(product?.image_url || '')}" />
                <label>MooGold Product ID</label>
                <input id="product-moogold" inputmode="numeric" placeholder="Optional" value="${escapeHtml(product?.moogold_id || '')}" />

                <label>Account type</label>
                <select id="product-target-type">
                    <option value="game_id" ${product?.target_type === 'game_id' ? 'selected' : ''}>Game / User ID</option>
                    <option value="telegram_username" ${product?.target_type === 'telegram_username' ? 'selected' : ''}>Telegram username</option>
                    <option value="none" ${product?.target_type === 'none' ? 'selected' : ''}>No account data</option>
                </select>
                <label class="checkbox-row"><input type="checkbox" id="product-req-target" ${product?.requires_target_id !== false ? 'checked' : ''}> Requires player/user ID</label>
                <input id="product-target-label" placeholder="ID игрока / Telegram username" value="${escapeHtml(product?.target_id_label || 'ID игрока / аккаунта')}" />
                <label class="checkbox-row"><input type="checkbox" id="product-req-server" ${product?.requires_server_id ? 'checked' : ''}> Requires server ID</label>
                <input id="product-server-label" placeholder="ID сервера" value="${escapeHtml(product?.target_server_label || 'Server ID')}" />
                <label class="checkbox-row"><input type="checkbox" id="product-req-region" ${product?.requires_region ? 'checked' : ''}> Requires region</label>
                <input id="product-region-label" placeholder="Регион" value="${escapeHtml(product?.target_region_label || 'Регион')}" />
                <label>Регион options, one per line: code=label</label>
                <textarea id="product-region-options" placeholder="uz_global=🇺🇿 UZB / 🌐 Global
uz_ph=🇺🇿 UZB / 🇵🇭 PH
ru=🇷🇺 RU">${escapeHtml(regionOptionsToLines(product?.region_options || []))}</textarea>
                <label>Input help text</label>
                <textarea id="product-help" placeholder="Например: проверьте ID и сервер перед покупкой">${escapeHtml(product?.input_help_text || '')}</textarea>

                <label>Sort order</label>
                <input id="product-sort" inputmode="numeric" value="${escapeHtml(product?.sort_order ?? 0)}" />
                <button class="btn-primary" id="save-product-btn">Save Product</button>
            </div>
        </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', closeModal);
    modal.querySelector('#save-product-btn').addEventListener('click', () => saveProduct(product?.id || null));
}

async function saveProduct(productId = null) {
    try {
        const payload = {
            name: document.getElementById('product-name').value.trim(),
            category_id: Number(document.getElementById('product-category').value),
            description: document.getElementById('product-description').value.trim() || null,
            image_url: document.getElementById('product-image').value.trim() || null,
            moogold_id: document.getElementById('product-moogold').value ? Number(document.getElementById('product-moogold').value) : null,
            target_type: document.getElementById('product-target-type').value,
            requires_target_id: document.getElementById('product-req-target').checked,
            requires_server_id: document.getElementById('product-req-server').checked,
            requires_region: document.getElementById('product-req-region').checked,
            target_id_label: document.getElementById('product-target-label').value.trim() || 'ID игрока / аккаунта',
            target_server_label: document.getElementById('product-server-label').value.trim() || 'Server ID',
            target_region_label: document.getElementById('product-region-label').value.trim() || 'Регион',
            region_options: parseРегионOptionsFromLines(document.getElementById('product-region-options').value),
            input_help_text: document.getElementById('product-help').value.trim() || null,
            sort_order: Number(document.getElementById('product-sort').value || 0),
        };
        if (productId) {
            await api('PUT', `/admin/products/${productId}`, payload);
        } else {
            await api('POST', '/admin/products', payload);
        }
        closeModal();
        showToast('success', 'Product saved');
        loadAdminProducts();
    } catch (error) {
        showToast('error', error.message || 'Failed to save product');
    }
}

function showVariationModal(productId, variationId = null) {
    const product = (state.adminProducts || []).find(p => p.id === productId);
    const variation = variationId ? (product?.variations || []).find(v => v.id === variationId) : null;
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-sheet">
            <div class="modal-header">
                <h2>${variation ? '✏️ Edit Variation' : '➕ Add Variation'}</h2>
                <button class="modal-close">&times;</button>
            </div>
            <div class="form-section admin-form">
                <label>Variation name</label>
                <input id="variation-name" placeholder="86 Diamonds" value="${escapeHtml(variation?.name || '')}" />
                <label>Price in UZS</label>
                <input id="variation-price" inputmode="numeric" placeholder="18000" value="${escapeHtml(variation?.price ?? '')}" />
                <label>Stock status</label>
                <select id="variation-stock">
                    <option value="instock" ${variation?.stock_status === 'instock' ? 'selected' : ''}>instock</option>
                    <option value="outofstock" ${variation?.stock_status === 'outofstock' ? 'selected' : ''}>outofstock</option>
                </select>
                <label>MooGold Variation ID</label>
                <input id="variation-moogold" inputmode="numeric" placeholder="Required for auto delivery" value="${escapeHtml(variation?.moogold_variation_id || '')}" />
                ${variation ? `
                    <label class="checkbox-row"><input type="checkbox" id="variation-active" ${variation.is_active ? 'checked' : ''}> Active</label>
                ` : ''}
                <button class="btn-primary" id="save-variation-btn">Save Variation</button>
            </div>
        </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', closeModal);
    modal.querySelector('#save-variation-btn').addEventListener('click', () => saveVariation(productId, variation?.id || null));
}

async function saveVariation(productId, variationId = null) {
    try {
        const payload = {
            name: document.getElementById('variation-name').value.trim(),
            price: Number(document.getElementById('variation-price').value || 0),
            stock_status: document.getElementById('variation-stock').value,
            moogold_variation_id: document.getElementById('variation-moogold').value ? Number(document.getElementById('variation-moogold').value) : null,
        };
        if (variationId) {
            payload.is_active = document.getElementById('variation-active')?.checked ?? true;
            await api('PUT', `/admin/variations/${variationId}`, payload);
        } else {
            await api('POST', `/admin/products/${productId}/variations`, payload);
        }
        closeModal();
        showToast('success', 'Variation saved');
        loadAdminProducts();
    } catch (error) {
        showToast('error', error.message || 'Failed to save variation');
    }
}

async function deleteVariation(variationId) {
    if (!confirm('Disable this variation?')) return;
    try {
        await api('DELETE', `/admin/variations/${variationId}`);
        showToast('success', 'Variation disabled');
        loadAdminProducts();
    } catch (error) {
        showToast('error', 'Failed to disable variation');
    }
}

async function deleteProduct(productId) {
    if (!confirm('Disable this product?')) return;
    try {
        await api('DELETE', `/admin/products/${productId}`);
        showToast('success', 'Product disabled');
        loadAdminProducts();
    } catch (error) {
        showToast('error', 'Failed to disable product');
    }
}

async function loadAdminUsers() {
    try {
        const users = await api('GET', '/admin/users');
        const container = document.getElementById('admin-users-list');
        
        container.innerHTML = users?.map(u => `
            <div class="admin-order-item">
                <div class="header">
                    <div>
                        <strong>${u.first_name || 'User'} ${u.last_name || ''}</strong>
                        <div style="font-size: 12px; color: var(--text-muted);">@${u.username || u.telegram_id}</div>
                    </div>
                </div>
                <div>Orders: ${u.orders?.length || 0} | Balance: ${formatMoney(u.balance || 0, 'UZS')}</div>
                <div class="actions">
                    ${u.is_blocked ? 
                        `<button onclick="unblockUser(${u.id})">Unblock</button>` :
                        `<button onclick="blockUser(${u.id})">Block</button>`
                    }
                </div>
            </div>
        `).join('') || '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No users</div>';
    } catch (error) {
        console.error('Admin users error:', error);
    }
}

async function blockUser(userId) {
    try {
        await api('POST', `/admin/users/${userId}/block`);
        showToast('success', 'User blocked');
        loadAdminUsers();
    } catch (error) {
        showToast('error', 'Failed to block user');
    }
}

async function unblockUser(userId) {
    try {
        await api('POST', `/admin/users/${userId}/unblock`);
        showToast('success', 'User unblocked');
        loadAdminUsers();
    } catch (error) {
        showToast('error', 'Failed to unblock user');
    }
}


async function loadAdminP2PCards() {
    try {
        const cards = await api('GET', '/admin/p2p/cards');
        loadAdminP2PTopups();
        const container = document.getElementById('admin-p2p-cards-list');
        if (!container) return;
        container.innerHTML = cards?.map(card => `
            <div class="admin-order-item">
                <div class="header">
                    <div>
                        <strong>${escapeHtml(card.name)}</strong>
                        <div style="font-size: 12px; color: var(--text-muted);">${escapeHtml(card.bank_name || '')} • ${escapeHtml(card.payment_system)} • ****${escapeHtml(card.last4)}</div>
                    </div>
                    <div class="status ${card.is_active ? 'status-completed' : 'status-cancelled'}">${card.is_active ? 'active' : 'off'}</div>
                </div>
                <div>Владелец: ${escapeHtml(card.card_holder || '-')}</div>
                <div>Limits: ${formatMoney(card.min_amount || 0, 'UZS')} - ${card.max_amount ? formatMoney(card.max_amount, 'UZS') : '∞'}</div>
                <div class="actions">
                    <button onclick="toggleP2PCard(${card.id}, ${card.is_active ? 'false' : 'true'})">${card.is_active ? 'Disable' : 'Enable'}</button>
                    <button style="color: var(--neon-red);" onclick="deleteP2PCard(${card.id})">Delete</button>
                </div>
            </div>
        `).join('') || '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No P2P cards. Add one first.</div>';
    } catch (error) {
        console.error('P2P cards error:', error);
        showToast('error', 'Failed to load P2P cards');
    }
}

function showAddP2PCardModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-sheet">
            <div class="modal-header">
                <h2>💳 Add P2P Card</h2>
                <button class="modal-close">&times;</button>
            </div>
            <div class="form-section">
                <input id="p2p-name" placeholder="Name, e.g. Main Humo" />
                <input id="p2p-bank" placeholder="Bank name" />
                <select id="p2p-system">
                    <option value="humo">Humo</option>
                    <option value="uzcard">Uzcard</option>
                    <option value="visa">Visa</option>
                    <option value="other">Other</option>
                </select>
                <input id="p2p-card" placeholder="Card number" inputmode="numeric" />
                <input id="p2p-holder" placeholder="Card holder" />
                <input id="p2p-phone" placeholder="Phone number / optional" />
                <input id="p2p-min" placeholder="Min amount" inputmode="numeric" value="0" />
                <input id="p2p-max" placeholder="Max amount / optional" inputmode="numeric" />
                <button class="btn-primary" id="save-p2p-card-btn">Save Card</button>
            </div>
        </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', closeModal);
    modal.querySelector('#save-p2p-card-btn').addEventListener('click', saveP2PCard);
}

async function saveP2PCard() {
    try {
        const payload = {
            name: document.getElementById('p2p-name').value.trim(),
            bank_name: document.getElementById('p2p-bank').value.trim() || null,
            payment_system: document.getElementById('p2p-system').value,
            card_number: document.getElementById('p2p-card').value.trim(),
            card_holder: document.getElementById('p2p-holder').value.trim() || null,
            phone_number: document.getElementById('p2p-phone').value.trim() || null,
            min_amount: Number(document.getElementById('p2p-min').value || 0),
            max_amount: document.getElementById('p2p-max').value ? Number(document.getElementById('p2p-max').value) : null,
            is_active: true,
            sort_order: 0,
        };
        await api('POST', '/admin/p2p/cards', payload);
        closeModal();
        showToast('success', 'P2P card added');
        loadAdminP2PCards();
    } catch (error) {
        showToast('error', error.message || 'Failed to save card');
    }
}

async function toggleP2PCard(cardId, isActive) {
    try {
        const cards = await api('GET', '/admin/p2p/cards');
        const card = cards.find(c => c.id === cardId);
        if (!card) return;
        card.is_active = isActive;
        await api('PUT', `/admin/p2p/cards/${cardId}`, card);
        showToast('success', 'Card updated');
        loadAdminP2PCards();
    } catch (error) {
        showToast('error', 'Failed to update card');
    }
}

async function deleteP2PCard(cardId) {
    if (!confirm('Disable this card?')) return;
    try {
        await api('DELETE', `/admin/p2p/cards/${cardId}`);
        showToast('success', 'Card disabled');
        loadAdminP2PCards();
    } catch (error) {
        showToast('error', 'Failed to disable card');
    }
}



async function loadAdminP2PTopups() {
    try {
        const topups = await api('GET', '/admin/p2p/topups?limit=20');
        const container = document.getElementById('admin-p2p-topups-list');
        if (!container) return;
        container.innerHTML = topups?.map(topup => `
            <div class="admin-order-item">
                <div class="header">
                    <div>
                        <strong>Top-up #${topup.id}</strong>
                        <div style="font-size: 12px; color: var(--text-muted);">User ID: ${escapeHtml(topup.user_id)} • ****${escapeHtml(topup.card?.last4 || '-')}</div>
                    </div>
                    <div class="status status-${topup.status}">${escapeHtml(topup.status)}</div>
                </div>
                <div>Amount: ${formatMoney(topup.amount, 'UZS')}</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">
                    Expires: ${new Date(topup.expires_at).toLocaleString()} ${topup.paid_at ? `• Paid: ${new Date(topup.paid_at).toLocaleString()}` : ''}
                </div>
                ${topup.note ? `<div style="font-size: 12px; color: var(--text-secondary); margin-top: 6px; white-space: pre-wrap;">${escapeHtml(topup.note)}</div>` : ''}
                <div class="actions">
                    ${topup.status !== 'paid' && topup.status !== 'cancelled' ? `
                        <button onclick="reviewTopup(${topup.id}, 'approve')">Approve</button>
                        <button style="color: var(--neon-red);" onclick="reviewTopup(${topup.id}, 'reject')">Reject</button>
                    ` : ''}
                </div>
            </div>
        `).join('') || '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No top-ups</div>';
    } catch (error) {
        console.error('Topups load error:', error);
    }
}

async function reviewTopup(topupId, action) {
    try {
        await api('POST', `/admin/p2p/topups/${topupId}/review`, { action, note: `${action} from Mini App admin` });
        showToast('success', `Top-up ${action}d`);
        loadAdminP2PTopups();
    } catch (error) {
        showToast('error', error.message || 'Failed to review top-up');
    }
}


async function loadAdminSystemCheck() {
    const summary = document.getElementById('admin-system-summary');
    const checksBox = document.getElementById('admin-system-checks');
    if (!summary || !checksBox) return;

    summary.innerHTML = '<div class="admin-order-item">Checking system...</div>';
    checksBox.innerHTML = '';

    try {
        const report = await api('GET', '/admin/system/check');
        const statusClass = report.status === 'ready' ? 'status-completed' : 'status-cancelled';
        summary.innerHTML = `
            <div class="admin-order-item">
                <div class="header">
                    <div>
                        <strong>System status</strong>
                        <div style="font-size: 12px; color: var(--text-muted);">Critical: ${report.critical_failed} • Warnings: ${report.warnings}</div>
                    </div>
                    <div class="status ${statusClass}">${escapeHtml(report.status)}</div>
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">
                    P2P Test: ${report.test_modes?.p2p_test_mode ? 'ON' : 'OFF'} • MooGold Test: ${report.test_modes?.moogold_test_mode ? 'ON' : 'OFF'}
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                    WebApp: ${escapeHtml(report.runtime?.webapp_url || '-')}
                </div>
            </div>
        `;

        checksBox.innerHTML = (report.checks || []).map(check => `
            <div class="admin-order-item">
                <div class="header">
                    <div>
                        <strong>${check.ok ? '✅' : (check.severity === 'critical' ? '❌' : '⚠️')} ${escapeHtml(check.name)}</strong>
                        <div style="font-size: 12px; color: var(--text-muted);">${escapeHtml(check.message || '')}</div>
                    </div>
                    <div class="status ${check.ok ? 'status-completed' : (check.severity === 'critical' ? 'status-cancelled' : 'status-processing')}">${escapeHtml(check.severity)}</div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        summary.innerHTML = `<div class="admin-order-item">System check failed: ${escapeHtml(error.message || 'unknown error')}</div>`;
    }
}

function showP2PParseTestModal() {
    showP2PTestModal(false);
}

function showP2PProcessTestModal() {
    showP2PTestModal(true);
}

function showP2PTestModal(processMode) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-sheet">
            <div class="modal-header">
                <h2>${processMode ? '⚠️ Process Test Payment' : '🧪 Parse HUMO Text'}</h2>
                <button class="modal-close">&times;</button>
            </div>
            <div class="form-section">
                <textarea id="p2p-test-text" rows="8" placeholder="Paste HUMO/CardXabar message here"></textarea>
                <input id="p2p-test-source" placeholder="Source" value="admin_test" />
                <button class="btn-primary" id="run-p2p-test-btn">${processMode ? 'Process with matcher' : 'Parse only'}</button>
                <div id="p2p-test-result" style="white-space: pre-wrap; font-size: 12px; color: var(--text-secondary); margin-top: 12px;"></div>
                ${processMode ? '<div style="font-size:12px;color:var(--neon-red);margin-top:8px;">Requires P2P_TEST_MODE=true. Can credit a pending test top-up.</div>' : ''}
            </div>
        </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.modal-close').addEventListener('click', closeModal);
    modal.querySelector('#run-p2p-test-btn').addEventListener('click', async () => {
        const raw_text = document.getElementById('p2p-test-text').value;
        const source = document.getElementById('p2p-test-source').value || 'admin_test';
        const resultBox = document.getElementById('p2p-test-result');
        try {
            const endpoint = processMode ? '/admin/system/p2p/process-test' : '/admin/system/p2p/parse-test';
            const result = await api('POST', endpoint, { raw_text, source });
            resultBox.textContent = JSON.stringify(result, null, 2);
            showToast('success', processMode ? 'Processed' : 'Parsed');
            if (processMode) {
                loadAdminP2PTopups();
                loadAdminSystemCheck();
            }
        } catch (error) {
            resultBox.textContent = error.message || 'Error';
            showToast('error', error.message || 'Test failed');
        }
    });
}

// ===== Search =====
function initSearch() {
    const searchBtn = document.getElementById('search-btn');
    const searchOverlay = document.getElementById('search-overlay');
    const closeSearch = document.getElementById('close-search');
    const searchInput = document.getElementById('search-input');
    const searchResults = document.getElementById('search-results');
    
    searchBtn?.addEventListener('click', () => {
        searchOverlay.classList.remove('hidden');
        searchInput.focus();
    });
    
    closeSearch?.addEventListener('click', () => {
        searchOverlay.classList.add('hidden');
    });
    
    let searchTimeout;
    searchInput?.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        
        if (query.length < 2) {
            searchResults.innerHTML = '';
            return;
        }
        
        searchTimeout = setTimeout(async () => {
            try {
                const products = await api('GET', `/products?search=${encodeURIComponent(query)}`);
                searchResults.innerHTML = products?.map(p => `
                    <div class="order-card" data-id="${p.id}" style="margin-bottom: 8px;">
                        <div class="header">
                            <div>${escapeHtml(p.name)}</div>
                            <div style="color: var(--neon-green);">${formatMoney(p.min_price, 'UZS')}</div>
                        </div>
                    </div>
                `).join('') || '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No results</div>';
                
                searchResults.querySelectorAll('.order-card').forEach(card => {
                    card.addEventListener('click', () => {
                        searchOverlay.classList.add('hidden');
                        openProductDetail(parseInt(card.dataset.id));
                    });
                });
            } catch (error) {
                console.error('Search error:', error);
            }
        }, 300);
    });
}

// ===== Toast Notifications =====
function showToast(type, message) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ',
    };
    
    toast.innerHTML = `<span>${icons[type]}</span> ${escapeHtml(message)}`;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-20px)';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== Event Listeners =====
function initEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            navigateTo(item.dataset.page);
        });
    });
    
    // Cart button
    document.getElementById('cart-btn')?.addEventListener('click', () => {
        navigateTo('cart');
    });
    
    // Explore button
    document.getElementById('explore-btn')?.addEventListener('click', () => {
        navigateTo('catalog');
    });
    
    // Product back button
    document.getElementById('product-back')?.addEventListener('click', () => {
        navigateTo('home');
    });
    
    // Referral button
    document.getElementById('referral-btn')?.addEventListener('click', async () => {
        try {
            const result = await api('GET', '/users/referral-link');
            if (result?.link) {
                if (tg) {
                    tg.openTelegramLink(result.link);
                } else {
                    navigator.clipboard.writeText(result.link);
                    showToast('success', tr('referral_copied'));
                }
            }
        } catch (error) {
            showToast('error', tr('failed_referral'));
        }
    });
    
    const openSupport = () => {
        if (tg) {
            const SUPPORT_USERNAME = state.user?.support_username || 'your_support';
            tg.openTelegramLink(`https://t.me/${SUPPORT_USERNAME}`);
        }
    };

    // Support button
    document.getElementById('support-btn')?.addEventListener('click', openSupport);
    document.getElementById('quick-support-btn')?.addEventListener('click', openSupport);
    
    // Home quick actions with data-page
    document.querySelectorAll('#page-home .quick-action[data-page]').forEach(item => {
        item.addEventListener('click', () => {
            navigateTo(item.dataset.page);
        });
    });

    // Menu items with data-page
    document.querySelectorAll('.menu-item[data-page]').forEach(item => {
        item.addEventListener('click', () => {
            navigateTo(item.dataset.page);
        });
    });
}



// ===== Initialize =====
function init() {
    initLanguageSwitcher();
    applyTranslations(document);
    initTelegram();
    initEventListeners();
    initSearch();
}

// Start
document.addEventListener('DOMContentLoaded', init);

// Expose functions globally for onclick handlers
window.navigateTo = navigateTo;
window.updateOrderStatus = updateOrderStatus;
window.blockUser = blockUser;
window.unblockUser = unblockUser;
window.deleteProduct = deleteProduct;
window.closeModal = closeModal;


/* =========================================================
   KADI TOPUP FLOW v12 — compact clean UI
   ========================================================= */
(function () {
    const MIN_AMOUNT = 3000;
    const MAX_AMOUNT = 2000000;
    let flowAmount = 0;
    let currentTopup = null;
    let timerId = null;
    const TOPUP_TTL_MS = 5 * 60 * 1000;

    function digits(value) {
        return String(value || '').replace(/[^\d]/g, '');
    }

    function formatAmount(value) {
        const d = digits(value);
        if (!d) return '';
        return d.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    }

    function parseAmount(value) {
        return Number(digits(value) || 0);
    }

    function money(value) {
        return formatAmount(Math.round(Number(value || 0))) + ' UZS';
    }

    function safe(value) {
        return String(value ?? '').replace(/[&<>"']/g, ch => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
        }[ch]));
    }

    function formatCard(value) {
        const d = digits(value);
        if (!d) return '';
        return d.replace(/(.{4})/g, '$1 ').trim();
    }


    function parseTopupDate(value) {
        if (!value) return NaN;

        let input = String(value).trim();
        if (!input) return NaN;

        if (/^\d+$/.test(input)) {
            const numeric = Number(input);
            if (!Number.isFinite(numeric)) return NaN;
            return input.length <= 10 ? numeric * 1000 : numeric;
        }

        input = input.replace(' ', 'T');

        // Backend stores UTC datetimes without timezone. Force UTC so Telegram
        // Android/WebView does not parse them as local time and collapse timer to 00:00.
        if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(input)) {
            input += 'Z';
        }

        const parsed = Date.parse(input);
        return Number.isFinite(parsed) ? parsed : NaN;
    }

    function getTopupExpiryMs(topup) {
        const expiresAt = parseTopupDate(topup?.expires_at);
        if (Number.isFinite(expiresAt)) return expiresAt;

        const createdAt = parseTopupDate(topup?.created_at);
        if (Number.isFinite(createdAt)) return createdAt + TOPUP_TTL_MS;

        return NaN;
    }

    function getTopupSecondsLeft(topup) {
        const expiryMs = getTopupExpiryMs(topup);
        if (!Number.isFinite(expiryMs)) return 0;
        return Math.max(0, Math.floor((expiryMs - Date.now()) / 1000));
    }

    function isActiveTopup(topup) {
        return String(topup?.status || '').toLowerCase() === 'pending'
            && getTopupSecondsLeft(topup) > 0;
    }

    function secondsLeftUntil(expiresAt) {
    if (!expiresAt) return 0;

    let value = String(expiresAt).trim();

    // Normalize backend date formats:
    // "2026-06-16 10:40:50" -> "2026-06-16T10:40:50"
    value = value.replace(" ", "T");

    // If backend sends UTC without timezone, force UTC.
    // Otherwise Android/Telegram reads it as local time and timer becomes 00:00.
    if (
        /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(value)
    ) {
        value += "Z";
    }

    const end = Date.parse(value);
    if (!Number.isFinite(end)) return 0;

    return Math.max(0, Math.floor((end - Date.now()) / 1000));
}

    function mmss(seconds) {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    }

    function stopTimer() {
        if (timerId) clearInterval(timerId);
        timerId = null;
    }

    function screen() {
        let el = document.getElementById('kadi-pay-v12');
        if (!el) {
            el = document.createElement('div');
            el.id = 'kadi-pay-v12';
            document.body.appendChild(el);
        }
        return el;
    }

    function open() {
        const el = screen();
        el.classList.add('active');
        document.body.classList.add('k12-lock');
    }

    function close() {
        stopTimer();
        const el = screen();
        el.classList.remove('active');
        document.body.classList.remove('k12-lock');
    }

    async function copyValue(value) {
        const text = String(value || '');
        try {
            if (typeof copyText === 'function') {
                await copyText(text);
                return;
            }
            await navigator.clipboard.writeText(text);
            if (typeof showToast === 'function') showToast('success', 'Скопировано');
        } catch (_) {
            if (typeof showToast === 'function') showToast('error', 'Не удалось скопировать');
        }
    }

    function icon(type) {
        if (type === 'card') return `
            <svg viewBox="0 0 64 44" aria-hidden="true">
                <rect x="4" y="8" width="56" height="32" rx="8"/>
                <path d="M10 18h48"/>
                <rect x="12" y="27" width="12" height="5" rx="2"/>
                <path d="M30 30h17"/>
            </svg>`;
        if (type === 'atm') return `
            <svg viewBox="0 0 64 44" aria-hidden="true">
                <rect x="12" y="5" width="40" height="34" rx="7"/>
                <rect x="19" y="11" width="26" height="9" rx="2"/>
                <path d="M23 27h18"/>
                <path d="M32 20v13"/>
            </svg>`;
        return `
            <svg viewBox="0 0 64 44" aria-hidden="true">
                <path d="M18 25a14 14 0 0 1 28 0"/>
                <rect x="11" y="22" width="9" height="13" rx="4"/>
                <rect x="44" y="22" width="9" height="13" rx="4"/>
                <path d="M44 34c-3 5-8 7-15 7"/>
                <circle cx="27" cy="41" r="3"/>
            </svg>`;
    }

    function header(back) {
        return `
            <div class="k12-header">
                <button class="k12-pill" data-back="${back}">${tr('back')}</button>
                <div class="k12-brand">
                    <div class="k12-logo">K</div>
                    <div>
                        <div class="k12-brand-title">KADI</div>
                        <div class="k12-brand-sub">TOP UP. PLAY MORE.</div>
                    </div>
                </div>
                <button class="k12-pill k12-lang">RU</button>
            </div>`;
    }

    function bindBack(el) {
        const back = el.querySelector('[data-back]');
        if (!back) return;
        back.addEventListener('click', () => {
            const action = back.dataset.back;
            if (action === 'amount') return renderAmount(flowAmount);
            if (action === 'method') return renderMethod(flowAmount);
            close();
        });
    }

    function renderAmount(defaultAmount = 0) {
        stopTimer();
        open();
        const el = screen();
        el.innerHTML = `
            <div class="k12-shell">
                ${header('close')}

                <section class="k12-headline">
                    <div class="k12-eyebrow">KADI WALLET</div>
                    <h1>${tr('topup_amount_title')}</h1>
                    <p>${tr('topup_amount_subtitle')}</p>
                </section>

                <section class="k12-panel">
                    <div class="k12-field-top">
                        <span>${tr('amount')}</span>
                        <b>UZS</b>
                    </div>

                    <label class="k12-input-box">
                        <input id="k12-amount" inputmode="numeric" autocomplete="off" placeholder="50 000" value="${defaultAmount ? formatAmount(defaultAmount) : ''}">
                        <span>UZS</span>
                    </label>

                    <div class="k12-chips">
                        <button data-amount="10000">10k</button>
                        <button data-amount="20000">20k</button>
                        <button data-amount="50000">50k</button>
                        <button data-amount="100000">100k</button>
                    </div>

                    <div class="k12-limits">
                        <div><span>${tr('minimum')}</span><b>3 000 UZS</b></div>
                        <div><span>${tr('maximum')}</span><b>2 000 000 UZS</b></div>
                        <div><span>${tr('payment_time')}</span><b>${tr('five_minutes')}</b></div>
                    </div>

                    <button class="k12-main-btn" id="k12-next">${tr('continue')}</button>
                    <div class="k12-error" id="k12-error"></div>
                </section>
            </div>`;

        bindBack(el);

        const input = el.querySelector('#k12-amount');
        const error = el.querySelector('#k12-error');
        const chips = [...el.querySelectorAll('.k12-chips button')];

        input.addEventListener('input', () => {
            input.value = formatAmount(input.value);
            chips.forEach(x => x.classList.remove('active'));
            error.textContent = '';
        });

        chips.forEach(btn => btn.addEventListener('click', () => {
            input.value = formatAmount(btn.dataset.amount);
            chips.forEach(x => x.classList.remove('active'));
            btn.classList.add('active');
            error.textContent = '';
        }));

        el.querySelector('#k12-next').addEventListener('click', () => {
            const amount = parseAmount(input.value);
            if (amount < MIN_AMOUNT) {
                error.textContent = tr('min_amount_error', { amount: '3 000 UZS' });
                return;
            }
            if (amount > MAX_AMOUNT) {
                error.textContent = tr('max_amount_error', { amount: '2 000 000 UZS' });
                return;
            }
            flowAmount = amount;
            createTopup(amount);
        });

        setTimeout(() => input.focus(), 120);
    }

    function renderMethod(amount) {
        stopTimer();
        open();
        const el = screen();
        el.innerHTML = `
            <div class="k12-shell">
                ${header('amount')}

                <section class="k12-headline compact center">
                    <h1>${tr('topup_method_title')}</h1>
                    <p>${tr('topup_method_subtitle')}</p>
                </section>

                <div class="k12-summary">
                    <span>${tr('payable')}</span>
                    <b>${money(amount)}</b>
                </div>

                <section class="k12-method-grid">
                    <button class="k12-method active" data-method="card">
                        <div class="k12-method-icon">${icon('card')}</div>
                        <b>${tr('pay_by_card')}</b>
                    </button>
                    <button class="k12-method disabled" disabled>
                        <div class="k12-method-icon">${icon('atm')}</div>
                        <b>${tr('atm')}</b>
                    </button>
                    <button class="k12-method disabled wide" disabled>
                        <div class="k12-method-icon">${icon('support')}</div>
                        <b>${tr('via_support')}</b>
                    </button>
                </section>

                <button class="k12-main-btn" id="k12-create">${tr('continue')}</button>
                <div class="k12-error" id="k12-method-error"></div>
            </div>`;

        bindBack(el);
        el.querySelector('#k12-create').addEventListener('click', () => createTopup(amount));
    }

    function getCard(topup) {
        return topup?.card || topup?.payment_card || {};
    }
    function getCardNumber(topup) {
        const c = getCard(topup);
        return c.card_number || c.number || topup?.card_number || '';
    }
    function getHolder(topup) {
        const c = getCard(topup);
        return c.holder_name || c.holder || c.card_holder || c.owner || '';
    }
    function getSystem(topup) {
        const c = getCard(topup);
        return String(c.system || c.payment_system || 'HUMO').toUpperCase();
    }

    async function createTopup(amount) {
        const el = screen();
        const btn = el.querySelector('#k12-create') || el.querySelector('#k12-next');
        const error = el.querySelector('#k12-method-error') || el.querySelector('#k12-error');
        if (btn) {
            btn.disabled = true;
            btn.textContent = tr('getting_card');
        }
        if (error) error.textContent = '';

        try {
            const topup = await api('POST', '/payments/topups', { amount });
            currentTopup = topup;
            renderPay(topup);
        } catch (e) {
            try {
                const activeTopup = await api('GET', '/payments/topups/active');
                if (isActiveTopup(activeTopup)) {
                    currentTopup = activeTopup;
                    renderPay(activeTopup);
                    return;
                }
            } catch (_) {}

            try {
                const topups = await api('GET', '/payments/topups/my');
                const activePending = (topups || []).find(isActiveTopup);
                if (activePending) {
                    currentTopup = activePending;
                    renderPay(activePending);
                    return;
                }
            } catch (_) {}

            if (error) error.textContent = e?.message || tr('failed_get_card');
            if (btn) {
                btn.disabled = false;
                btn.textContent = tr('continue');
            }
        }
    }

    function renderPay(topup) {
        currentTopup = topup;
        const el = screen();

        const amount = Number(topup.amount || flowAmount || 0);
        const cardNumber = getCardNumber(topup);
        const holder = getHolder(topup);
        const system = getSystem(topup);

        el.innerHTML = `
            <div class="k12-shell">
                ${header('amount')}

                <section class="k12-pay-panel">
                    <div class="k12-pay-timer">
                        <span>${tr('time_left')}</span>
                        <b id="k12-timer">00:00</b>
                    </div>

                    <div class="k12-pay-card-row">
                        <div class="k12-card-main">
                            <div class="k12-card-system">${safe(system)}</div>
                            <div class="k12-card-number">${safe(formatCard(cardNumber))}</div>
                            <div class="k12-holder">${safe(holder || 'CARD HOLDER')}</div>
                        </div>
                        <button class="k12-copy-btn" id="k12-copy-card">${tr('copy')}</button>
                    </div>

                    <div class="k12-pay-amount">
                        <div>
                            <span>${tr('amount_to_pay')}</span>
                            <b>${money(amount)}</b>
                        </div>
                        <button class="k12-copy-btn" id="k12-copy-amount">${tr('copy')}</button>
                    </div>

                    <div class="k12-rules">
                        <div class="k12-rules-title">${tr('rules')}</div>
                        <p class="ok"><b>✓</b> ${tr('pay_within_5_minutes')}</p>
                        <p class="ok"><b>✓</b> ${tr('send_exact_amount')}</p>
                        <p class="bad"><b>×</b> ${tr('do_not_pay_from_atm')}</p>
                        <p class="bad"><b>×</b> ${tr('do_not_send_other_amount')}</p>
                    </div>

                    <div class="k12-expired-note" id="k12-expired-note" hidden>${tr('payment_expired_note')}</div>
                    <button class="k12-main-btn kadi-pay-paid-btn-v15" id="k12-paid" type="button">${tr('i_paid')}</button>
                    <button class="k12-cancel" id="k12-cancel">${tr('cancel_topup')}</button>
                </section>
            </div>`;

        bindBack(el);

        const copyCardBtn = el.querySelector('#k12-copy-card');
        if (copyCardBtn) {
            copyCardBtn.addEventListener('click', () => copyValue(digits(cardNumber)));
        }

        const copyAmountBtn = el.querySelector('#k12-copy-amount');
        if (copyAmountBtn) {
            copyAmountBtn.addEventListener('click', () => copyValue(Math.round(amount)));
        }

        const paidBtn = el.querySelector('#k12-paid');
        if (paidBtn) {
            paidBtn.addEventListener('click', () => {
                if (typeof window.kadiPayWaitForPaymentV15 === 'function') {
                    window.kadiPayWaitForPaymentV15();
                }
            });
        }

        const cancelBtn = el.querySelector('#k12-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', async () => {
                try {
                    if (topup?.id) await api('POST', `/payments/topups/${topup.id}/cancel`);
                    showToast('success', 'Пополнение отменено');
                } catch (e) {
                    console.warn('Topup cancel error:', e);
                    showToast('info', 'Пополнение закрыто');
                } finally {
                    close();
                }
            });
        }

        startTimer(topup);
    }

function startTimer(topup) {
        stopTimer();

        const el = screen();
        const timerEl = el.querySelector('#k12-timer');
        const timerLabel =
            el.querySelector('#k12-timer-label') ||
            el.querySelector('.k12-pay-timer span') ||
            el.querySelector('.k12-timer span');

        const expiredNote = el.querySelector('#k12-expired-note');
        const cancelBtn = el.querySelector('#k12-cancel');

        function setExpiredState() {
            el.classList.add('k12-topup-expired');

            if (timerLabel) timerLabel.textContent = tr('status');
            if (timerEl) timerEl.textContent = tr('time_expired');
            if (expiredNote) expiredNote.hidden = false;
            if (cancelBtn) cancelBtn.textContent = tr('back_to_amount');

            el.querySelectorAll('.kadi-pay-paid-btn-v15, .kadi-paid-btn, .kadi-paid-btn-v13, #k12-paid').forEach(btn => {
                btn.disabled = true;
                btn.textContent = tr('time_expired');
            });
        }

        function tick() {
            const secondsLeft = getTopupSecondsLeft(topup);

            if (secondsLeft <= 0) {
                setExpiredState();
                stopTimer();
                return;
            }

            el.classList.remove('k12-topup-expired');
            if (timerLabel) timerLabel.textContent = tr('time_left');
            if (timerEl) timerEl.textContent = mmss(secondsLeft);
            if (expiredNote) expiredNote.hidden = true;
        }

        tick();

        if (getTopupSecondsLeft(topup) > 0) {
            timerId = setInterval(tick, 1000);
        }
    }

    function prepareButtons() {
        const btn = document.getElementById('hero-topup-btn');
        if (btn) {
            btn.removeAttribute('data-page');
            btn.setAttribute('data-open-kadi-topup', '1');
        }
    }

    document.addEventListener('DOMContentLoaded', prepareButtons);
    setTimeout(prepareButtons, 400);
    setTimeout(prepareButtons, 1200);

    window.addEventListener('click', function (event) {
        prepareButtons();
        const target = event.target.closest('#hero-topup-btn, [data-open-kadi-topup]');
        if (!target) return;
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        renderAmount(0);
    }, true);

    window.openKadiTopupFlow = renderAmount;
    window.renderKadiTopupV12 = renderAmount;
})();


/* KADI v12.1: reset overlay scroll after every render */
(function () {
    function resetKadiScroll() {
        const el = document.getElementById('kadi-pay-v12') || document.getElementById('kadi-pay-v11');
        if (!el) return;
        setTimeout(() => {
            el.scrollTop = 0;
            window.scrollTo(0, 0);
        }, 30);
    }

    document.addEventListener('click', function (e) {
        if (e.target.closest('#hero-topup-btn, [data-open-kadi-topup], .k12-back, .k12-primary, .k12-method')) {
            resetKadiScroll();
        }
    }, true);

    const oldOpen = window.openKadiTopupFlow;
    if (typeof oldOpen === 'function') {
        window.openKadiTopupFlow = function () {
            const res = oldOpen.apply(this, arguments);
            resetKadiScroll();
            return res;
        };
    }

    window.resetKadiScroll = resetKadiScroll;
})();

/* KADI TIMER FINAL FIX — force UTC parsing for backend dates */
(function () {
    function parseKadiDate(value) {
        if (!value) return NaN;

        let s = String(value).trim();

        // backend sometimes sends "2026-06-16 10:40:50"
        s = s.replace(' ', 'T');

        // timestamp support
        if (/^\d+$/.test(s)) {
            const n = Number(s);
            return s.length <= 10 ? n * 1000 : n;
        }

        // if timezone already exists
        if (/[zZ]$/.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)) {
            return Date.parse(s);
        }

        // if no timezone, backend date is UTC
        return Date.parse(s + 'Z');
    }

    window.secondsLeftUntil = function (expiresAt) {
        const end = parseKadiDate(expiresAt);

        if (!Number.isFinite(end)) {
            return 0;
        }

        return Math.max(0, Math.floor((end - Date.now()) / 1000));
    };

    window.kadiParseDate = parseKadiDate;

    console.log('KADI TIMER FINAL FIX loaded');
})();

/* KADI production safety: hide fake payment test button */
(function () {
    const blockedLabels = [
        'Тест платежа',
        'Process Test Payment',
        'Test Payment',
        'Test to‘lov'
    ];

    function removeTestPaymentButtons() {
        document.querySelectorAll('button').forEach((btn) => {
            const text = (btn.textContent || '').trim();
            if (blockedLabels.some(label => text.includes(label))) {
                btn.remove();
            }
        });
    }

    document.addEventListener('DOMContentLoaded', removeTestPaymentButtons);
    document.addEventListener('click', () => setTimeout(removeTestPaymentButtons, 100));
    setInterval(removeTestPaymentButtons, 1000);
})();


/* KADI: paid button wait flow */
(function () {
    if (window.confirmBalanceTopupPaid) return;

    let kadiPaidWaitTimer = null;

    function setPaidButtonLoading(isLoading) {
        document.querySelectorAll('.kadi-paid-btn').forEach(btn => {
            btn.disabled = isLoading;
            btn.textContent = isLoading ? 'Ожидаем оплату...' : 'Я оплатил';
        });
    }

    function showPaidWaitNotice() {
        const box = document.getElementById('active-topup-box');
        if (!box || box.querySelector('.kadi-paid-wait')) return;

        const notice = document.createElement('div');
        notice.className = 'kadi-paid-wait';
        notice.innerHTML = `
            <div class="kadi-paid-wait-title">Проверяем оплату</div>
            <div class="kadi-paid-wait-text">
                Обычно подтверждение занимает 10–60 секунд.
                Баланс пополнится автоматически после уведомления банка.
            </div>
        `;
        box.prepend(notice);
    }

    async function refreshBalanceSoft() {
        try {
            if (typeof loadUserBalance === 'function') await loadUserBalance();
        } catch (e) {}
        try {
            if (typeof loadBalance === 'function') await loadBalance();
        } catch (e) {}
        try {
            if (typeof updateBalance === 'function') await updateBalance();
        } catch (e) {}
    }

    window.confirmBalanceTopupPaid = async function (topupId) {
        if (kadiPaidWaitTimer) {
            clearTimeout(kadiPaidWaitTimer);
            kadiPaidWaitTimer = null;
        }

        setPaidButtonLoading(true);
        showPaidWaitNotice();

        if (typeof showToast === 'function') {
            showToast('success', 'Ожидаем подтверждение банка...');
        }

        let attempts = 0;
        const maxAttempts = 80; // about 4 minutes

        async function checkTopupStatus() {
            attempts += 1;

            try {
                const topups = await api('GET', '/payments/topups/my');
                const topup = (topups || []).find(t => Number(t.id) === Number(topupId));

                if (topup && topup.status === 'paid') {
                    await refreshBalanceSoft();

                    if (typeof showToast === 'function') {
                        showToast('success', 'Баланс пополнен ✅');
                    }

                    setTimeout(() => {
                        if (typeof navigateTo === 'function') {
                            navigateTo('home');
                        } else {
                            location.hash = '#home';
                        }
                    }, 800);

                    return;
                }

                if (topup && ['expired', 'cancelled', 'rejected'].includes(String(topup.status))) {
                    setPaidButtonLoading(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Платёж не найден или пополнение отменено');
                    }
                    return;
                }

                if (attempts >= maxAttempts) {
                    setPaidButtonLoading(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Пока не нашли платёж. Если оплатили — напишите в поддержку.');
                    }
                    return;
                }

                kadiPaidWaitTimer = setTimeout(checkTopupStatus, 3000);
            } catch (e) {
                if (attempts >= maxAttempts) {
                    setPaidButtonLoading(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Не удалось проверить оплату');
                    }
                    return;
                }
                kadiPaidWaitTimer = setTimeout(checkTopupStatus, 3000);
            }
        }

        await checkTopupStatus();
    };
})();


/* KADI_PAID_BUTTON_V13: robust "Я оплатил" button */
(function () {
    const MARKER = 'KADI_PAID_BUTTON_V13';
    let waitTimer = null;

    function paidText() {
        return tr('i_paid');
    }

    function waitText() {
        return tr('waiting_confirmation');
    }

    function insertPaidButton() {
        const box = document.getElementById('active-topup-box');
        if (!box) return;

        if (box.querySelector('.kadi-paid-btn-v13')) return;

        const text = box.innerText || '';
        const hasTopup = /HUMO|UZCARD|Карта|Сумма|UZS|Активное пополнение/i.test(text);
        if (!hasTopup) return;

        const btn = document.createElement('button');
        btn.className = 'btn-primary kadi-paid-btn-v13';
        btn.type = 'button';
        btn.textContent = paidText();
        btn.onclick = function () {
            window.kadiWaitForTopupPaidV13();
        };

        const cancelBtn = box.querySelector('button[onclick*="cancelBalanceTopup"]');
        if (cancelBtn && cancelBtn.parentNode) {
            cancelBtn.parentNode.insertBefore(btn, cancelBtn);
        } else {
            box.appendChild(btn);
        }
    }

    function showWaitNotice() {
        const box = document.getElementById('active-topup-box');
        if (!box || box.querySelector('.kadi-paid-wait-v13')) return;

        const notice = document.createElement('div');
        notice.className = 'kadi-paid-wait-v13';
        notice.innerHTML = `
            <b>${tr('checking_payment_title')}</b>
            <span>${tr('checking_payment_hint')}</span>
        `;
        box.prepend(notice);
    }

    function setButtonWaiting(waiting) {
        document.querySelectorAll('.kadi-paid-btn-v13').forEach(btn => {
            btn.disabled = waiting;
            btn.textContent = waiting ? waitText() : paidText();
        });
    }

    async function softRefreshBalance() {
        try { if (typeof loadUserBalance === 'function') await loadUserBalance(); } catch (e) {}
        try { if (typeof loadBalance === 'function') await loadBalance(); } catch (e) {}
        try { if (typeof updateBalance === 'function') await updateBalance(); } catch (e) {}
    }

    window.kadiWaitForTopupPaidV13 = async function () {
        if (waitTimer) clearTimeout(waitTimer);

        showWaitNotice();
        setButtonWaiting(true);

        if (typeof showToast === 'function') {
            showToast('success', 'Ожидаем подтверждение банка...');
        }

        let attempts = 0;
        const maxAttempts = 90;

        async function check() {
            attempts++;

            try {
                const topups = await api('GET', '/payments/topups/my');
                const list = Array.isArray(topups) ? topups : [];
                const latest = list[0];
                const pending = list.find(t => String(t.status) === 'pending');

                if (latest && String(latest.status) === 'paid') {
                    await softRefreshBalance();

                    if (typeof showToast === 'function') {
                        showToast('success', 'Баланс пополнен ✅');
                    }

                    setTimeout(() => {
                        if (typeof navigateTo === 'function') {
                            navigateTo('home');
                        } else {
                            location.hash = '#home';
                        }
                    }, 700);

                    return;
                }

                if (!pending && latest && ['cancelled', 'expired', 'rejected'].includes(String(latest.status))) {
                    setButtonWaiting(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Платёж не найден или пополнение отменено');
                    }
                    return;
                }

                if (attempts >= maxAttempts) {
                    setButtonWaiting(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Пока не нашли платёж. Если оплатили — напишите в поддержку.');
                    }
                    return;
                }

                waitTimer = setTimeout(check, 3000);
            } catch (e) {
                if (attempts >= maxAttempts) {
                    setButtonWaiting(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Не удалось проверить оплату');
                    }
                    return;
                }
                waitTimer = setTimeout(check, 3000);
            }
        }

        await check();
    };

    setInterval(insertPaidButton, 1000);

    const observer = new MutationObserver(insertPaidButton);
    observer.observe(document.documentElement, { childList: true, subtree: true });

    document.addEventListener('DOMContentLoaded', insertPaidButton);
    window.addEventListener('load', insertPaidButton);

    console.log(MARKER + ' loaded');
})();


/* KADI_NO_PROFILE_TOPUP_V14: top-up is separate flow, not profile block */
(function () {
    const MARKER = 'KADI_NO_PROFILE_TOPUP_V14';

    function removeProfileTopupSection() {
        document.querySelectorAll('.wallet-topup-section').forEach(el => {
            el.remove();
        });

        document.querySelectorAll('.kadi-paid-btn-v13, .kadi-paid-wait-v13').forEach(el => {
            const inProfile = el.closest('#profile-page, .profile-page, .wallet-topup-section');
            if (inProfile) el.remove();
        });
    }

    function openTopupFlowSafe() {
        if (typeof window.openKadiTopupFlow === 'function') {
            window.openKadiTopupFlow();
            return true;
        }

        if (typeof openKadiTopupFlow === 'function') {
            openKadiTopupFlow();
            return true;
        }

        if (typeof navigateTo === 'function') {
            navigateTo('profile');
            setTimeout(removeProfileTopupSection, 300);
        }

        return false;
    }

    document.addEventListener('click', function (event) {
        const target = event.target.closest(
            '#hero-topup-btn, .hero-cta#hero-topup-btn, [data-open-kadi-topup], [data-page="profile"].quick-action'
        );

        if (!target) return;

        const text = (target.innerText || '').toLowerCase();
        const isTopupButton =
            target.id === 'hero-topup-btn' ||
            target.hasAttribute('data-open-kadi-topup') ||
            text.includes('пополн') ||
            text.includes('top up') ||
            text.includes('to‘ld');

        if (!isTopupButton) return;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        openTopupFlowSafe();
    }, true);

    setInterval(removeProfileTopupSection, 700);
    document.addEventListener('DOMContentLoaded', removeProfileTopupSection);
    window.addEventListener('load', removeProfileTopupSection);

    console.log(MARKER + ' loaded');
})();


/* KADI_PAY_PAID_BUTTON_V15: paid button for standalone payment screen */
(function () {
    const MARKER = 'KADI_PAY_PAID_BUTTON_V15';
    let waitTimer = null;

    function isPaymentScreen() {
        const overlay = document.getElementById('kadi-pay-v12');
        const root = overlay || document;
        return !!(
            root.querySelector('.k12-pay-panel') &&
            root.querySelector('.k12-pay-amount') &&
            root.querySelector('.k12-pay-card-row') &&
            (root.querySelector('#k12-paid') || root.querySelector('#k12-cancel'))
        );
    }

    function findCancelButton() {
        const k12Cancel = document.getElementById('k12-cancel');
        if (k12Cancel) return k12Cancel;

        const buttons = Array.from(document.querySelectorAll('button'));
        return buttons.find(btn => /Отменить пополнение|Отменить/i.test(btn.innerText || ''));
    }

    function insertButton() {
        if (!isPaymentScreen()) return;
        if (document.querySelector('.k12-topup-expired')) return;
        if (document.querySelector('.kadi-pay-paid-btn-v15')) return;

        const cancelBtn = findCancelButton();
        if (!cancelBtn || !cancelBtn.parentNode) return;

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'kadi-pay-paid-btn-v15';
        btn.textContent = tr('i_paid');
        btn.onclick = function () {
            waitForPayment();
        };

        cancelBtn.parentNode.insertBefore(btn, cancelBtn);
    }

    function showWaitBlock() {
        if (document.querySelector('.kadi-pay-wait-v15')) return;

        const cancelBtn = findCancelButton();
        if (!cancelBtn || !cancelBtn.parentNode) return;

        const block = document.createElement('div');
        block.className = 'kadi-pay-wait-v15';
        block.innerHTML = `
            <b>${tr('checking_payment_title')}</b>
            <span>${tr('checking_payment_hint')}</span>
        `;

        cancelBtn.parentNode.insertBefore(block, cancelBtn);
    }

    function setWaiting(waiting) {
        document.querySelectorAll('.kadi-pay-paid-btn-v15').forEach(btn => {
            btn.disabled = waiting;
            btn.textContent = waiting ? tr('waiting_confirmation') : tr('i_paid');
        });
    }

    async function refreshBalanceSoft() {
        try { if (typeof loadUserBalance === 'function') await loadUserBalance(); } catch (e) {}
        try { if (typeof loadBalance === 'function') await loadBalance(); } catch (e) {}
        try { if (typeof updateBalance === 'function') await updateBalance(); } catch (e) {}
    }

    async function goHome() {
        await refreshBalanceSoft();

        if (typeof showToast === 'function') {
            showToast('success', 'Баланс пополнен ✅');
        }

        setTimeout(() => {
            if (typeof navigateTo === 'function') {
                navigateTo('home');
            } else {
                location.hash = '#home';
            }
        }, 700);
    }

    async function waitForPayment() {
        if (waitTimer) clearTimeout(waitTimer);

        setWaiting(true);
        showWaitBlock();

        if (typeof showToast === 'function') {
            showToast('success', 'Ожидаем подтверждение банка...');
        }

        let attempts = 0;
        const maxAttempts = 90;

        async function check() {
            attempts++;

            try {
                const topups = await api('GET', '/payments/topups/my');
                const list = Array.isArray(topups) ? topups : [];

                const latest = list[0];
                const paid = list.find(t => String(t.status) === 'paid');
                const pending = list.find(t => String(t.status) === 'pending');

                if (paid && (!pending || Number(paid.id) >= Number(pending.id || 0))) {
                    await goHome();
                    return;
                }

                if (!pending && latest && ['expired', 'cancelled', 'rejected'].includes(String(latest.status))) {
                    setWaiting(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Платёж не найден или пополнение отменено');
                    }
                    return;
                }

                if (attempts >= maxAttempts) {
                    setWaiting(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Пока не нашли платёж. Если оплатили — напишите в поддержку.');
                    }
                    return;
                }

                waitTimer = setTimeout(check, 3000);
            } catch (e) {
                if (attempts >= maxAttempts) {
                    setWaiting(false);
                    if (typeof showToast === 'function') {
                        showToast('error', 'Не удалось проверить оплату');
                    }
                    return;
                }

                waitTimer = setTimeout(check, 3000);
            }
        }

        await check();
    }

    window.kadiPayWaitForPaymentV15 = waitForPayment;

    setInterval(insertButton, 700);

    const observer = new MutationObserver(insertButton);
    observer.observe(document.documentElement, { childList: true, subtree: true });

    document.addEventListener('DOMContentLoaded', insertButton);
    window.addEventListener('load', insertButton);

    console.log(MARKER + ' loaded');
})();


/* KADI_PAY_CLOSE_OVERLAY_V16: close payment overlay after successful top-up */
(function () {
    const MARKER = 'KADI_PAY_CLOSE_OVERLAY_V16';
    let timer = null;
    let startedAt = 0;

    function hasPayWait() {
        return !!document.querySelector('.kadi-pay-wait-v15, .kadi-paid-wait-v13');
    }

    function isPayScreenVisible() {
        const overlay = document.getElementById('kadi-pay-v12');
        if (!overlay) return false;

        return !!(
            overlay.querySelector('.k12-pay-panel') &&
            (overlay.querySelector('#k12-paid') || overlay.querySelector('#k12-cancel'))
        );
    }

    function closePayOverlay() {
        const selectors = [
            '#kadi-pay-v11',
            '#kadi-pay-v12',
            '#kadi-pay-flow',
            '#kadi-pay-overlay',
            '.kadi-pay-overlay',
            '.kadi-pay-flow',
            '.kadi-topup-overlay'
        ];

        selectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                try { el.remove(); } catch (e) {}
            });
        });

        document.body.style.overflow = '';
        document.documentElement.style.overflow = '';
    }

    async function refreshBalanceSoft() {
        try { if (typeof loadUserBalance === 'function') await loadUserBalance(); } catch (e) {}
        try { if (typeof loadBalance === 'function') await loadBalance(); } catch (e) {}
        try { if (typeof updateBalance === 'function') await updateBalance(); } catch (e) {}
    }

    async function goHomeAfterPaid() {
        await refreshBalanceSoft();

        closePayOverlay();

        if (typeof navigateTo === 'function') {
            navigateTo('home');
        } else {
            location.hash = '#home';
        }

        if (typeof showToast === 'function') {
            showToast('success', 'Баланс пополнен ✅');
        }
    }

    async function checkPaidAndClose() {
        if (!hasPayWait() && !isPayScreenVisible()) return;

        try {
            const topups = await api('GET', '/payments/topups/my');
            const list = Array.isArray(topups) ? topups : [];

            const latest = list[0];
            const pending = list.find(t => String(t.status) === 'pending');

            if (latest && String(latest.status) === 'paid' && !pending) {
                await goHomeAfterPaid();
                if (timer) clearInterval(timer);
                timer = null;
                return;
            }
        } catch (e) {}
    }

    function startWatcher() {
        startedAt = Date.now();

        if (timer) clearInterval(timer);

        timer = setInterval(checkPaidAndClose, 2000);
        checkPaidAndClose();
    }

    document.addEventListener('click', function (event) {
        const btn = event.target.closest('.kadi-pay-paid-btn-v15, .kadi-paid-btn-v13');
        if (!btn) return;
        setTimeout(startWatcher, 500);
    }, true);

    document.addEventListener('visibilitychange', function () {
        if (!document.hidden && (hasPayWait() || isPayScreenVisible())) {
            startWatcher();
        }
    });

    window.addEventListener('focus', function () {
        if (hasPayWait() || isPayScreenVisible()) {
            startWatcher();
        }
    });

    setInterval(function () {
        if (hasPayWait()) checkPaidAndClose();
    }, 3000);

    console.log(MARKER + ' loaded');
})();


/* KADI_MANUAL_COMPLETE_FORCE_V2: force manual completion instead of MooGold */
(function () {
    const MARKER = 'KADI_MANUAL_COMPLETE_FORCE_V2';

    async function manualCompleteOrder(orderId) {
        if (!orderId) return;

        const ok = confirm('Отметить заказ как выполненный?');
        if (!ok) return;

        try {
            await api('POST', `/admin/orders/${orderId}/status`, { status: 'completed' });

            if (typeof showToast === 'function') {
                showToast('success', 'Заказ выполнен ✅');
            }

            if (typeof loadAdminOrders === 'function') {
                await loadAdminOrders();
            }
        } catch (e) {
            if (typeof showToast === 'function') {
                showToast('error', e.message || 'Не удалось выполнить заказ');
            } else {
                alert(e.message || 'Не удалось выполнить заказ');
            }
        }
    }

    // Even if old button still calls fulfillOrder(orderId), make it manual completion.
    window.fulfillOrder = manualCompleteOrder;
    window.kadiManualCompleteOrder = manualCompleteOrder;

    function patchButtons() {
        document.querySelectorAll('button').forEach(btn => {
            const text = (btn.innerText || '').trim().toLowerCase();
            const onclick = btn.getAttribute('onclick') || '';

            if (text.includes('send moogold') || onclick.includes('fulfillOrder')) {
                const match = onclick.match(/fulfillOrder\((\d+)\)/);
                if (!match) return;

                const orderId = match[1];

                btn.innerText = '✅ Выполнено';
                btn.classList.add('kadi-complete-order-btn');
                btn.setAttribute('onclick', `kadiManualCompleteOrder(${orderId})`);
            }
        });
    }

    setInterval(patchButtons, 500);

    const observer = new MutationObserver(patchButtons);
    observer.observe(document.documentElement, { childList: true, subtree: true });

    document.addEventListener('DOMContentLoaded', patchButtons);
    window.addEventListener('load', patchButtons);

    console.log(MARKER + ' loaded');
})();


/* KADI_CLEAR_CART_AFTER_ORDER_V1: clear cart after successful balance checkout */
(function () {
    const MARKER = 'KADI_CLEAR_CART_AFTER_ORDER_V1';

    function kadiClearCartStorage() {
        try {
            const keys = [];

            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (!key) continue;

                if (/cart|basket|korzina|kadi_cart|cartItems/i.test(key)) {
                    keys.push(key);
                }
            }

            keys.forEach(key => localStorage.removeItem(key));
        } catch (e) {}

        try {
            const keys = [];

            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                if (!key) continue;

                if (/cart|basket|korzina|kadi_cart|cartItems/i.test(key)) {
                    keys.push(key);
                }
            }

            keys.forEach(key => sessionStorage.removeItem(key));
        } catch (e) {}

        try {
            if (Array.isArray(window.cart)) window.cart.length = 0;
            if (Array.isArray(window.cartItems)) window.cartItems.length = 0;
            if (Array.isArray(window.basket)) window.basket.length = 0;
        } catch (e) {}
    }

    async function kadiRefreshAfterCartClear() {
        try { if (typeof updateCartBadge === 'function') updateCartBadge(); } catch (e) {}
        try { if (typeof renderCart === 'function') renderCart(); } catch (e) {}
        try { if (typeof loadCart === 'function') await loadCart(); } catch (e) {}
        try { if (typeof loadUserBalance === 'function') await loadUserBalance(); } catch (e) {}
        try { if (typeof loadBalance === 'function') await loadBalance(); } catch (e) {}
        try { if (typeof updateBalance === 'function') await updateBalance(); } catch (e) {}
    }

    async function kadiClearCartAfterOrder() {
        kadiClearCartStorage();
        await kadiRefreshAfterCartClear();

        if (typeof showToast === 'function') {
            showToast('success', 'Заказ создан ✅ Корзина очищена');
        }
    }

    function patchApiForCartClear() {
        if (window.__kadiClearCartApiPatched) return;
        if (typeof window.api !== 'function') return;

        const originalApi = window.api;

        window.api = async function (method, endpoint, data) {
            const result = await originalApi.apply(this, arguments);

            const m = String(method || '').toUpperCase();
            const e = String(endpoint || '');

            if (m === 'POST' && /\/orders\/?$/.test(e)) {
                setTimeout(kadiClearCartAfterOrder, 100);
            }

            return result;
        };

        window.__kadiClearCartApiPatched = true;
    }

    patchApiForCartClear();
    setInterval(patchApiForCartClear, 1000);

    console.log(MARKER + ' loaded');
})();


/* KADI_TELEGRAM_SCROLL_UNLOCK_V1: unlock scroll for Telegram WebApp */
(function () {
    const MARKER = 'KADI_TELEGRAM_SCROLL_UNLOCK_V1';

    function expandTelegramWebApp() {
        try {
            if (window.Telegram && window.Telegram.WebApp) {
                window.Telegram.WebApp.ready();
                window.Telegram.WebApp.expand();
            }
        } catch (e) {}
    }

    function unlockScroll() {
        try {
            document.documentElement.style.overflowY = 'auto';
            document.documentElement.style.height = 'auto';

            document.body.style.overflowY = 'auto';
            document.body.style.height = 'auto';
            document.body.style.position = 'relative';
            document.body.style.touchAction = 'pan-y';
        } catch (e) {}
    }

    function addBottomSpace() {
        try {
            let spacer = document.getElementById('kadi-scroll-bottom-spacer');
            if (!spacer) {
                spacer = document.createElement('div');
                spacer.id = 'kadi-scroll-bottom-spacer';
                spacer.style.height = '140px';
                spacer.style.minHeight = '140px';
                spacer.style.pointerEvents = 'none';
                document.body.appendChild(spacer);
            }
        } catch (e) {}
    }

    function applyScrollFix() {
        expandTelegramWebApp();
        unlockScroll();
        addBottomSpace();
    }

    applyScrollFix();
    document.addEventListener('DOMContentLoaded', applyScrollFix);
    window.addEventListener('load', applyScrollFix);
    window.addEventListener('resize', applyScrollFix);
    setInterval(applyScrollFix, 1000);

    console.log(MARKER + ' loaded');
})();


// KADI_REMOVE_EMPTY_PROFILE_HISTORY_CARD_V1
function kadiRemoveEmptyProfileHistoryCard() {
    try {
        if (state.currentPage !== 'profile') return;

        const page = document.getElementById('page-content') || document.body;
        const allowedTexts = [
            'Реферальная программа',
            'Поддержка',
            'Админ-панель',
            'Настройки',
            'Язык',
            'Условия',
            'Политика'
        ];

        const candidates = page.querySelectorAll('.profile-menu-item, .menu-item, .profile-option, .profile-action, button, a, div');

        candidates.forEach((el) => {
            const text = (el.innerText || '').replace(/\s+/g, ' ').trim();

            if (!text) return;

            const isAllowed = allowedTexts.some((word) => text.includes(word));
            const looksLikeOldHistory =
                text === '📦' ||
                text === '📦 ›' ||
                text === '📦 >' ||
                text.includes('Моя история') ||
                text.includes('My history') ||
                text.includes('My History');

            if (looksLikeOldHistory && !isAllowed) {
                el.remove();
            }
        });

        // дополнительная защита: удаляем большую пустую карточку перед "Реферальная программа"
        const allCards = Array.from(page.querySelectorAll('.profile-menu-item, .menu-item, .profile-option, .profile-action, .card'));
        allCards.forEach((el) => {
            const text = (el.innerText || '').replace(/\s+/g, ' ').trim();
            const hasReferralAfter = el.nextElementSibling && (el.nextElementSibling.innerText || '').includes('Реферальная программа');

            if (hasReferralAfter && (text === '' || text === '📦' || text === '📦 ›')) {
                el.remove();
            }
        });
    } catch (e) {
        console.warn('KADI remove empty profile history card failed:', e);
    }
}

const kadiOldLoadProfilePageV1 = loadProfilePage;
loadProfilePage = async function(...args) {
    const result = await kadiOldLoadProfilePageV1.apply(this, args);
    setTimeout(kadiRemoveEmptyProfileHistoryCard, 50);
    setTimeout(kadiRemoveEmptyProfileHistoryCard, 300);
    return result;
};
