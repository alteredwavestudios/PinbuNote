"""Pinbu Note 0.8.7a release contracts without Qt, plus SQLite compatibility."""
from pathlib import Path
from yomunote.notebook import Notebook
from yomunote.vector_marks import make_sticky, valid_sticky, translated_vector
from yomunote.project import unique_project_path

ROOT = Path(__file__).resolve().parents[1]

def test_new_extension_stays_portable_with_legacy_extension(tmp_path):
    old = Notebook.create(tmp_path, 'Legacy')
    assert old.path.suffix == '.yomunote'
    old.close()
    new = Notebook.create(tmp_path, 'New', extension='.pinbunote')
    assert new.path.suffix == '.pinbunote'
    new.close()
    for name in ('Legacy.yomunote', 'New.pinbunote'):
        reopened = Notebook.load(tmp_path / name)
        assert reopened.tabs
        reopened.close()

def test_sticky_style_fields_are_optional_for_old_notebooks():
    old = make_sticky(text='hello')
    old.pop('show_background')
    old.pop('alignment')
    old.pop('letter_spacing_pct')
    assert valid_sticky(old)
    modern = make_sticky(text='• first\n• second', alignment='center',
                         show_background=False, letter_spacing_pct=115)
    assert valid_sticky(modern)
    moved = translated_vector(modern, .1, .2)
    assert moved['x'] > modern['x']
    assert moved['y'] > modern['y']

def test_rebrand_sticky_and_palette_source_contract():
    window = (ROOT/'yomunote/window.py').read_text(encoding='utf-8')
    composer = (ROOT/'yomunote/sticky_note_dialog.py').read_text(encoding='utf-8')
    assert 'class PinbuWordmark(QWidget)' in (ROOT/'yomunote/ui.py').read_text(encoding='utf-8')
    assert 'stickyPlaceRequested.emit' in window
    assert "'sticky_place'" in window
    assert "'photo', 'sticky'" in window
    assert all(x in window for x in ("'pinbu-quilt'", "'silk-sampler'", "'indigo-stitch'"))
    assert '_toggle_bullets' in composer
    assert 'PercentageSpacing' in composer
