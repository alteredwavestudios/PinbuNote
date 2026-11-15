"""v0.8.4c: immutable metadata, independent SQLite worker, failure safety."""
from __future__ import annotations

import sqlite3
import threading

import pytest

from yomunote.notebook import Notebook
from yomunote.snapshot_save import write_snapshot


def _notes(nb):
    return nb.project(nb.active_id).notes_html


def _change_notes(nb, text):
    p = nb.project(nb.active_id)
    p.notes_html = text
    p.save()
    return p


def _run_in_thread(snapshot):
    results = []
    t = threading.Thread(target=lambda: results.append(write_snapshot(snapshot)))
    t.start()
    t.join(timeout=15)
    assert not t.is_alive()
    return results[0]


def test_background_worker_roundtrip_and_no_raster_caches(tmp_path):
    nb = Notebook.create(tmp_path, 'Snapshots')
    path = nb.path
    try:
        p = _change_notes(nb, '<h2>Snapshot test</h2>')
        p.asset_path('originals/page.jpg').write_bytes(b'P' * 2200000)
        p.pages.append({'id': 'one', 'kind': 'image', 'source': 'originals/page.jpg',
                        'render_source': 'originals/page.jpg'})
        p.save()
        (p.path / 'cache' / 'thumbs' / 'irrelevant.jpg').write_bytes(b'cache')
        snapshot = nb.capture_save_snapshot()
        result = _run_in_thread(snapshot)
        assert result.applied and result.changed
        assert nb.accept_background_save(result)
        with sqlite3.connect(path) as conn:
            paths = [row[0] for row in conn.execute('SELECT path FROM files')]
            assert any('originals/page.jpg' in p for p in paths)
            assert not any('cache/' in p for p in paths)
    finally:
        nb.close()
    loaded = Notebook.load(path)
    try:
        assert _notes(loaded) == '<h2>Snapshot test</h2>'
        assert loaded.project(loaded.active_id).asset_path('originals/page.jpg').stat().st_size == 2200000
    finally:
        loaded.close()


def test_frozen_metadata_not_read_from_mutable_workspace(tmp_path):
    nb = Notebook.create(tmp_path, 'Freeze')
    try:
        _change_notes(nb, 'FIRST')
        first = nb.capture_save_snapshot()
        _change_notes(nb, 'SECOND')
        # The worker must save exactly what was visible at capture time.
        result = write_snapshot(first)
        assert nb.accept_background_save(result)
        with sqlite3.connect(nb.path) as conn:
            rel = f'tabs/{nb.active_id}/project.json'
            first_json = conn.execute('SELECT data FROM files WHERE path=?', (rel,)).fetchone()[0]
        assert b'FIRST' in first_json
        assert b'SECOND' not in first_json
        second = nb.capture_save_snapshot()
        result = write_snapshot(second)
        assert nb.accept_background_save(result)
        with sqlite3.connect(nb.path) as conn:
            final = conn.execute('SELECT data FROM files WHERE path=?', (rel,)).fetchone()[0]
        assert b'SECOND' in final
    finally:
        nb.close()


def test_stale_worker_can_never_overwrite_newer_sync_commit(tmp_path):
    nb = Notebook.create(tmp_path, 'No stale save')
    try:
        _change_notes(nb, 'OLD')
        old_snapshot = nb.capture_save_snapshot()
        _change_notes(nb, 'LATEST')
        assert nb.save()
        stale = write_snapshot(old_snapshot)
        assert not stale.applied
        assert not nb.accept_background_save(stale)
        with sqlite3.connect(nb.path) as conn:
            blob = conn.execute('SELECT data FROM files WHERE path=?',
                                (f'tabs/{nb.active_id}/project.json',)).fetchone()[0]
        assert b'LATEST' in blob
        assert b'OLD' not in blob
    finally:
        nb.close()


def test_missing_asset_rolls_back_working_database(tmp_path):
    nb = Notebook.create(tmp_path, 'Atomic worker')
    try:
        original = nb.path.read_bytes()
        p = nb.project(nb.active_id)
        p.asset_path('originals/x.jpg').write_bytes(b'original')
        p.pages.append({'id': 'x', 'kind': 'image', 'source': 'originals/x.jpg'})
        p.save()
        frozen = nb.capture_save_snapshot()
        p.asset_path('originals/x.jpg').unlink()
        with pytest.raises((FileNotFoundError, OSError)):
            write_snapshot(frozen)
        # The SQLite transaction should remain usable and without a partial page.
        with sqlite3.connect(nb.path) as conn:
            assert not conn.execute("SELECT 1 FROM files WHERE path LIKE '%/x.jpg'").fetchone()
    finally:
        nb.close()


def test_close_before_queued_job_is_harmless(tmp_path):
    nb = Notebook.create(tmp_path, 'Close')
    _change_notes(nb, 'not yet committed')
    snapshot = nb.capture_save_snapshot()
    nb.close()
    result = write_snapshot(snapshot)
    assert not result.applied


def test_synced_saved_manifest_cache_correctly_updated(tmp_path):
    nb = Notebook.create(tmp_path, 'Metadata')
    try:
        _change_notes(nb, 'Saved')
        result = write_snapshot(nb.capture_save_snapshot())
        assert nb.accept_background_save(result)
        assert nb.save() is False  # no unnecessary BLOB write on next save
        assert nb.backup_dirty
    finally:
        nb.close()


def test_source_contracts_for_gui_autosave():
    import ast
    from pathlib import Path
    window = (Path(__file__).parents[1] / 'yomunote' / 'window.py').read_text()
    tree = ast.parse(window)
    assert 'self._saving_from_autosave = True' in window
    assert 'self._queue_background_notebook_save((pane,))' in window
    assert 'self._background_save_pending_panes.update(panes)' in window
    assert 'self._save_panes_in_one_commit' in window
    assert 'start_task(self, worker, finished, priority=-1)' in window
