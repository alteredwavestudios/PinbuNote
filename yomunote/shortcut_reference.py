"""Read-only, searchable keyboard shortcuts reference for the Help menu.

IMPORTANT for future maintainers:
* Menu shortcuts are discovered directly from QAction objects. This avoids a
  second, inaccurate hard-coded copy when a menu key binding changes.
* The notes-only entries use the existing platform_shortcuts.docs_shortcut
  definitions, which NotesEditor also uses in tooltips and buttons.
* This window does not register any new QShortcut or edit a notebook. It is
  safe to open during a save or while the notes editor has keyboard focus.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
                               QLabel, QTreeWidget, QTreeWidgetItem,
                               QDialogButtonBox, QHeaderView)
from .platform_shortcuts import docs_shortcut, shortcut_label, IS_MAC


# Only list note-editing commands that the current editor actually handles.
# These are not QActions in the main menu, because the note editor installs
# them only while its own QTextEdit has focus.
NOTES_SHORTCUTS = (
    ('Bold', 'bold'), ('Italic', 'italic'), ('Underline', 'underline'),
    ('Strikethrough', 'strike'), ('Align left', 'left'),
    ('Centre text', 'centre'), ('Align right', 'right'),
    ('Justify', 'justify'), ('Numbered list', 'numbered'),
    ('Bulleted list', 'bulleted'), ('Indent', 'indent'),
    ('Outdent', 'outdent'), ('Link to selected page', 'page_link'),
    ('Insert website link', 'web_link'), ('Insert table', 'insert_table'),
    ('Find next match', 'find_next'),
    ('Find previous match', 'find_previous'),
    ('Increase notes zoom', 'notes_zoom_in'),
    ('Decrease notes zoom', 'notes_zoom_out'),
    ('Reset notes zoom', 'notes_zoom_reset'),
    ('Add table row above', 'table_row_before'),
    ('Add table row below', 'table_row_after'),
    ('Add table column before', 'table_column_before'),
    ('Add table column after', 'table_column_after'),
    ('Delete table row', 'table_delete_row'),
    ('Delete table column', 'table_delete_column'),
)

# These editor-local shortcuts are installed in NotesEditor.setup_shortcuts,
# rather than platform_shortcuts. Keep their sources together here and verify
# the actual binding by reading the setup_shortcuts map during maintenance.
MORE_NOTES_SHORTCUTS = (
    ('Paste plain text', 'Ctrl+Shift+V'),
    ('Clear text formatting', 'Ctrl+\\'),
    ('Normal paragraph', 'Ctrl+Alt+0'),
    ('Heading 1', 'Ctrl+Alt+1'),
    ('Heading 2', 'Ctrl+Alt+2'),
    ('Heading 3', 'Ctrl+Alt+3'),
    ('Heading 4', 'Ctrl+Alt+4'),
    ('Heading 5', 'Ctrl+Alt+5'),
    ('Heading 6', 'Ctrl+Alt+6'),
)


def _clean_action_name(label):
    # Visual labels may include key hints. The shortcut is displayed in its
    # own column; don't show those hint suffixes a second time.
    return str(label).replace('&', '').split('  ·  ')[0].strip()


def menu_shortcut_rows(window):
    """Return (menu name, action label, native shortcut) for live QActions."""
    rows = []
    for top in window.menuBar().actions():
        menu = top.menu()
        if menu is None:
            continue
        group = _clean_action_name(top.text())
        for action in menu.actions():
            if action.isSeparator() or action.menu() is not None:
                continue
            # QAction.shortcuts() includes the alternative Ctrl+Y redo key.
            keys = [key.toString(QKeySequence.SequenceFormat.NativeText)
                    for key in action.shortcuts() if not key.isEmpty()]
            if keys:
                rows.append((group, _clean_action_name(action.text()),
                             ' / '.join(keys)))
    return rows


def editor_shortcut_rows():
    rows = [('Notes editor', label, docs_shortcut(key))
            for label, key in NOTES_SHORTCUTS]
    rows.extend(('Notes editor', label, shortcut_label(key))
                for label, key in MORE_NOTES_SHORTCUTS)
    rows.extend([
        ('Page navigation', 'Previous page', shortcut_label('Ctrl+Alt+Up')),
        ('Page navigation', 'Next page', shortcut_label('Ctrl+Alt+Down')),
        ('Page navigation', 'Cycle page-number display', shortcut_label('Alt+N')),
    ])
    return rows


class KeyboardShortcutsDialog(QDialog):
    """Show the current keys in a small, keyboard-accessible searchable tree."""
    def __init__(self, window):
        super().__init__(window)
        self.setWindowTitle('Keyboard Shortcuts · Pinbu Note')
        self.setMinimumSize(630, 430)
        self.resize(760, 590)
        outer = QVBoxLayout(self)
        description = QLabel(
            'Search the commands below. Notes-editor shortcuts work while '
            'typing in notes; page-navigation keys also work while editing.')
        description.setWordWrap(True)
        outer.addWidget(description)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText('Search commands, menus or keys…')
        self.search.setClearButtonEnabled(True)
        outer.addWidget(self.search)
        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(['Command', 'Shortcut'])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setUniformRowHeights(True)
        outer.addWidget(self.tree, 1)
        grouped = {}
        for category, command, key in menu_shortcut_rows(window) + editor_shortcut_rows():
            if category not in grouped:
                parent = QTreeWidgetItem([category, ''])
                parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.tree.addTopLevelItem(parent)
                grouped[category] = parent
            QTreeWidgetItem(grouped[category], [command, key])
        self.tree.expandAll()
        self.search.textChanged.connect(self._filter)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.search.setFocus()

    def _filter(self, text):
        query = text.casefold().strip()
        for index in range(self.tree.topLevelItemCount()):
            category = self.tree.topLevelItem(index)
            category_match = query in category.text(0).casefold()
            any_visible = False
            for child_index in range(category.childCount()):
                child = category.child(child_index)
                matches = (not query or category_match or
                           query in child.text(0).casefold() or
                           query in child.text(1).casefold())
                child.setHidden(not matches)
                any_visible |= matches
            category.setHidden(not any_visible)
            if query:
                category.setExpanded(True)
