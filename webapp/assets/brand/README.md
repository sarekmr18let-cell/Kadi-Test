# KADI brand assets

Text-based KADI dark-neon brand assets for the Telegram Mini App UI.

This folder intentionally keeps only source assets that are safe to review in Git:

- `kadi-mark.svg` — scalable standalone K mark using the KADI cyan-to-violet gradient, soft glow, and bold geometry for small-size readability.
- `kadi-full-logo.svg` — transparent full logo lockup with KADI and TOP UP. PLAY MORE. for dark UI contexts only.

PNG files are intentionally not committed because binary files are not supported in this change. Export runtime PNG deliverables later from the SVG sources when needed, for example:

- `kadi-telegram-avatar-512.png` from `kadi-mark.svg`
- `kadi-app-icon-512.png` from `kadi-mark.svg`
- `kadi-header-logo-transparent.png` from `kadi-full-logo.svg`
