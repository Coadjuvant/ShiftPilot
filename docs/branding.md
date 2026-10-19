# ShiftPilot / Shift Grid

The selected mark has three independent shift blocks. Their colors stay the
same in both themes: top Medical Blue `#28aeca`, middle Brand Blue `#0033a0`,
bottom Effective Blue `#377cb5`.

The light wordmark uses Deep Blue `#071b45` for Shift and Brand Blue for Pilot.
The dark wordmark is Clear White `#ffffff`. Shapes use solid fills with no
gradients. Wordmark text is outlined so the SVG does not need an installed font.

`frontend/public/brand/` contains light/dark transparent SVG banners and PNG
exports, an icon-only SVG, SVG and multi-size ICO favicons, 192/512 PNG icons,
an Apple touch icon, and the icon manifest. A white favicon tile preserves
contrast in both light and dark browser chrome.

To regenerate locally, install Pillow, fonttools, and PyMuPDF in a development
environment and run `python scripts/build-brand-assets.py`. It defaults to
Windows Arial Bold; on another platform supply a licensed bold sans-serif TTF
with `--font /path/to/font.ttf`. Raster exports are rendered from the same
vector source. No font file is distributed or downloaded at runtime.

Previous logo files are retained for compatibility; the header and document
icons use the new `/brand/` paths to avoid the old cached favicon URLs.
