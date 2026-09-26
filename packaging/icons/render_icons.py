#!/usr/bin/env python3
"""Renders PNG and ICO icon assets from the master SVG file."""

import os
from pathlib import Path
import sys

import cairo
import gi
gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg
from PIL import Image

SCRIPT_DIR = Path(__file__).parent.resolve()
SVG_PATH = SCRIPT_DIR / "org.wallforge.app.svg"
SIZES = [16, 24, 32, 48, 64, 128, 256, 512]


def render_svg_to_png(svg_path: Path, output_png: Path, size: int) -> None:
    """Render an SVG file to a PNG of specified width and height using cairo + librsvg."""
    handle = Rsvg.Handle.new_from_file(str(svg_path))
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    context = cairo.Context(surface)
    context.scale(size / 512.0, size / 512.0)
    handle.render_cairo(context)
    surface.write_to_png(str(output_png))


def main():
    print(f"[ICONS] Rendering icons from {SVG_PATH.name}...")
    png_images = []

    for size in SIZES:
        out_file = SCRIPT_DIR / f"wallforge_{size}x{size}.png"
        render_svg_to_png(SVG_PATH, out_file, size)
        print(f"  ✓ Rendered {out_file.name}")
        if size in (16, 24, 32, 48, 64, 128, 256):
            png_images.append(Image.open(out_file))

    # Save canonical 512x512 as org.wallforge.app.png
    canonical_png = SCRIPT_DIR / "org.wallforge.app.png"
    render_svg_to_png(SVG_PATH, canonical_png, 512)
    print(f"  ✓ Saved canonical {canonical_png.name}")

    # Generate multi-size Windows .ico file
    ico_path = SCRIPT_DIR / "wallforge.ico"
    if png_images:
        png_images[0].save(
            str(ico_path),
            format="ICO",
            sizes=[(img.width, img.height) for img in png_images],
            append_images=png_images[1:],
        )
        print(f"  ✓ Generated Windows icon: {ico_path.name}")

    print("[ICONS] All icon assets rendered successfully.")


if __name__ == "__main__":
    main()
