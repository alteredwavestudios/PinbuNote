"""v0.8.6b: safe notebook sessions and movable paper/bookmark data."""
from __future__ import annotations

import copy
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from yomunote.notebook import Notebook
from yomunote.notebook_lock import (NotebookInUseError,
    NotebookExternallyModifiedError, NotebookLease)
from yomunote.importers import blank_page
from yomunote.project import Project
from yomunote.snapshot_save import write_snapshot
from yomunote.vector_marks import (make_sticky, valid_sticky, valid_vector,
                                    vector_bounds, translated_vector, resized_vector)

ROOT = Path(__file__).resolve().parents[1]


def test_sticky_validated_movable_and_resizable():
    note = make_sticky('Remember this!\nAnd that!', rect=(.1, .2, .35, .25),
                       color='#CCEE99', font='Nunito', font_size=19,
                       bold=True, italic=True)
    assert valid_vector(note) and valid_sticky(note)
    assert vector_bounds(note) == pytest.approx((.1, .2, .45, .45))
    dragged = translated_vector(note, .2, .1)
    assert dragged['text'] == note['text']
    assert dragged['x'] == pytest.approx(.3)
    assert valid_sticky(dragged)
    resized = resized_vector(note, 'br', .7, .6)
    assert valid_sticky(resized)
    assert resized['w'] > note['w']
    assert resized['h'] > note['h']
    assert resized['font_size'] == 19
    for corrupt in (dict(note, font_size=1000), dict(note, text='x'*8001),
                    dict(note, bold=1), dict(note, color='red'),
                    dict(note, x=.9), dict(note, w=.0001)):
        assert not valid_sticky(corrupt)


def test_sticky_and_bookmark_survive_save_and_reopen(tmp_path):
    nb = Notebook.create(tmp_path, 'Paper')
    path = nb.path
    try:
        project = nb.project(nb.active_id)
        page = blank_page(project, 'Course reading')
        page['bookmark'] = 'Key argument'
        project.pages.append(page)
        project.annotations[page['id']] = [make_sticky(
            'p. 3: the core thesis', color='#FFC8D9', font='DejaVu Sans',
            font_size=23, italic=True)]
        project.save()
        nb.save()
    finally:
        nb.close()
    restored = Notebook.load(path)
    try:
        project = restored.project(restored.active_id)
        assert project.pages[0]['bookmark'] == 'Key argument'
        assert project.annotations[project.pages[0]['id']][0]['text'] == 'p. 3: the core thesis'
        assert project.annotations[project.pages[0]['id']][0]['italic'] is True
    finally:
        restored.close()


def test_sticky_and_bookmark_survive_cross_tab_move(tmp_path):
    nb = Notebook.create(tmp_path, 'Move notes')
    try:
        source = nb.active_id
        destination = nb.add_tab('To do')
        project = nb.project(source)
        page = blank_page(project, 'Annotated page')
        page['bookmark'] = 'Exam revision'
        project.pages.append(page)
        mark = make_sticky('Important', font_size=21, bold=True)
        project.annotations[page['id']] = [mark]
        project.save()
        nb.save()
        assert nb.transfer_pages(source, destination, [page['id']], move=True) == 1
        target = nb.project(destination)
        assert target.pages[0]['bookmark'] == 'Exam revision'
        assert target.annotations[target.pages[0]['id']] == [mark]
    finally:
        nb.close()


def test_invalid_bookmark_must_not_be_saved(tmp_path):
    p = Project.create(tmp_path, 'Bookmarks')
    item = blank_page(p)
    item['bookmark'] = 'too long '*30
    p.pages.append(item)
    with pytest.raises(ValueError, match='bookmark'):
        p.save()


def test_same_notebook_cannot_open_twice_and_unlocks_on_close(tmp_path):
    notebook = Notebook.create(tmp_path, 'Lock me')
    path = notebook.path
    try:
        with pytest.raises(NotebookInUseError, match='already open'):
            Notebook.load(path)
        assert path.with_name(path.name + '.lock').exists()
    finally:
        notebook.close()
    later = Notebook.load(path)
    later.close()


def test_other_notebook_does_not_share_lock(tmp_path):
    a = Notebook.create(tmp_path, 'A')
    b = Notebook.create(tmp_path, 'B')
    try:
        assert a.path != b.path
    finally:
        b.close()
        a.close()


def test_lock_is_cross_process_and_not_a_stale_marker(tmp_path):
    nb = Notebook.create(tmp_path, 'Other process')
    path = nb.path
    source = """import sys
from yomunote.notebook import Notebook
from yomunote.notebook_lock import NotebookInUseError
try:
    n = Notebook.load(sys.argv[1])
except NotebookInUseError:
    sys.exit(0)
else:
    n.close()
    sys.exit(10)
"""
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
    try:
        process = subprocess.run([sys.executable, '-c', source, str(path)],
                                 env=env, capture_output=True, text=True,
                                 timeout=20)
        assert process.returncode == 0, process.stderr
    finally:
        nb.close()
    process = subprocess.run([sys.executable, '-c', source, str(path)],
                             env=env, capture_output=True, text=True, timeout=20)
    assert process.returncode == 10, process.stderr


def test_windows_held_lock_reports_in_use_without_unlocking_others(tmp_path, monkeypatch):
    """Windows uses mandatory byte locks; a failed acquire must NOT unlock."""
    from types import SimpleNamespace
    from yomunote import notebook_lock
    path = tmp_path / 'existing.yomunote'
    lockfile = path.with_name(path.name + '.lock')
    lockfile.write_bytes(b'\0')
    attempts = []

    def locking(fd, mode, length):
        attempts.append(mode)
        if mode == 1:  # acquire, mocked below as LK_NBLCK
            raise PermissionError('the lock is owned by another process')
        raise AssertionError('Must never unlock a lock this process did not acquire')

    fake_msvcrt = SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=locking)
    with monkeypatch.context() as m:
        m.setattr(notebook_lock.sys, 'platform', 'win32')
        m.setitem(sys.modules, 'msvcrt', fake_msvcrt)
        with pytest.raises(NotebookInUseError, match='another Pinbu Note window'):
            NotebookLease(path).acquire()
    assert attempts == [1]
    assert not notebook_lock._active_paths


def test_external_edit_blocks_sync_and_async_save(tmp_path):
    nb = Notebook.create(tmp_path, 'Edited elsewhere')
    try:
        snap = nb.capture_save_snapshot()
        # Simulate older Yomu Note or Dropbox changing the file externally.
        with sqlite3.connect(nb.path) as con:
            con.execute('CREATE TABLE external_revision (token INTEGER)')
        with pytest.raises(NotebookExternallyModifiedError, match='modified on disk'):
            nb.save()
        with pytest.raises(NotebookExternallyModifiedError, match='changed on disk'):
            write_snapshot(snap)
        assert nb._save_guard.generation == 1
    finally:
        nb.close()


def test_gui_contract_has_sticky_editor_and_bookmark_navigation():
    source = (ROOT / 'yomunote/window.py').read_text(encoding='utf-8')
    assert 'class StickyAnnotationItem(QGraphicsPathItem)' in source
    assert 'def edit_sticky_note(self, mark_id=None)' in source
    assert 'self.canvas.stickyDoubleClicked.connect(self.edit_sticky_note)' in source
    assert "self._add_vector(mark, 'Add Sticky Note', auto_select=True)" in source
    assert 'def _populate_bookmark_menu(self):' in source
    assert 'def select_page_id(self, page_id: str):' in source
    assert 'def _bookmark_page_menu(self, menu, page_id):' in source
    assert 'QShortcut(QKeySequence(QKeySequence.StandardKey.Paste), widget)' in source
