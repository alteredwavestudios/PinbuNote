"""v0.96 finishing features: safe labels + platform UI regressions.

Pure metadata tests run on Linux without Qt. Native tests run automatically on
GitHub's Windows/macOS runners where PySide6 is available.
"""
from __future__ import annotations

import copy
import os
import pytest

from yomunote.navigator_research_display import build_display_rows, group_reference_labels
from yomunote.page_groups import page_node, group_node
from yomunote.research import empty_research, new_reference, set_assignment


def reference_fixture():
    research = empty_research()
    book = new_reference(research, {'type': 'book', 'title': 'Study Notes',
                                   'authors': ['Bernasco, Jacques'], 'year': '2015'})
    root = group_node('Chapter 1', [page_node('p1'), page_node('p2')])
    sub = group_node('Subchapter', [page_node('p3')])
    root['children'].append(sub)
    other = group_node('Other', [page_node('p4')])
    set_assignment(research, 'groups', root['id'], book)
    pages = [{'id': f'p{i}', 'title': f'Original page {i}',
              'source_page': i+375, 'source': 'originals/book.pdf'} for i in range(1, 5)]
    return research, [root, other], pages, root, sub, book


def test_reference_labels_off_preserves_all_original_titles():
    research, tree, pages, root, sub, book = reference_fixture()
    before = copy.deepcopy((research, tree, pages))
    rows = build_display_rows(research, tree, pages, reference_labels=False)
    assert all('display_title' not in row for row in rows.values())
    assert group_reference_labels(research, tree, enabled=False) == {}
    assert (research, tree, pages) == before


def test_reference_labels_on_uses_inherited_locator_but_never_writes_to_notebook():
    research, tree, pages, root, sub, book = reference_fixture()
    before = copy.deepcopy((research, tree, pages))
    rows = build_display_rows(research, tree, pages, reference_labels=True)
    assert rows['p1']['display_title'] == 'Bernasco (2015) · p. 376'
    assert rows['p2']['display_title'] == 'Bernasco (2015) · p. 377'
    assert 'display_title' not in rows['p4']
    group_labels = group_reference_labels(research, tree, enabled=True)
    assert group_labels[root['id']] == 'Bernasco (2015) · Chapter 1'
    assert group_labels[sub['id']] == 'Bernasco (2015) · Subchapter'
    assert (research, tree, pages) == before


def test_explicit_reference_exclusion_does_not_generate_false_labels():
    research, tree, pages, root, sub, book = reference_fixture()
    set_assignment(research, 'groups', sub['id'], None)
    set_assignment(research, 'pages', 'p2', None)
    rows = build_display_rows(research, tree, pages, reference_labels=True)
    groups = group_reference_labels(research, tree, enabled=True)
    assert 'display_title' not in rows['p2']
    assert 'display_title' not in rows['p3']
    assert sub['id'] not in groups
    assert root['id'] in groups


def test_reference_labels_do_not_override_manual_page_title_or_bookmark():
    research, tree, pages, root, sub, book = reference_fixture()
    pages[0]['title'] = 'Keep my original title'
    pages[0]['bookmark'] = 'Argument 1'
    rows = build_display_rows(research, tree, pages, reference_labels=True)
    assert rows['p1']['title'] == 'Keep my original title'
    assert rows['p1']['display_title'].startswith('Bernasco (2015)')
    assert pages[0]['bookmark'] == 'Argument 1'


def test_version_increases_from_stability_release():
    from yomunote import __version__
    from yomunote.notebook import _version_sortkey
    assert _version_sortkey(__version__) > _version_sortkey('0.95')


# Real Qt tests intentionally skip on a headless machine WITHOUT PySide6,
# but run on CI machines after installing requirements.txt.
try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QTreeWidgetItem
    from PySide6.QtCore import Qt
    HAS_QT = True
except ImportError:
    HAS_QT = False


def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.skipif(not HAS_QT, reason='PySide6 not installed')
def test_reference_labels_cannot_leak_into_group_tree_saved_names():
    app()
    from yomunote.page_groups_ui import PageGroupsTree
    research, tree, pages, root, sub, book = reference_fixture()
    widget = PageGroupsTree()
    widget.load_tree(tree, pages, active_page='p1')
    widget.set_research_display(
        build_display_rows(research, tree, pages, reference_labels=True),
        group_labels=group_reference_labels(research, tree, enabled=True))
    assert widget.find_item('group', root['id']).text(0).startswith('Bernasco')
    assert widget.find_item('page', 'p1').text(0).startswith('Bernasco')
    extracted = widget.extract_tree()
    assert extracted[0]['name'] == 'Chapter 1'
    assert extracted[0]['children'][-1]['name'] == 'Subchapter'
    widget.close()


@pytest.mark.skipif(not HAS_QT, reason='PySide6 not installed')
def test_title_editor_edits_stored_not_synthetic_title():
    app()
    from yomunote.window import PageTitleEditor
    widget = PageTitleEditor()
    widget._has_page = True
    widget.setText('Bernasco (2015) · p. 376', original='Original PDF page')
    widget.start_edit()
    assert widget.edit.text() == 'Original PDF page'
    widget.cancel()
    widget.close()


@pytest.mark.skipif(not HAS_QT, reason='PySide6 not installed')
def test_shortcut_help_uses_live_menu_keys_and_is_searchable():
    app()
    from yomunote.shortcut_reference import KeyboardShortcutsDialog, menu_shortcut_rows
    window = QMainWindow()
    menu = window.menuBar().addMenu('&File')
    action = menu.addAction('Save Project')
    action.setShortcut('Ctrl+S')
    rows = menu_shortcut_rows(window)
    assert any(category == 'File' and title == 'Save Project' for category, title, _ in rows)
    dialog = KeyboardShortcutsDialog(window)
    dialog._filter('Save Project')
    assert not dialog.tree.topLevelItem(0).isHidden()
    dialog.close()
    window.close()


@pytest.mark.skipif(not HAS_QT, reason='PySide6 not installed')
def test_fullscreen_remembers_maximised_state():
    app()
    from yomunote.window import MainWindow
    window = QMainWindow()
    window.showMaximized()
    # The method only needs the QWidget interface, not a full notebook.
    MainWindow.toggle_fullscreen(window, True)
    assert window.isFullScreen()
    MainWindow.toggle_fullscreen(window, False)
    assert window.isMaximized()
    window.close()
