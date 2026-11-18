"""v1.0 final-release regression contract.

The failed v0.97 annotation-to-notes experiment is fully removed, not merely
hidden in a toolbar. Testing the project format separately protects existing
notes when users open a notebook last saved with the experimental version.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from yomunote import __version__
from yomunote.preview_night import READING_MODES, recolour_image, reading_mode
from yomunote.project import Project
from yomunote.notebook import _version_sortkey

ROOT = Path(__file__).resolve().parents[1]


def test_release_identity_is_strictly_newer_than_previous_build():
    assert __version__ == '1.0'
    assert _version_sortkey('1.0') > _version_sortkey('0.97')
    assert _version_sortkey('1.0') > _version_sortkey('0.95')
    assert (ROOT / 'RELEASE_NOTES_v1.0.md').is_file()
    assert (ROOT / 'START-HERE-v1.0.md').is_file()


def test_annotation_to_notes_feature_is_not_shipped():
    removed = [
        'yomunote/annotation_notes.py',
        'yomunote/note_anchor_qt.py',
        'tests/test_v097_annotation_notes.py',
    ]
    assert all(not (ROOT / path).exists() for path in removed)
    main = (ROOT / 'yomunote/window.py').read_text(encoding='utf-8')
    project = (ROOT / 'yomunote/project.py').read_text(encoding='utf-8')
    for text in (
        'NoteLinkBadge', 'annotationLinkRequested', 'annotationContextRequested',
        'link_selected_annotation', 'return_to_source_annotation',
        'annotation_note_links', 'insert_anchor(document',
        '_pending_annotation_note_link',
    ):
        assert text not in main
    assert 'annotation_note_links' not in project
    assert 'from .annotation_notes' not in project


def test_v097_experimental_links_do_not_block_opening_or_damage_notes(tmp_path):
    project = Project.create(tmp_path, 'Experimental saved notebook')
    # A minimal valid old note page; save it first so no unrelated data differs.
    project.notes_html = '<p>My original notes remain available.</p>'
    project.save()
    path = project.path / 'project.json'
    stored = json.loads(path.read_text(encoding='utf-8'))
    stored['annotation_note_links'] = {
        'a' * 32 + '/' + 'b' * 32:
        {'note_page_id': 'c' * 32, 'anchor_id': 'pn-note-' + 'd' * 32}}
    path.write_text(json.dumps(stored), encoding='utf-8')
    loaded = Project.load(project.path)
    assert loaded.notes_html == '<p>My original notes remain available.</p>'
    loaded.save()
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert 'annotation_note_links' not in saved
    assert 'My original notes remain available.' in saved['notes_html']


def test_preview_reading_modes_are_non_destructive_and_optional():
    picture = Image.new('RGB', (80, 80), (251, 251, 251))
    picture.putpixel((3, 4), (3, 4, 5))
    before = picture.tobytes()
    assert READING_MODES == ('original', 'smart', 'inverted')
    assert reading_mode('unexpected-setting') == 'original'
    assert recolour_image(picture, 'smart').getpixel((20, 20))[0] < 50
    assert recolour_image(picture, 'smart').getpixel((3, 4))[0] > 200
    assert recolour_image(picture, 'inverted').getpixel((20, 20))[0] == 4
    assert recolour_image(picture, 'original').getpixel((20, 20))[0] == 251
    assert picture.tobytes() == before


def test_only_preview_is_recoloured_never_original_assets():
    window = (ROOT / 'yomunote/window.py').read_text(encoding='utf-8')
    assert 'def set_preview_reading_mode(self, mode):' in window
    assert "self.settings.value('previewReadingMode', 'original')" in window
    assert "controls.addAction('☾ Dark')" in window
    assert "controls.addAction('Invert')" in window
    assert 'self._apply_reading_colours(image)' in window
    assert 'self._apply_reading_colours(decoded)' in window
    assert 'self._clarity_token += 1' in window
    assert 'CompositionMode_Screen if self.reading_dark' in window


@pytest.mark.skipif(not __import__('importlib').util.find_spec('PySide6'),
                    reason='Qt/PySide6 is not installed in this environment')
def test_qt_preview_raster_and_toolbar_smoke():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage
    from yomunote.window import ImageCanvas
    app = QApplication.instance() or QApplication([])
    canvas = ImageCanvas()
    original = QImage(48, 48, QImage.Format.Format_RGB32)
    original.fill(0xFFFFFF)
    canvas.set_reading_mode('smart')
    dark = canvas._apply_reading_colours(original)
    assert dark.pixelColor(0, 0).red() < 50
    assert original.pixelColor(0, 0).red() == 255
    canvas.set_reading_mode('original')
    assert canvas._apply_reading_colours(original).pixelColor(0, 0).red() == 255
    canvas.close()
    canvas.deleteLater()


def test_complete_notebook_opens_v097_experimental_link_field(tmp_path):
    """Open a real SQLite notebook, not only a Project fixture.

    This simulates the only novel project field added by v0.97. The file path
    and note HTML are intentionally left intact so opening and resaving can
    prove that obsolete UI metadata never destroys normal study data.
    """
    import sqlite3
    from yomunote.notebook import Notebook

    nb = Notebook.create(tmp_path, 'Legacy with links', extension='.pinbunote')
    tab_id = nb.active_id
    project = nb.project(tab_id)
    project.notes_html = '<p>Keep my important study notes.</p>'
    project.save()
    nb.save()
    file = nb.path
    nb.close()
    record = f'tabs/{tab_id}/project.json'
    with sqlite3.connect(file) as db:
        payload = db.execute('SELECT data FROM files WHERE path=?', (record,)).fetchone()[0]
        obj = json.loads(payload)
        obj['annotation_note_links'] = {
            'a'*32 + '/' + 'b'*32:
                {'note_page_id':'c'*32,'anchor_id':'pn-note-'+'d'*32}}
        raw = json.dumps(obj).encode('utf-8')
        db.execute('UPDATE files SET data=?,size=? WHERE path=?', (raw,len(raw),record))
        db.commit()
    migrated = Notebook.load(file)
    try:
        loaded = migrated.project(tab_id)
        assert loaded.notes_html == '<p>Keep my important study notes.</p>'
        loaded.save()
        migrated.save()
    finally:
        migrated.close()
    with sqlite3.connect(file) as db:
        saved = json.loads(db.execute('SELECT data FROM files WHERE path=?',
                                      (record,)).fetchone()[0])
    assert 'annotation_note_links' not in saved
    assert 'Keep my important study notes.' in saved['notes_html']
