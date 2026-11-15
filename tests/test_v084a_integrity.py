"""v0.8.4a fault-injection coverage for atomic tab transfers and asset integrity."""
from __future__ import annotations

import copy
import sqlite3
from pathlib import Path

import pytest

from yomunote.notebook import Notebook
from yomunote.project import Project
from yomunote.page_groups import group_node, page_node
from yomunote.reading_view import empty_view


def setup_pages(tmp_path):
    nb = Notebook.create(tmp_path, 'Reliability Test')
    source_id = nb.active_id
    target_id = nb.add_tab('Target')
    source = nb.project(source_id)
    (source.path / 'originals').mkdir(exist_ok=True)
    source.asset_path('originals/deck.pdf').write_bytes(b'%PDF-1.4\n' + b'A' * 256)
    source.pages = [
        {'id': 'p1', 'kind': 'pdf', 'source_page': 1,
         'source': 'originals/deck.pdf', 'render_source': 'originals/deck.pdf'},
        {'id': 'p2', 'kind': 'pdf', 'source_page': 2,
         'source': 'originals/deck.pdf', 'render_source': 'originals/deck.pdf'},
    ]
    source.page_groups = [group_node('Reading', [page_node('p1'), page_node('p2')])]
    source.read_page_ids = ['p1']
    source.annotations = {'p1': []}
    source.notes_html = '<p>Important source notes</p>'
    source.reading_view = empty_view()
    source.reading_view['positions']['p1'] = {'x': .5, 'y': .3, 'bottom': False}
    source.save()
    target = nb.project(target_id)
    target.notes_html = '<p>Important destination notes</p>'
    target.save()
    nb.save()
    return nb, source_id, target_id


def snapshot(nb, source_id, target_id):
    return [
        (nb.workspace / 'tabs' / tid / 'project.json').read_bytes()
        for tid in (source_id, target_id)
    ]


def db_snapshot(nb):
    with sqlite3.connect(nb.path) as conn:
        return list(conn.execute('SELECT path,data FROM files ORDER BY path'))


def test_missing_original_blocks_save_and_preserves_committed_file(tmp_path):
    nb = Notebook.create(tmp_path, 'Absent PDF')
    try:
        project = nb.project(nb.active_id)
        project.pages.append({'id': 'broken', 'kind': 'pdf',
                              'source': 'originals/missing.pdf'})
        project.save()
        baseline = db_snapshot(nb)
        with pytest.raises(ValueError, match='missing or unsafe page asset'):
            nb.save()
        assert db_snapshot(nb) == baseline
    finally:
        nb.close()


def test_missing_converted_render_blocks_save(tmp_path):
    nb = Notebook.create(tmp_path, 'Missing Conversion')
    try:
        project = nb.project(nb.active_id)
        project.asset_path('originals/report.docx').write_bytes(b'not actually a DOCX')
        project.pages.append({'id': 'broken', 'kind': 'pdf',
                              'source': 'originals/report.docx',
                              'render_source': 'pages/rendered.pdf'})
        project.save()
        with pytest.raises(ValueError, match='pages/rendered.pdf'):
            nb.save()
    finally:
        nb.close()


def test_missing_asset_in_existing_sqlite_rejected_on_load(tmp_path):
    nb = Notebook.create(tmp_path, 'Old Broken Notebook')
    path = nb.path
    try:
        project = nb.project(nb.active_id)
        project.pages.append({'id': 'broken', 'kind': 'pdf',
                              'source': 'originals/missing.pdf'})
        project.save()
        # Simulate a notebook written by an older version whose live asset
        # references were not checked before saving.
        manifest = (project.path / 'project.json').read_bytes()
        relative = f"tabs/{nb.active_id}/project.json"
        with sqlite3.connect(path) as conn:
            conn.execute('UPDATE files SET data=?, size=? WHERE path=?',
                         (manifest, len(manifest), relative))
    finally:
        nb.close()
    with pytest.raises(ValueError, match='missing a page asset'):
        Notebook.load(path)


def test_blank_pages_and_reused_asset_save_successfully(tmp_path):
    nb = Notebook.create(tmp_path, 'Blank And Reused')
    try:
        project = nb.project(nb.active_id)
        project.asset_path('originals/shared.pdf').write_bytes(b'PDF')
        project.pages = [{'id': 'blank', 'kind': 'blank'}] + [
            {'id': f'p{i}', 'kind': 'pdf', 'source_page': i+1,
             'source': 'originals/shared.pdf'} for i in range(100)]
        project.save()
        assert nb.save()
        with sqlite3.connect(nb.path) as conn:
            result = conn.execute("SELECT count(*) FROM files WHERE path LIKE '%/originals/%'").fetchone()[0]
        assert result == 1
    finally:
        nb.close()


@pytest.mark.parametrize('failure_at', ['copy', 'destination_save', 'source_save', 'sqlite'])
def test_transfer_rolls_back_at_every_failure_stage(tmp_path, monkeypatch, failure_at):
    nb, source_id, target_id = setup_pages(tmp_path)
    try:
        old = snapshot(nb, source_id, target_id)
        db_before = db_snapshot(nb)
        target_dir = nb.project(target_id).path
        source_dir = nb.project(source_id).path
        if failure_at == 'copy':
            import yomunote.notebook as notebook_module
            def bad_copy(*args, **kwargs):
                raise OSError('injected copy failure')
            monkeypatch.setattr(notebook_module.shutil, 'copy2', bad_copy)
        elif failure_at in ('destination_save', 'source_save'):
            original_save = Project.save
            bad_dir = target_dir if failure_at == 'destination_save' else source_dir
            def fail_at_save(project, *args, **kwargs):
                if project.path == bad_dir:
                    raise OSError('injected manifest failure')
                return original_save(project, *args, **kwargs)
            monkeypatch.setattr(Project, 'save', fail_at_save)
        else:
            def failed_sql():
                raise OSError('injected sqlite failure')
            monkeypatch.setattr(nb, 'save', failed_sql)
        with pytest.raises(OSError, match='injected'):
            nb.transfer_pages(source_id, target_id, ['p1', 'p2'], move=True)
        assert snapshot(nb, source_id, target_id) == old
        assert db_snapshot(nb) == db_before
        assert not list((target_dir / 'originals').glob('*.pdf'))
        assert not list(target_dir.glob('.yomu-transfer-*'))
    finally:
        nb.close()


def test_transfer_transaction_commit_and_undo_redo_survive_reopen(tmp_path):
    nb, source_id, target_id = setup_pages(tmp_path)
    path = nb.path
    try:
        before = snapshot(nb, source_id, target_id)
        count, change = nb.transfer_pages(source_id, target_id, ['p1', 'p2'],
                                          move=True, return_change=True)
        assert count == 2
        assert change.estimated_bytes > 0
        assert len(change.created_assets) == 1
        assert nb.project(source_id).pages == []
        target = nb.project(target_id)
        assert len(target.pages) == 2
        assert target.pages[0]['source'] == target.pages[1]['source']
        assert target.read_page_ids == [target.pages[0]['id']]
        assert target.reading_view['positions'][target.pages[0]['id']]['x'] == .5
        assert target.notes_html == '<p>Important destination notes</p>'
        nb.replay_page_transfer(change, undo=True)
        assert nb.project(source_id).pages[0]['id'] == 'p1'
        assert nb.project(target_id).pages == []
        with sqlite3.connect(path) as conn:
            assert not conn.execute(
                'SELECT path FROM files WHERE path LIKE ?',
                (f'tabs/{target_id}/originals/%',)).fetchone()
        nb.replay_page_transfer(change, undo=False)
        assert nb.project(source_id).pages == []
        assert len(nb.project(target_id).pages) == 2
    finally:
        nb.close()
    reopened = Notebook.load(path)
    try:
        assert reopened.project(source_id).pages == []
        assert len(reopened.project(target_id).pages) == 2
    finally:
        reopened.close()


def test_transfer_undo_does_not_erase_unrelated_notes(tmp_path):
    nb, source_id, target_id = setup_pages(tmp_path)
    try:
        _, change = nb.transfer_pages(source_id, target_id, ['p1'],
                                      move=False, return_change=True)
        target = nb.project(target_id)
        target.note_pages[0]['html'] = target.notes_html = '<b>Edited after copy</b>'
        target.save()
        nb.save()
        nb.replay_page_transfer(change, undo=True)
        assert nb.project(target_id).notes_html == '<b>Edited after copy</b>'
        nb.replay_page_transfer(change, undo=False)
        assert nb.project(target_id).notes_html == '<b>Edited after copy</b>'
    finally:
        nb.close()


def test_transfer_undo_requires_unchanged_page_structure(tmp_path):
    nb, source_id, target_id = setup_pages(tmp_path)
    try:
        _, change = nb.transfer_pages(source_id, target_id, ['p1'],
                                      return_change=True)
        target = nb.project(target_id)
        target.pages.append({'id': 'another', 'kind': 'blank'})
        target.save()
        with pytest.raises(ValueError, match='Pages or annotations changed'):
            nb.replay_page_transfer(change, undo=True)
        assert len(nb.project(target_id).pages) == 2
    finally:
        nb.close()


def test_failed_transfer_does_not_block_future_valid_save(tmp_path, monkeypatch):
    nb, source_id, target_id = setup_pages(tmp_path)
    try:
        original_save = nb.save
        attempts = [0]
        def fail_once():
            attempts[0] += 1
            if attempts[0] == 1:
                raise OSError('injected transient error')
            return original_save()
        monkeypatch.setattr(nb, 'save', fail_once)
        with pytest.raises(OSError):
            nb.transfer_pages(source_id, target_id, ['p1'], move=True)
        assert nb.save() is False
        assert nb.transfer_pages(source_id, target_id, ['p1'], move=True) == 1
    finally:
        nb.close()


def test_sqlite_partial_write_rolls_back_every_tab_and_asset(tmp_path, monkeypatch):
    nb, source_id, target_id = setup_pages(tmp_path)
    try:
        original_files = nb._files
        before_db = db_snapshot(nb)
        before_manifests = snapshot(nb, source_id, target_id)
        def fail_after_promoted_asset():
            for relative, item in original_files():
                yield relative, item
                if relative.startswith(f'tabs/{target_id}/originals/'):
                    raise OSError('injected failure after a SQLite BLOB write')
        monkeypatch.setattr(nb, '_files', fail_after_promoted_asset)
        with pytest.raises(OSError, match='after a SQLite BLOB'):
            nb.transfer_pages(source_id, target_id, ['p1'], move=True)
        assert snapshot(nb, source_id, target_id) == before_manifests
        assert db_snapshot(nb) == before_db
        assert not list((nb.workspace / 'tabs' / target_id / 'originals').glob('*.pdf'))
    finally:
        nb.close()


def test_undo_failure_keeps_committed_transfer_intact(tmp_path, monkeypatch):
    nb, source_id, target_id = setup_pages(tmp_path)
    try:
        _, change = nb.transfer_pages(source_id, target_id, ['p1'], move=True,
                                      return_change=True)
        original_state = snapshot(nb, source_id, target_id)
        committed_db = db_snapshot(nb)
        def refuse_commit():
            raise OSError('injected undo commit failure')
        monkeypatch.setattr(nb, 'save', refuse_commit)
        with pytest.raises(OSError, match='undo commit'):
            nb.replay_page_transfer(change, undo=True)
        assert snapshot(nb, source_id, target_id) == original_state
        assert db_snapshot(nb) == committed_db
    finally:
        nb.close()


def test_undo_rejects_changed_annotations_instead_of_discarding_them(tmp_path):
    nb, source_id, target_id = setup_pages(tmp_path)
    try:
        _, change = nb.transfer_pages(source_id, target_id, ['p1'],
                                      return_change=True)
        target = nb.project(target_id)
        page_id = target.pages[0]['id']
        target.annotations[page_id] = [{'kind': 'highlight', 'x': .2, 'y': .2,
                                        'w': .2, 'h': .2, 'color': '#FFE536'}]
        target.save()
        with pytest.raises(ValueError, match='annotations changed'):
            nb.replay_page_transfer(change, undo=True)
        assert nb.project(target_id).annotations[page_id]
    finally:
        nb.close()


def test_security_rejects_symlinked_page_source(tmp_path):
    nb = Notebook.create(tmp_path, 'Symlinked Source')
    try:
        outside = tmp_path / 'outside.pdf'
        outside.write_bytes(b'private')
        project = nb.project(nb.active_id)
        link = project.path / 'originals' / 'link.pdf'
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip('Creating symlinks requires additional permissions here')
        project.pages = [{'id': 'foo', 'kind': 'pdf',
                          'source': 'originals/link.pdf'}]
        # A corrupted or hand-edited project must not allow a symlink
        # to escape the notebook's internal asset directory.
        project.save()
        with pytest.raises(ValueError, match='outside|escapes'):
            Project.load(project.path)
    finally:
        nb.close()


def test_undo_preserves_unrelated_later_reading_positions(tmp_path):
    nb, source_id, target_id = setup_pages(tmp_path)
    try:
        count, change = nb.transfer_pages(source_id, target_id, ['p1'],
                                          move=True, return_change=True)
        assert count == 1
        source = nb.project(source_id)
        # p2 did not participate in the transfer; the user has since read it.
        source.reading_view['positions']['p2'] = {
            'x': .1, 'y': .8, 'bottom': False}
        source.save()
        nb.save()
        nb.replay_page_transfer(change, undo=True)
        source_after = nb.project(source_id)
        assert source_after.reading_view['positions']['p2']['y'] == .8
        assert source_after.reading_view['positions']['p1']['y'] == .3
    finally:
        nb.close()
