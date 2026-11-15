"""v0.8.4c: phase-two Tab Exchange worker + cache memory safeguards."""
from __future__ import annotations

import ast
import threading
from pathlib import Path

import pytest

from yomunote.notebook import Notebook
from yomunote.importers import trim_disposable_caches
from yomunote.tab_exchange import stage_import, commit_import


def make_shared(tmp_path):
    source = Notebook.create(tmp_path, 'Sharing Source')
    p = source.project(source.active_id)
    p.notes_html = '<h1>Imported notes preserved</h1>'
    p.asset_path('originals/image.png').write_bytes(b'example-image' * 20000)
    p.pages.append({'id': 'shared', 'kind': 'image',
                    'source': 'originals/image.png', 'render_source': 'originals/image.png'})
    p.save()
    source.save()
    destination = Notebook.create(tmp_path, 'Receiving Notebook')
    stage, entries = stage_import(source.path, [source.active_id],
                                  destination.workspace, ('My Notes',))
    return source, destination, stage, entries


def test_final_tab_commit_on_worker_thread_is_reopenable(tmp_path):
    src, dest, stage, entries = make_shared(tmp_path)
    saved = dest.path
    try:
        outcomes = []
        thread = threading.Thread(target=lambda: outcomes.append(commit_import(dest, stage, entries)))
        thread.start()
        thread.join(timeout=12)
        assert not thread.is_alive()
        assert len(outcomes) == 1
        assert len(dest.tabs) == 2
        assert len(outcomes[0]) == 1
        assert dest.project(outcomes[0][0]['id']).notes_html == '<h1>Imported notes preserved</h1>'
    finally:
        src.close()
        dest.close()
    reread = Notebook.load(saved)
    try:
        assert len(reread.tabs) == 2
        p = reread.project(reread.active_id)
        assert p.asset_path('originals/image.png').read_bytes() == b'example-image' * 20000
    finally:
        reread.close()


def test_final_tab_worker_rolls_back_after_injected_save_failure(tmp_path, monkeypatch):
    src, dest, stage, entries = make_shared(tmp_path)
    initial_tabs = list(dest.tabs)
    try:
        def fail_sqlite():
            raise OSError('simulated disk failure during imported-tab commit')
        monkeypatch.setattr(dest, '_save_synchronous', fail_sqlite)
        errors = []
        def run():
            try:
                commit_import(dest, stage, entries)
            except Exception as exc:
                errors.append(str(exc))
        thread = threading.Thread(target=run)
        thread.start()
        thread.join(timeout=12)
        assert not thread.is_alive()
        assert errors and 'simulated disk failure' in errors[0]
        assert dest.tabs == initial_tabs
        assert all(not (dest.workspace / 'tabs' / item['id']).exists() for item in entries)
    finally:
        src.close()
        dest.close()


def test_trim_old_jpegs_preserves_originals_and_selected_page(tmp_path, monkeypatch):
    import yomunote.importers as imports
    from yomunote.project import Project
    p = Project.create(tmp_path, 'Cache')
    try:
        p.selected_page = 'selected'
        originals = p.asset_path('originals/document.pdf')
        originals.write_bytes(b'%PDF important unchanged')
        folder = p.path / 'cache' / 'previews'
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(9):
            (folder / f'{index:02d}.jpg').write_bytes(b'x' * 100)
        (folder / 'selected.jpg').write_bytes(b'x' * 100)
        monkeypatch.setattr(imports, 'PREVIEW_DISK_BUDGET', 240)
        trimmed = trim_disposable_caches(p)
        assert trimmed['previews'] == 8
        assert (folder / 'selected.jpg').exists()
        assert originals.read_bytes() == b'%PDF important unchanged'
    finally:
        pass


def test_deactivated_group_thumbnails_are_released_and_commits_worker_only():
    src = (Path(__file__).parents[1] / 'yomunote' / 'window.py').read_text()
    tree = ast.parse(src)
    main = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
    pane = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ProjectPane')
    method = lambda cls, name: ast.get_source_segment(src, next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name))
    deactivate = method(pane, 'deactivate')
    assert 'self.group_tree.discard_other_thumbnails(set())' in deactivate
    activate = method(pane, 'activate')
    assert 'trim_disposable_caches' in activate
    exchange = method(main, 'import_notebook_tabs')
    assert 'def commit_worker():' in exchange
    assert 'return commit_import(destination_nb, stage, entries)' in exchange
    assert 'start_task(self, commit_worker,' in exchange
    assert "self._exchange_progress.setCancelButtonText('')" in exchange
    end_exchange = method(main, '_end_exchange')
    assert 'self._exchange_deferred_panes' in end_exchange


def test_large_json_snapshot_has_bounded_fallback(tmp_path, monkeypatch):
    import yomunote.notebook as nb_module
    from yomunote.snapshot_save import SnapshotTooLarge
    nb = Notebook.create(tmp_path, 'Cap test')
    try:
        monkeypatch.setattr(nb_module, 'MAX_SNAPSHOT_JSON_BYTES', 1)
        with pytest.raises(SnapshotTooLarge):
            nb.capture_save_snapshot()
        assert nb.save() is False
    finally:
        nb.close()
