"""Build exact-color Shift Grid SVGs and raster/icon exports.

Optional local tooling: pip install pillow fonttools pymupdf
Use --font to supply a licensed bold sans-serif TTF on non-Windows machines.
The generated wordmarks contain outlines, not a runtime font dependency.
"""
from __future__ import annotations

import argparse
from io import BytesIO
import json
import os
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "brand"
BLUE = "#0033a0"
DEEP = "#071b45"
MEDICAL = "#28aeca"
EFFECTIVE = "#377cb5"
WHITE = "#ffffff"


def svg(body: str, width: int, height: int, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">'
            f'<title id="title">{title}</title>{body}</svg>\n')


def blocks() -> str:
    return (f'<rect x="56" y="4" width="64" height="28" rx="9" fill="{MEDICAL}"/>'
            f'<rect x="4" y="44" width="64" height="28" rx="9" fill="{BLUE}"/>'
            f'<rect x="32" y="84" width="80" height="28" rx="9" fill="{EFFECTIVE}"/>')


def png(source: str, width: int) -> Image.Image:
    with pymupdf.open(stream=source.encode(), filetype="svg") as document:
        scale = width / document[0].rect.width
        pixmap = document[0].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
        return Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGBA")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path(os.getenv("WINDIR", "C:/Windows")) / "Fonts/arialbd.ttf")
    args = parser.parse_args()
    if not args.font.is_file():
        parser.error("Supply a licensed bold sans-serif TTF using --font")
    font = TTFont(args.font)
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = 96 / font["head"].unitsPerEm
    wordmark = []
    advance = 0
    for index, letter in enumerate("ShiftPilot"):
        glyph_name = cmap[ord(letter)]
        pen = SVGPathPen(glyphs)
        glyphs[glyph_name].draw(pen)
        wordmark.append((index, advance, pen.getCommands()))
        advance += font["hmtx"].metrics[glyph_name][0] * scale
    width = round(156 + advance + 16)
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        paths = "".join(
            f'<path fill="{WHITE if theme == "dark" else DEEP if index < 5 else BLUE}" '
            f'transform="translate({156 + x:.4f} 94) scale({scale:.8f} {-scale:.8f})" d="{path}"/>'
            for index, x, path in wordmark
        )
        banner = svg(blocks() + paths, width, 120, "ShiftPilot")
        (OUT / f"shiftpilot-banner-{theme}.svg").write_text(banner, encoding="utf-8")
        png(banner, width * 3).save(OUT / f"shiftpilot-banner-{theme}.png")
    (OUT / "shiftpilot-icon.svg").write_text(svg(blocks(), 128, 120, "ShiftPilot"), encoding="utf-8")
    favicon = svg(f'<rect width="128" height="128" rx="24" fill="{WHITE}"/>'
                  f'<g transform="translate(10 13) scale(.86)">{blocks()}</g>', 128, 128, "ShiftPilot")
    (OUT / "favicon.svg").write_text(favicon, encoding="utf-8")
    png(favicon, 256).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    for size in (192, 512):
        png(favicon, size).save(OUT / f"favicon-{size}.png")
    apple = svg(f'<rect width="128" height="128" fill="{WHITE}"/>'
                f'<g transform="translate(10 13) scale(.86)">{blocks()}</g>', 128, 128, "ShiftPilot")
    png(apple, 180).save(OUT / "apple-touch-icon.png")
    manifest = {"name": "ShiftPilot", "short_name": "ShiftPilot", "start_url": "/",
                "display": "browser", "background_color": WHITE, "theme_color": DEEP,
                "icons": [{"src": f"/brand/favicon-{size}.png", "sizes": f"{size}x{size}",
                           "type": "image/png", "purpose": "any"} for size in (192, 512)]}
    (OUT / "site.webmanifest").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Created brand assets in {OUT}")


if __name__ == "__main__":
    main()
