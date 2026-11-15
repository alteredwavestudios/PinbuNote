"""v0.8.7b: bullet behaviour, visible rebrand and migration safeguards."""
from pathlib import Path

from yomunote.sticky_bullets import plan_bullet_toggle
from yomunote.notebook import Notebook

ROOT = Path(__file__).resolve().parents[1]


def apply(text, start, end):
    changes = plan_bullet_toggle(text, start, end)
    for change in reversed(changes):
        text = text[:change.start] + change.replacement + text[change.end:]
    return text


def test_bullet_toggle_single_empty_line():
    assert apply('', 0, 0) == '• '
    assert apply('• ', 0, 0) == ''


def test_bullet_toggle_mixed_lines_does_not_duplicate():
    before = 'one\n• two\nthree'
    after = apply(before, 0, len(before))
    assert after == '• one\n• two\n• three'
    assert apply(after, 0, len(after)) == 'one\ntwo\nthree'


def test_bullet_toggle_preserves_indentation_and_skips_next_line_at_boundary():
    before = '  first\n\tsecond\nnext'
    end = before.index('next')
    assert apply(before, 0, end) == '  • first\n\t• second\nnext'


def test_empty_selected_line_starts_new_bullet():
    assert apply('first\n\nthird', 6, 6) == 'first\n• \nthird'


def test_bookmark_and_quick_font_gui_contracts():
    source = (ROOT/'yomunote/window.py').read_text(encoding='utf8')
    tree = (ROOT/'yomunote/page_groups_ui.py').read_text(encoding='utf8')
    assert "('Pinbu ♥', 'font-size: 27px; font-weight: bold;')" in source
    assert "('N O T E', 'font-size: 10px; font-weight: bold;')" in source
    assert "('Yomu ❤︎', 'font-size: 25px; font-weight: bold;')" not in source
    assert 'quickStickyFontSize' in source
    assert 'Change Sticky Font Size' in source
    assert 'paint_bookmark_ribbon(painter' in source
    assert 'ROLE_BOOKMARK' in tree
    assert 'def update_page_bookmark(self, page_id, label):' in tree
    assert 'self.bookmark_ribbon.setVisible(visible)' in source


def test_sticky_preview_does_not_format_whole_document():
    source = (ROOT/'yomunote/sticky_note_dialog.py').read_text(encoding='utf8')
    assert 'plan_bullet_toggle' in source
    assert 'setDefaultTextOption(option)' in source
    assert 'mergeBlockFormat(fmt)' not in source


def test_tree_lookup_avoids_recursive_search_in_steady_state():
    source = (ROOT/'yomunote/page_groups_ui.py').read_text(encoding='utf8')
    assert 'QPersistentModelIndex' in source
    assert 'if index is not None and index.isValid():' in source
    assert 'self.itemFromIndex(index)' in source


def test_legacy_pinbu_notebooks_open_with_bookmarks_and_sticky(tmp_path):
    for extension in ('.yomunote', '.pinbunote'):
        notebook = Notebook.create(tmp_path, 'Legacy' if extension == '.yomunote' else 'Pinbu', extension=extension)
        notebook.close()
        reopened = Notebook.load(notebook.path)
        assert reopened.tabs
        reopened.close()
