"""Native PySide6 smoke tests for v0.9.2b number badge click targets.

Skipped only when Qt isn't installed. In GitHub CI PySide6 is a dependency,
so Windows/Linux/macOS must run these checks rather than silently skipping.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtTest import QTest
from uuid import uuid4

from yomunote.page_groups_ui import PageGroupsTree, ROLE_ID
from yomunote.page_groups import page_node, group_node
from yomunote.navigator_research_display import build_display_rows
from yomunote.research import empty_research, new_reference, set_assignment


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_group_number_click_does_not_activate_page_or_toggle_read(app):
    pid = uuid4().hex
    page = {'id':pid, 'title':'Research page', 'source_page':5, 'source':'originals/book.pdf'}
    group = group_node('Chapter', [page_node(pid)])
    research = empty_research()
    rid = new_reference(research, {'type':'book', 'title':'Book One', 'year':'2025'})
    set_assignment(research, 'groups', group['id'], rid)
    rows = build_display_rows(research,[group],[page],default='smart')
    tree = PageGroupsTree()
    try:
        tree.resize(380, 270)
        tree.load_tree([group],[page],pid)
        tree.set_research_display(rows)
        tree.show()
        app.processEvents()
        item = tree.find_item('page', pid)
        assert item is not None
        index = tree.indexFromItem(item,0)
        rect = tree.itemDelegate().number_rect(tree.visualRect(index), tree._nav_density)
        clicks, selections, checked = [], [], []
        tree.numberClicked.connect(clicks.append)
        tree.pageActivated.connect(selections.append)
        tree.readToggled.connect(lambda *args:checked.append(args))
        QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
        assert clicks == [pid]
        assert selections == []
        assert checked == []
        assert 'Book One' in item.toolTip(0) or '2025' in item.toolTip(0)
    finally:
        tree.close()


def test_individual_number_click_is_separate_from_page_selection(app):
    from yomunote.window import DropPageList
    pid = uuid4().hex
    page = {'id':pid,'title':'Lecture','source_page':21,'source':'originals/lecture.pdf'}
    rows=build_display_rows(empty_research(),[page_node(pid)],[page])
    view=DropPageList()
    try:
        view.resize(250,260)
        item=QListWidgetItem(page['title'])
        item.setData(Qt.ItemDataRole.UserRole,pid)
        # Match the real ProjectPane, which assigns a tall thumbnail row.
        # Without this, the badge may fall *outside* Qt's hit-tested item.
        item.setSizeHint(QSize(155, view.ROW_HEIGHT))
        view.addItem(item)
        view.set_research_display(rows)
        view.show()
        app.processEvents()
        rect=view.number_rect(view.visualItemRect(item))
        assert view.itemAt(rect.center()) is item, 'Number badge must be inside page row'
        assert view._number_hit(rect.center()) == pid
        got=[]
        view.numberClicked.connect(got.append)
        previous_selection = view.currentItem()
        QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,pos=rect.center())
        assert got==[pid]
        assert view.currentItem() is previous_selection, 'Clicking the badge must not change the selected page'
        assert 'Tree order' in item.toolTip()
    finally:
        view.close()
