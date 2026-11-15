"""v0.8.3a Text Lab: native PDF character geometry without raster replacement.

Pure-Python geometry; the only PDFium access is inspect_page(), performed by
Yomu Note's existing background worker under its process-global PDFIUM_LOCK.
No PDFium handles, QObjects, pixmaps, or source document edits escape the worker.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path

from .pdfium_guard import PDFIUM_LOCK

MAX_CHARS = 25000
MAX_FRAGMENTS = 320


@dataclass(frozen=True)
class Glyph:
    index: int
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class TextPageGeometry:
    """Small, disposable active-page character map; all coordinates 0..1."""
    glyphs: list[Glyph]
    text: str                  # 1 codepoint per PDFium character index
    char_count: int
    # Immutable after extraction: one shallow row index built on first mouse
    # hit-test, never persisted and never shared with a PDFium handle.
    _hit_buckets: tuple[tuple[Glyph, ...], ...] | None = field(
        default=None, init=False, repr=False, compare=False)

    def _hit_candidates(self, y: float) -> tuple[Glyph, ...]:
        """Return only glyphs possibly within the original ±.045 y-band.

        Each bucket stores glyphs whose y0..y1 range, expanded by .045,
        intersects that row. Preserve input order to keep exact tie-breaking.
        The bucket count and number of pointers are bounded by MAX_CHARS.
        """
        rows = self._hit_buckets
        if rows is None:
            bins: list[list[Glyph]] = [[] for _ in range(48)]
            for g in self.glyphs:
                if not all(math.isfinite(v) for v in
                           (g.x0, g.x1, g.y0, g.y1)):
                    continue
                low = min(47, max(0, int(math.floor((g.y0 - .045) * 48))))
                high = min(47, max(0, int(math.floor((g.y1 + .045) * 48))))
                for index in range(low, high + 1):
                    bins[index].append(g)
            rows = tuple(tuple(bucket) for bucket in bins)
            self._hit_buckets = rows
        index = min(47, max(0, int(math.floor(y * 48))))
        return rows[index]

    def nearest(self, x: float, y: float) -> int | None:
        """Snap to the nearest glyph using a disposable vertical row index."""
        if (not self.glyphs or not math.isfinite(x) or not math.isfinite(y)
                or y < -.045 or y > 1.045):
            return None
        best_idx = None
        best = float('inf')
        for g in self._hit_candidates(y):
            cy = (g.y0 + g.y1) * .5
            dy = max(0.0, abs(y - cy) - (g.y1-g.y0) * .5)
            if dy > .045:  # Not on or near the selected line.
                continue
            dx = max(g.x0 - x, 0.0, x - g.x1)
            # Within a line, favour glyphs beneath the pointer.
            d = dx * dx + dy * dy * 4
            if d < best:
                best, best_idx = d, g.index
        return best_idx

    def selected_text(self, first: int, last: int) -> str:
        lo, hi = sorted((first, last))
        return self.text[max(0, lo):min(self.char_count, hi + 1)].strip()

    def boxes(self, first: int, last: int) -> list[list[float]]:
        """Merge adjacent characters on the same visual line, never columns."""
        lo, hi = sorted((first, last))
        result: list[list[float]] = []
        for g in self.glyphs:
            if g.index < lo or g.index > hi:
                continue
            if not result:
                result.append([g.x0, g.y0, g.x1, g.y1])
                continue
            old = result[-1]
            height = max(.0005, old[3] - old[1], g.y1 - g.y0)
            overlap = min(old[3], g.y1) - max(old[1], g.y0)
            gap = g.x0 - old[2]
            if (overlap >= height * .25 and
                    -height*.35 <= gap <= max(height * 1.2, .006)):
                old[0] = min(old[0], g.x0)
                old[1] = min(old[1], g.y0)
                old[2] = max(old[2], g.x1)
                old[3] = max(old[3], g.y1)
            else:
                result.append([g.x0, g.y0, g.x1, g.y1])
            if len(result) > MAX_FRAGMENTS:
                return []  # Reject enormous, potentially pathological paths.
        return [[round(x0, 7), round(y0, 7), round(x1-x0, 7), round(y1-y0, 7)]
                for x0, y0, x1, y1 in result if x1 > x0 and y1 > y0]


def inspect_page(source: Path, page_number: int) -> TextPageGeometry | None:
    """Inspect the original/converted PDF, not the cached JPEG image.

    Non-zero page crop origins and rotated pages deliberately fall back to OCR
    in this conservative alpha: incorrect highlight geometry is worse than no
    selectable text. The main PDF preview and existing tools still work.
    """
    import pypdfium2 as pdfium

    source = Path(source)
    with PDFIUM_LOCK:
        document = pdfium.PdfDocument(str(source))
        try:
            number = int(page_number) - 1
            if number < 0 or number >= len(document):
                return None
            page = document[number]
            try:
                width, height = page.get_size()
                left, bottom, right, top = page.get_bbox()
                if (page.get_rotation() != 0 or width <= 1 or height <= 1 or
                    abs(left) > .25 or abs(bottom) > .25 or
                    abs((right-left)-width) > .25 or
                    abs((top-bottom)-height) > .25):
                    return None
                textpage = page.get_textpage()
                try:
                    count = textpage.count_chars()
                    if not 1 <= count <= MAX_CHARS:
                        return None
                    chars = []
                    glyphs = []
                    for index in range(count):
                        code = pdfium.raw.FPDFText_GetUnicode(textpage.raw, index)
                        chars.append(chr(code) if 0 < code <= 0x10FFFF and
                                     not (0xD800 <= code <= 0xDFFF) else '\ufffd')
                        try:
                            a, b, c, d = textpage.get_charbox(index, loose=True)
                        except Exception:
                            continue
                        if not all(map(math.isfinite, (a, b, c, d))):
                            continue
                        # PDF (0,0) = bottom left; QGraphicsScene = top left.
                        x0, x1 = a/width, c/width
                        y0, y1 = (height-d)/height, (height-b)/height
                        if (x1-x0 <= 1e-6 or y1-y0 <= 1e-6 or
                            x0 < -0.005 or y0 < -0.005 or
                            x1 > 1.005 or y1 > 1.005):
                            continue
                        glyphs.append(Glyph(index, max(0., x0), max(0., y0),
                                            min(1., x1), min(1., y1)))
                    if len(glyphs) < 2 or not any(ch.isalnum() for ch in chars):
                        return None
                    geometry = TextPageGeometry(glyphs, ''.join(chars), count)
                    # Warm the pure-Python index inside the existing worker,
                    # not during the first mouse-drag event on the GUI thread.
                    geometry._hit_candidates(.5)
                    return geometry
                finally:
                    textpage.close()
            finally:
                page.close()
        finally:
            document.close()
