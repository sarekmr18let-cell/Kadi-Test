from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'webapp/js/app.js'
CSS = ROOT / 'webapp/css/style.css'
INDEX = ROOT / 'webapp/index.html'
I18N = ROOT / 'webapp/js/i18n.js'


def read(path):
    return path.read_text(encoding='utf-8')


class PR35AdminMobileUiStaticTests(unittest.TestCase):
    def variation_renderer(self):
        app = read(APP)
        match = re.search(r"function renderAdminVariationRow\(product, v\) \{(?P<body>.*?)\n\}", app, re.S)
        self.assertIsNotNone(match, 'renderAdminVariationRow must exist')
        return match.group('body')

    def test_variation_card_uses_vertical_structure(self):
        body = self.variation_renderer()
        for class_name in ('admin-variation-card', 'admin-variation-head', 'admin-variation-title', 'admin-variation-price', 'admin-variation-meta', 'admin-variation-finance'):
            self.assertIn(class_name, body)
        css = read(CSS)
        self.assertRegex(css, r"\.admin-variation-card\s*\{[^}]*display:\s*flex")
        self.assertRegex(css, r"\.admin-variation-card\s*\{[^}]*flex-direction:\s*column")

    def test_actions_block_inside_card_not_header_or_meta(self):
        body = self.variation_renderer()
        card_start = body.index('admin-variation-card')
        actions = body.index('admin-variation-actions')
        self.assertGreater(actions, card_start)
        self.assertGreater(actions, body.index('admin-variation-head'))
        self.assertGreater(actions, body.index('admin-variation-meta'))
        self.assertGreater(actions, body.index('admin-variation-finance'))
        self.assertNotIn('inline-actions', body)

    def test_css_admin_variation_actions(self):
        css = read(CSS)
        self.assertRegex(css, r"\.admin-variation-actions\s*\{[^}]*display:\s*flex")
        self.assertRegex(css, r"\.admin-variation-actions\s*\{[^}]*margin-top:\s*auto")
        self.assertRegex(css, r"\.admin-variation-actions button\s*\{[^}]*flex:\s*1")

    def test_admin_catalog_has_bottom_padding_for_nav(self):
        css = read(CSS)
        self.assertIn('#admin-products', css)
        self.assertIn('padding-bottom', css)
        self.assertIn('safe-area-inset-bottom', css)

    def test_provider_price_and_currency_readonly(self):
        app = read(APP)
        self.assertIn('id="variation-provider-price"', app)
        self.assertIn('id="variation-provider-currency"', app)
        self.assertRegex(app, r'id="variation-provider-price"[^>]*readonly[^>]*aria-readonly="true"')
        self.assertRegex(app, r'id="variation-provider-currency"[^>]*readonly[^>]*aria-readonly="true"')
        self.assertIn('admin-readonly-input', app)

    def test_no_inline_styles_in_variation_card_renderer(self):
        self.assertNotIn('style=', self.variation_renderer())

    def test_cache_buster_updated(self):
        index = read(INDEX)
        self.assertIn('2026062912', index)
        self.assertIn('css/style.css?v=2026062912', index)
        self.assertIn('js/app.js?v=2026062912', index)
        self.assertIn('js/i18n.js?v=2026062912', index)

    def test_js_syntax_is_valid(self):
        for rel in ['webapp/js/app.js', 'webapp/js/i18n.js', 'webapp/js/admin-catalog-utils.js']:
            subprocess.run(['node', '--check', str(ROOT / rel)], check=True)

    def test_i18n_key_sets_still_match(self):
        i18n = read(I18N)
        self.assertNotIn('admin_variation_price_readonly', i18n)


if __name__ == '__main__':
    unittest.main()
