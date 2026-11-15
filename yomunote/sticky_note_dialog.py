"""A small, themed sticky-note composer; notes remain plain text, never HTML.

Avoid injecting remote fonts or arbitrary rich text into notebooks. Saved marks
contain only validated text and uniform font/style metadata.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
    QDialogButtonBox, QFontComboBox, QFormLayout, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout)
from .vector_marks import make_sticky, valid_sticky
from .sticky_bullets import plan_bullet_toggle


COLOURS = (
    ('Butter', '#FFE88E'), ('Rose', '#FFC8D9'),
    ('Mint', '#C5F2D4'), ('Lilac', '#DCCBFF'),
    ('Sky', '#C7E5FF'), ('Paper', '#FFF8E9'),
)


class StickyNoteDialog(QDialog):
    def __init__(self, mark=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Edit Sticky Note' if mark else 'New Sticky Note')
        self.setMinimumWidth(390)
        self._mark = dict(mark) if mark else make_sticky()
        self._colour = self._mark['color']
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        tip = QLabel('A note to place on your page ♡  Click where it should go after saving. Double-click to edit.')
        tip.setWordWrap(True)
        layout.addWidget(tip)
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(self._mark['text'])
        self.editor.setPlaceholderText('Write your note here…')
        self.editor.setMinimumHeight(155)
        layout.addWidget(self.editor)
        editor_tools = QHBoxLayout()
        bullet_button = QPushButton('• Bullet list')
        bullet_button.setToolTip('Toggle bullets on selected lines, or the current line')
        bullet_button.clicked.connect(self._toggle_bullets)
        editor_tools.addWidget(bullet_button)
        editor_tools.addStretch(1)
        layout.addLayout(editor_tools)
        form = QFormLayout()
        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(self._mark['font']))
        form.addRow('Font', self.font)
        self.size = QSpinBox()
        self.size.setRange(6, 72)
        self.size.setValue(round(self._mark['font_size']))
        form.addRow('Size (pt)', self.size)
        self.alignment = QComboBox()
        for label, value in (('Left', 'left'), ('Centre', 'center'), ('Right', 'right')):
            self.alignment.addItem(label, value)
        self.alignment.setCurrentIndex(max(0, self.alignment.findData(self._mark.get('alignment','left'))))
        form.addRow('Text alignment', self.alignment)
        self.letter_spacing = QSpinBox()
        self.letter_spacing.setRange(80, 150)
        self.letter_spacing.setSuffix('%')
        self.letter_spacing.setValue(round(self._mark.get('letter_spacing_pct', 100)))
        self.letter_spacing.setToolTip('100% is normal; spacing scales with the chosen font size')
        form.addRow('Character spacing', self.letter_spacing)
        self.show_background = QCheckBox('Show paper background and folded corner')
        self.show_background.setChecked(self._mark.get('show_background', True))
        form.addRow('Background', self.show_background)
        styles = QHBoxLayout()
        self.bold = QCheckBox('Bold')
        self.bold.setChecked(self._mark['bold'])
        self.italic = QCheckBox('Italic')
        self.italic.setChecked(self._mark['italic'])
        styles.addWidget(self.bold)
        styles.addWidget(self.italic)
        styles.addStretch(1)
        form.addRow('Style', styles)
        layout.addLayout(form)
        colours = QHBoxLayout()
        colours.addWidget(QLabel('Paper colour'))
        self.colour_combo = QComboBox()
        for label, colour in COLOURS:
            self.colour_combo.addItem(label, colour)
        current = self.colour_combo.findData(self._colour)
        if current >= 0:
            self.colour_combo.setCurrentIndex(current)
        else:
            self.colour_combo.addItem('Custom', self._colour)
            self.colour_combo.setCurrentIndex(self.colour_combo.count() - 1)
        self.colour_combo.currentIndexChanged.connect(self._choose_preset)
        colours.addWidget(self.colour_combo, 1)
        custom = QPushButton('Custom…')
        custom.clicked.connect(self._choose_custom)
        colours.addWidget(custom)
        layout.addLayout(colours)
        self.font.currentFontChanged.connect(lambda *_: self._refresh_preview())
        self.size.valueChanged.connect(lambda *_: self._refresh_preview())
        self.bold.toggled.connect(lambda *_: self._refresh_preview())
        self.italic.toggled.connect(lambda *_: self._refresh_preview())
        self.alignment.currentIndexChanged.connect(lambda *_: self._refresh_preview())
        self.letter_spacing.valueChanged.connect(lambda *_: self._refresh_preview())
        self.show_background.toggled.connect(lambda *_: self._refresh_preview())
        self._refresh_preview()
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _toggle_bullets(self):
        """One Undo step, preserve selections, never duplicate bullets on mixed lines."""
        cursor = self.editor.textCursor()
        first, last = cursor.selectionStart(), cursor.selectionEnd()
        edits = plan_bullet_toggle(self.editor.toPlainText(), first, last)
        if not edits:
            return
        # Changes occur from the end backwards, so all source offsets remain
        # valid; only one QTextDocument undo command is produced.
        work = self.editor.textCursor()
        work.beginEditBlock()
        for change in reversed(edits):
            work.setPosition(change.start)
            work.setPosition(change.end, work.MoveMode.KeepAnchor)
            work.insertText(change.replacement)
        work.endEditBlock()
        def mapped(position):
            # Only ORIGINAL offsets are compared. Never compare the shifted
            # caret with later source edits or it can jump across lines.
            shift = sum(len(change.replacement) - (change.end-change.start)
                        for change in edits if position >= change.end)
            return max(0, min(position + shift,
                              self.editor.document().characterCount()-1))
        restored = self.editor.textCursor()
        restored.setPosition(mapped(first))
        if last != first:
            restored.setPosition(mapped(last), restored.MoveMode.KeepAnchor)
        self.editor.setTextCursor(restored)
        self.editor.setFocus()

    def _choose_preset(self, *_):
        self._colour = self.colour_combo.currentData() or '#FFE88E'
        self._refresh_preview()

    def _choose_custom(self):
        chosen = QColorDialog.getColor(QColor(self._colour), self, 'Sticky paper colour')
        if chosen.isValid():
            self._colour = chosen.name()
            pos = self.colour_combo.findData(self._colour)
            if pos < 0:
                self.colour_combo.addItem('Custom', self._colour)
                pos = self.colour_combo.count() - 1
            self.colour_combo.setCurrentIndex(pos)
            self._refresh_preview()

    def _refresh_preview(self):
        colour = QColor(self._colour)
        ink = '#25302c' if colour.lightness() >= 125 else '#ffffff'
        font = self.font.currentFont()
        font.setPointSize(self.size.value())
        font.setBold(self.bold.isChecked())
        font.setItalic(self.italic.isChecked())
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing,
                              self.letter_spacing.value())
        self.editor.setFont(font)
        self.editor.setStyleSheet(
            f'QPlainTextEdit {{background: {self._colour if self.show_background.isChecked() else "transparent"};'
            f'color:{ink}; border:1px solid rgba(100,80,50,65);'
            f'border-radius:2px;padding:12px;}}')
        from PySide6.QtGui import QTextOption
        self.editor.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        alignment = {'left': Qt.AlignmentFlag.AlignLeft,
                     'center': Qt.AlignmentFlag.AlignHCenter,
                     'right': Qt.AlignmentFlag.AlignRight}[self.alignment.currentData()]
        # Plain-text notes have one uniform alignment. Set the document's
        # default layout option rather than merging block formats over the
        # ENTIRE document on every font/colour/spacing preview. The old code
        # generated needless undo entries and large relayouts while typing.
        option = self.editor.document().defaultTextOption()
        if option.alignment() != alignment:
            option.setAlignment(alignment)
            self.editor.document().setDefaultTextOption(option)

    def value(self):
        mark = dict(self._mark)
        mark.update(text=self.editor.toPlainText(), color=self._colour,
                    font=self.font.currentFont().family(), font_size=self.size.value(),
                    bold=self.bold.isChecked(), italic=self.italic.isChecked(),
                    alignment=self.alignment.currentData(),
                    show_background=self.show_background.isChecked(),
                    letter_spacing_pct=self.letter_spacing.value())
        return mark

    def _accept(self):
        if not valid_sticky(self.value()):
            QMessageBox.warning(self, 'Sticky note too large',
                'Keep the note under 8,000 characters and use a valid font and colour.')
            return
        self.accept()
