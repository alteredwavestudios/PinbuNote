"""No-GUI source contract tests for the v0.8.3b integration build.

These deliberately import no Qt library so they can run on a CI worker that
has not installed optional GUI dependencies yet.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / 'yomunote' / 'window.py').read_text(encoding='utf-8')
PROJECT = (ROOT / 'yomunote' / 'project.py').read_text(encoding='utf-8')


def pane_method(name):
    mod = ast.parse(WINDOW)
    pane = next(n for n in mod.body if isinstance(n, ast.ClassDef) and n.name == 'ProjectPane')
    return next(n for n in pane.body if isinstance(n, ast.FunctionDef) and n.name == name)


class _Item:
    def __init__(self, identifier):
        self.identifier = identifier

    def data(self, role):
        return self.identifier


class TestSelectionAndUIMerge(unittest.TestCase):
    def test_selected_pages_from_actual_source_for_groups_and_individual(self):
        fn = pane_method('selected_pages')
        class StubQt:
            class ItemDataRole:
                UserRole = 32
        scope = {'Qt': StubQt}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<actual selected_pages>', 'exec'), scope)
        method = scope['selected_pages']

        class Pane:
            project = type('Project', (), {'pages': [{'id': f'p{i}'} for i in range(5)]})()
            group_tree = type('Tree', (), {'selected_page_ids': lambda self: ['p1', 'p3']})()
            pages_list = type('List', (), {
                'selectedItems': lambda self: [_Item('p0'), _Item('p4')],
                'currentItem': lambda self: _Item('p2'),
            })()
            _navigator_view = 'groups'
        pane = Pane()
        self.assertEqual([p['id'] for _, p in method(pane)], ['p1', 'p3'])
        pane._navigator_view = 'thumbnails'
        self.assertEqual([p['id'] for _, p in method(pane)], ['p0', 'p4'])

    def test_multi_delete_one_undo_and_both_keyboard_navigators(self):
        src = ast.get_source_segment(WINDOW, pane_method('remove_page'))
        self.assertIn("'Remove Pages'", src)
        self.assertIn('self.history.perform(CallbackAction(', src)
        self.assertIn('self._restore_removed_page_selection(', src)
        self.assertIn('self._navigator_view', src)
        self.assertIn("for key in ('Delete', 'Backspace')", WINDOW)
        self.assertIn("('Delete', self.remove_page)", WINDOW)

    def test_highlight_defaults_and_text_group_exist(self):
        self.assertIn("highlight_color: str = '#FFE536'", PROJECT)
        for name in ('marker', 'highlight', 'highlight_area', 'highlight_line'):
            self.assertRegex(WINDOW, re.escape("self.tool_styles['"+name+"']") + r'\s*=\s*\{[^}]*[\'\"]opacity[\'\"]:\s*80')
        for value in ('Text selection modes', "QAction('Select Text'", "QAction('OCR'",
                      'button_width = 43 if icon_only else 104',
                      "menu.addAction('Copy Text')", "menu.addAction('Highlight Text')",
                      "self._text_highlight_menu_action.setEnabled(available)"):
            self.assertIn(value, WINDOW)

    def test_pref_copy_is_whitelisted_and_production_read_only(self):
        from yomunote.dev_preferences import SAFE_UI_KEYS
        self.assertIn('theme', SAFE_UI_KEYS)
        self.assertIn('previewClarity', SAFE_UI_KEYS)
        self.assertFalse({'recentProjects', 'openProjects', 'backupDirectory'} & SAFE_UI_KEYS)
        self.assertIn("os.environ.get('YOMU_INTEGRATION_DEV') == '1'", WINDOW)


if __name__ == '__main__':
    unittest.main()
