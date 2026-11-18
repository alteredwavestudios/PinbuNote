"""Small optional research editor for navigator context menus.

All citation logic lives in research.py, not Qt. Nothing contacts a network.
"""
from __future__ import annotations

from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget, QMessageBox)
from .research import SOURCE_TYPES, render_reference, render_in_text, to_html, missing_required

TYPE_LABELS = {
    'book':'Book / e-book', 'chapter':'Chapter in edited book',
    'journal':'Journal article', 'website':'Website / webpage',
    'film':'Film', 'television':'Television programme',
    'video':'Online video',
}
FIELD_LABELS = {
    'title':'Title', 'year':'Publication year',
    'organisation':'Organisation / corporate author',
    'authors':'Authors (Surname, Initials; separate multiple with ;) ',
    'editors':'Editors (Surname, Initials; separate with ;)',
    'container_title':'Book / journal / series title',
    'publisher':'Publisher / production company',
    'edition':'Edition (e.g. 2nd edn.)',
    'volume':'Journal volume', 'issue':'Journal issue',
    'pages':'Chapter / article page range (e.g. 40–67)',
    'url':'Website URL', 'doi':'DOI', 'accessed':'Accessed date (e.g. 17 November 2026)',
    'director':'Director (e.g. S. Spielberg)',
    'medium':'Medium / format (e.g. DVD)',
    'platform':'Streaming service / platform',
}
FIELDS = ('title','year','authors','organisation','editors','container_title','publisher',
          'edition','volume','issue','pages','url','doi','accessed','director','medium','platform')
VISIBLE = {
    'book':('title','year','authors','organisation','editors','publisher','edition','url','doi','accessed'),
    'chapter':('title','year','authors','editors','container_title','publisher','pages','url','doi','accessed'),
    'journal':('title','year','authors','container_title','volume','issue','pages','url','doi','accessed'),
    'website':('title','year','authors','organisation','publisher','url','accessed'),
    'film':('title','year','director','publisher','medium','platform','url','accessed'),
    'television':('title','year','publisher','platform','url','accessed'),
    'video':('title','year','authors','organisation','platform','url','accessed'),
}


class ReferenceEditor(QDialog):
    """Manual metadata input + instantaneous rich-text citation preview."""
    def __init__(self, record=None, parent=None, *, existing_references=None):
        super().__init__(parent)
        self.setWindowTitle('Reference · Cite Them Right Harvard')
        self.resize(640, 650)
        layout=QVBoxLayout(self)
        self.type_box=QComboBox()
        for key in SOURCE_TYPES:
            self.type_box.addItem(TYPE_LABELS[key], key)
        layout.addWidget(QLabel('Source type'))
        layout.addWidget(self.type_box)
        self.parent_label = QLabel('Parent edited book (optional, for chapters)')
        layout.addWidget(self.parent_label)
        self.parent_box = QComboBox()
        self.parent_box.addItem('No linked parent book', '')
        self._books = dict(existing_references or {})
        for identifier, book in self._books.items():
            if book.get('type') == 'book':
                self.parent_box.addItem(book['title'], identifier)
        layout.addWidget(self.parent_box)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        fields_widget=QWidget()
        self.form=QFormLayout(fields_widget)
        self.inputs={}
        self.rows={}
        for key in FIELDS:
            field=QLineEdit()
            field.setPlaceholderText('Optional unless indicated below')
            self.inputs[key]=field
            lbl=QLabel(FIELD_LABELS[key])
            self.form.addRow(lbl,field)
            self.rows[key]=(lbl,field)
            field.textChanged.connect(self._update_preview)
        scroll.setWidget(fields_widget)
        layout.addWidget(scroll,1)
        layout.addWidget(QLabel('Formatted bibliography preview'))
        self.preview=QLabel()
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.TextFormat.RichText)
        self.preview.setMinimumHeight(65)
        self.preview.setStyleSheet('padding: 9px; border: 1px solid palette(mid); border-radius: 7px;')
        layout.addWidget(self.preview)
        self.warning=QLabel()
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        self.buttons=QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        record=record or {}
        self.type_box.setCurrentIndex(max(0,list(SOURCE_TYPES).index(record.get('type','book'))
            if record.get('type') in SOURCE_TYPES else 0))
        for key in FIELDS:
            value=record.get(key,'')
            self.inputs[key].setText('; '.join(value) if isinstance(value,list) else str(value))
        parent_id = record.get('parent_id', '')
        for index in range(self.parent_box.count()):
            if self.parent_box.itemData(index) == parent_id:
                self.parent_box.setCurrentIndex(index)
                break
        self.parent_box.currentIndexChanged.connect(self._update_preview)
        self.type_box.currentIndexChanged.connect(self._update_fields)
        self._update_fields()

    def record(self):
        kind=self.type_box.currentData()
        result={'type':kind}
        for key in VISIBLE[kind]:
            text=self.inputs[key].text().strip()
            if text:
                result[key]=[p.strip() for p in text.split(';') if p.strip()] if key in ('authors','editors') else text
        if kind == 'chapter' and self.parent_box.currentData():
            result['parent_id'] = self.parent_box.currentData()
        return result

    def _update_fields(self, *_):
        kind=self.type_box.currentData()
        visible=set(VISIBLE[kind])
        self.parent_box.setVisible(kind == 'chapter')
        self.parent_label.setVisible(kind == 'chapter')
        for key,(lbl,field) in self.rows.items():
            lbl.setVisible(key in visible)
            field.setVisible(key in visible)
        self._update_preview()

    def _update_preview(self,*_):
        record=self.record()
        if not record.get('title'):
            self.preview.setText('<i>Enter a title to see the formatted reference.</i>')
            self.warning.setText('')
            return
        # Preview uses escaped, formatted HTML — never trust imported text.
        from .research import to_html
        parent = self._books.get(record.get('parent_id'))
        self.preview.setText(to_html(render_reference(record, parent=parent)))
        missing=missing_required(record, parent=parent)
        self.warning.setText('Missing details: '+', '.join(missing) if missing else 'Required core fields are present.')

    def _accept(self):
        record=self.record()
        if not record.get('title'):
            QMessageBox.warning(self,'Reference incomplete','Please enter a title first.')
            return
        self.accept()
