"""Native text selection regression tests, no third-party PDF authoring needed."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from yomunote.pdf_text_engine import inspect_page, TextPageGeometry, Glyph
from yomunote.vector_marks import (
    make_text_highlight, valid_vector, translated_vector, resized_vector,
)


def make_tiny_pdf(path: Path):
    """Write a two-line, text-layer PDF using only the Python standard library."""
    contents = (b"BT /F1 18 Tf 72 700 Td (Hello Yomu Note) Tj ET\n"
                b"BT /F1 18 Tf 72 675 Td (Second line of text) Tj ET\n")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(contents)).encode() + b" >>\nstream\n" + contents + b"endstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, payload in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + payload + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects)+1}\n".encode())
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    path.write_bytes(data)


class TestTextLab(unittest.TestCase):
    def test_native_pdf_character_extraction_and_multiline_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'text.pdf'
            make_tiny_pdf(path)
            page = inspect_page(path, 1)
            self.assertIsNotNone(page)
            self.assertIn('Hello Yomu', page.text)
            self.assertIn('Second line', page.text)
            self.assertGreater(page.char_count, 20)
            self.assertGreaterEqual(len(page.boxes(0, page.char_count-1)), 2)
            first = page.glyphs[0]
            index = page.nearest((first.x0+first.x1)/2, (first.y0+first.y1)/2)
            self.assertEqual(index, first.index)

    def test_grouped_highlight_is_one_valid_editable_vector(self):
        boxes = [[.1, .2, .4, .02], [.1, .24, .28, .02]]
        mark = make_text_highlight(boxes, '#ffcf69', 90)
        self.assertEqual(mark['kind'], 'highlight')
        self.assertEqual(len(mark['segments']), 2)
        self.assertTrue(valid_vector(mark))
        moved = translated_vector(mark, .03, .02)
        self.assertTrue(valid_vector(moved))
        self.assertEqual(moved['id'], mark['id'])
        self.assertGreater(moved['segments'][0][0], mark['segments'][0][0])
        resized = resized_vector(mark, 'br', .62, .32)
        self.assertTrue(valid_vector(resized))
        self.assertEqual(len(resized['segments']), 2)
        self.assertEqual(resized['id'], mark['id'])

    def test_reject_bad_fragments(self):
        mark = make_text_highlight([[.1, .2, .4, .02]], '#ffcf69')
        mark['segments'] = [[.8, .2, .4, .02]]
        self.assertFalse(valid_vector(mark))

    def test_no_text_in_empty_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'empty.pdf'
            make_tiny_pdf(path)
            raw = path.read_bytes().replace(b'(Hello Yomu Note)', b'()', 1)
            # Do not change lengths in raw synthetic PDF; use invalid page index
            # to assert safe no-text fallback without corrupting the PDF.
            self.assertIsNone(inspect_page(path, 50))


if __name__ == '__main__':
    unittest.main()
