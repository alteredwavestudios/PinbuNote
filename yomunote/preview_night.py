"""Fast, non-destructive reading colours for *displayed* page bitmaps.

Qt and PDFium keep using the unmodified original assets for OCR, text select,
export and high-quality rendering. This module only transforms the raster that
is about to be shown in the central document preview. Nothing is written to
``cache/`` and no per-page transformed images are retained in memory.

A photograph cannot always be distinguished from coloured text with a simple
colour heuristic. The Smart Dark mode is intentionally a *best effort*;
Original is always available and is the default.
"""
from __future__ import annotations

from PIL import Image, ImageOps, ImageChops

READING_MODES = ('original', 'smart', 'inverted')
MAX_SMART_PIXELS = 6_000_000


def reading_mode(value) -> str:
    return value if value in READING_MODES else 'original'


def recolour_image(image: Image.Image, mode='original') -> Image.Image:
    """Return a NEW Pillow image; never change the caller's source bitmap.

    The grayscale LUT maps white paper to charcoal and black type to light
    grey. Saturated pixels remain closer to their original hues, which helps
    diagrams and photographs. Because this is a heuristic rather than
    document-semantic recolouring, odd scans can be viewed in Original mode.
    """
    mode = reading_mode(mode)
    source = image.convert('RGBA')
    if mode == 'original':
        return source
    if mode == 'inverted' or source.width * source.height > MAX_SMART_PIXELS:
        rgb = ImageOps.invert(source.convert('RGB'))
        rgb.putalpha(source.getchannel('A'))
        return rgb
    rgb = source.convert('RGB')
    # Paper whites land around RGB 30; pure black letters around RGB 232.
    # The single-channel mapping is performed in Pillow's native code rather
    # than a slow Python loop over every pixel.
    lum = ImageOps.grayscale(rgb)
    lut = [int(232 - 202 * (x / 255.0)) for x in range(256)]
    mono = lum.point(lut).convert('RGB')
    saturation = rgb.convert('HSV').getchannel('S')
    # Near-grayscale text and paper recolour fully. Highly saturated images
    # retain much more of their existing colour, without requiring OCR.
    mask = saturation.point([max(0, min(225, int((x - 30) * 1.45))) for x in range(256)])
    # A near-black stroke may have a tiny blue or brown cast, making its HSV
    # saturation surprisingly high. Saturation alone would preserve that ink
    # almost black on dark paper. Reduce colour preservation for dark pixels
    # so slightly tinted black writing still becomes readable light writing.
    # Both masks run in Pillow's native code, once per decoded preview image.
    lightness_weight = lum.point([min(255, int(x * 255 / 100)) for x in range(256)])
    mask = ImageChops.multiply(mask, lightness_weight)
    result = Image.composite(rgb, mono, mask)
    result.putalpha(source.getchannel('A'))
    return result
