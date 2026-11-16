"""v0.9.0b3 safety tests for deliberate overwrite / newer-file handling."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from yomunote.notebook import Notebook, NotebookNewerVersionError
from yomunote.notebook_lock import NotebookExternallyModifiedError
from yomunote.safe_backup import list_snapshots, restore_snapshot
from yomunote.safe_overwrite import read_destination_info, save_copy_as


def make_notebook(folder, name, text):
    nb = Notebook.create(folder, name, extension='.pinbunote')
    path = nb.path
    p = nb.project(nb.active_id)
    p.notes_html = text
    p.save()
    nb.save()
    nb.close()
    return path


def patch_version(path, *, app=None, fmt=None):
    with closing(sqlite3.connect(path)) as db, db:
        meta = json.loads(db.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()[0])
        if app is not None:
            meta['app_version'] = app
        if fmt is not None:
            meta['version'] = fmt
        db.execute("UPDATE meta SET value=? WHERE key='manifest'", (json.dumps(meta),))


def test_overwrite_creates_verified_destination_history_and_restores_old_content(tmp_path, monkeypatch):
    import yomunote.safe_overwrite as mod
    monkeypatch.setattr(mod, 'working_root', lambda: tmp_path / 'working')
    src = make_notebook(tmp_path / 'source', 'Source', '<p>NEW notes</p>')
    dest = make_notebook(tmp_path / 'cloud', 'Destination', '<p>OLD notes</p>')
    original = dest.read_bytes()
    with closing(sqlite3.connect(dest)) as db, db:
        old_id = json.loads(db.execute(
            "SELECT value FROM meta WHERE key='manifest'").fetchone()[0])['id']
    output, snapshot = save_copy_as(src, dest, backup_directory=tmp_path/'backups')
    assert output == dest
    assert snapshot and snapshot.exists()
    assert snapshot.parent.parent.parent.name == 'Destination'
    from yomunote.safe_backup import BACKUP_MARKER
    marker = json.loads((snapshot.parent.parent.parent / BACKUP_MARKER).read_text())
    assert marker['notebook_id'] == old_id
    assert snapshot.parent.parent.parent.joinpath('assets').is_dir()
    assert snapshot.parent.parent.parent.joinpath('data', 'objects').is_dir()
    assert list_snapshots(snapshot.parent.parent.parent)[0]['reason'] == 'pre-overwrite'
    restored = tmp_path/'Before overwrite.pinbunote'
    restore_snapshot(snapshot.parent.parent.parent, restored)
    older = Notebook.load(restored)
    assert older.project(older.active_id).notes_html == '<p>OLD notes</p>'
    older.close()
    newer = Notebook.load(output)
    assert newer.project(newer.active_id).notes_html == '<p>NEW notes</p>'
    newer.close()
    assert dest.read_bytes() != original


def test_newer_app_destination_demands_explicit_override_and_backs_up(tmp_path, monkeypatch):
    import yomunote.safe_overwrite as mod
    monkeypatch.setattr(mod, 'working_root', lambda: tmp_path/'working')
    src = make_notebook(tmp_path/'source', 'Source', '<p>New</p>')
    dest = make_notebook(tmp_path/'cloud', 'Dest', '<p>Created in future app</p>')
    patch_version(dest, app='99.0.0')
    assert read_destination_info(dest).newer_application
    untouched = dest.read_bytes()
    with pytest.raises(NotebookNewerVersionError, match='STRONGLY'):
        save_copy_as(src, dest, backup_directory=tmp_path/'backups')
    assert dest.read_bytes() == untouched
    out, snap = save_copy_as(src, dest, backup_directory=tmp_path/'backups',
                             allow_newer_application=True)
    assert out == dest and snap.is_file()
    entry = list_snapshots(snap.parent.parent.parent)[0]
    assert entry['reason'] == 'pre-overwrite'
    # Future app version retained in archive; old app refuses to restore it
    # until upgraded, but it has NOT lost the protected original contents.
    snapshot_json = json.loads(snap.read_text())
    assert snapshot_json['manifest']['app_version'] == '99.0.0'


def test_future_format_cannot_be_overwritten_even_when_user_approves(tmp_path, monkeypatch):
    import yomunote.safe_overwrite as mod
    monkeypatch.setattr(mod, 'working_root', lambda: tmp_path/'working')
    src = make_notebook(tmp_path/'source', 'Source', '<p>new</p>')
    dest = make_notebook(tmp_path/'cloud', 'Future', '<p>future</p>')
    patch_version(dest, app='99.0.0', fmt=99)
    before = dest.read_bytes()
    with pytest.raises(NotebookNewerVersionError, match='must NOT be overwritten'):
        save_copy_as(src, dest, backup_directory=tmp_path/'backups',
                     allow_newer_application=True)
    assert dest.read_bytes() == before
    assert not list((tmp_path/'backups').glob('*')) if (tmp_path/'backups').exists() else True


def test_bad_backup_never_replaces_destination(tmp_path, monkeypatch):
    import yomunote.safe_overwrite as mod
    monkeypatch.setattr(mod, 'working_root', lambda: tmp_path/'working')
    src = make_notebook(tmp_path/'source', 'Source', '<p>new</p>')
    dest = make_notebook(tmp_path/'cloud', 'Dest', '<p>keep</p>')
    unchanged = dest.read_bytes()
    monkeypatch.setattr(mod, 'verify_snapshot', lambda *a, **k: (_ for _ in ()).throw(IOError('verification failed')))
    with pytest.raises(IOError, match='verification failed'):
        save_copy_as(src, dest, backup_directory=tmp_path/'backups')
    assert dest.read_bytes() == unchanged
    assert not list(dest.parent.glob('*.pinbu-copy-*.pinbunote'))


def test_external_change_during_backup_blocks_overwrite(tmp_path, monkeypatch):
    import yomunote.safe_overwrite as mod
    monkeypatch.setattr(mod, 'working_root', lambda: tmp_path/'working')
    src = make_notebook(tmp_path/'source', 'Source', '<p>new</p>')
    dest = make_notebook(tmp_path/'cloud', 'Dest', '<p>old</p>')
    original = mod.create_snapshot
    def mutate_destination(*args, **kwargs):
        result = original(*args, **kwargs)
        with closing(sqlite3.connect(dest)) as db, db:
            db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", ('external_change','a'))
        return result
    monkeypatch.setattr(mod, 'create_snapshot', mutate_destination)
    with pytest.raises(NotebookExternallyModifiedError, match='changed'):
        save_copy_as(src, dest, backup_directory=tmp_path/'backups')
    with closing(sqlite3.connect(dest)) as db, db:
        assert db.execute("SELECT value FROM meta WHERE key='external_change'").fetchone()[0] == 'a'


def test_new_filename_does_not_replace_late_created_file(tmp_path, monkeypatch):
    src = make_notebook(tmp_path/'source', 'Source', '<p>New</p>')
    dest = tmp_path/'cloud'/'Extra.pinbunote'
    output, backup = save_copy_as(src, dest, backup_directory=tmp_path/'backups')
    assert output.exists() and backup is None
    patch_version(dest, app='99.0.0')
    with pytest.raises(NotebookNewerVersionError):
        save_copy_as(src, dest, backup_directory=tmp_path/'backups')


def test_opening_a_newer_app_warns_and_does_not_change_notebook(tmp_path):
    dest = make_notebook(tmp_path/'cloud', 'New version', '<p>from the future</p>')
    patch_version(dest, app='99.0.0')
    data = dest.read_bytes()
    with pytest.raises(NotebookNewerVersionError, match='upgrading Pinbu'):
        Notebook.open_session(dest, tmp_path/'working')
    assert dest.read_bytes() == data


def test_publish_newer_synced_original_warns_and_keeps_local_autosave(tmp_path):
    src = make_notebook(tmp_path/'cloud', 'Cloud', '<p>original</p>')
    session = Notebook.open_session(src, tmp_path/'working')
    try:
        p = session.project(session.active_id)
        p.notes_html = '<p>local work survives</p>'
        p.save(); session.save()
        patch_version(src, app='99.0.0')
        remote = src.read_bytes()
        with pytest.raises(NotebookNewerVersionError, match='strongly recommend'):
            session.publish()
        assert src.read_bytes() == remote
        assert session.path.is_file() and session._unpublished
    finally:
        session.close()


def test_autosave_only_local_and_warns_on_newer_external_version_source_contract():
    src = Path(__file__).parents[1] / 'yomunote' / 'window.py'
    contents = src.read_text()
    assert 'def _warn_if_newer_original' in contents
    assert 'self._warn_if_newer_original()' in contents
    assert 'self._queue_background_notebook_save((pane,))' in contents
    assert 'Your local autosave will continue safely' in contents


def test_missing_page_asset_preoverwrite_backup_blocks_replacement(tmp_path, monkeypatch):
    """Don't archive a checksum-perfect but unusable old notebook and replace it."""
    import yomunote.safe_overwrite as mod
    from yomunote.safe_backup import BackupFormatError
    monkeypatch.setattr(mod, 'working_root', lambda: tmp_path/'working')
    src = make_notebook(tmp_path/'src', 'Source', '<p>new</p>')
    dest = make_notebook(tmp_path/'dest', 'Destination', '<p>old</p>')
    with closing(sqlite3.connect(dest)) as db, db:
        manifest = json.loads(db.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()[0])
        tab = manifest['tabs'][0]['id']
        rel = f'tabs/{tab}/project.json'
        row = db.execute('SELECT data FROM files WHERE path=?', (rel,)).fetchone()
        project = json.loads(row[0])
        project['pages'] = [{'id':'missing-file-page','kind':'pdf','title':'Missing',
                             'source':'originals/missing.pdf',
                             'render_source':'originals/missing.pdf','source_page':1}]
        data = json.dumps(project).encode()
        db.execute('UPDATE files SET data=?,size=? WHERE path=?', (data,len(data),rel))
    old = dest.read_bytes()
    with pytest.raises(BackupFormatError, match='missing a page asset'):
        save_copy_as(src, dest, backup_directory=tmp_path/'backups')
    assert dest.read_bytes() == old


def test_save_copy_as_respects_older_adjacent_lock(tmp_path, monkeypatch):
    from yomunote.notebook_lock import NotebookInUseError
    import yomunote.safe_overwrite as mod
    monkeypatch.setattr(mod, 'working_root', lambda: tmp_path/'working')
    src = make_notebook(tmp_path/'src', 'Source', '<p>new</p>')
    dest = make_notebook(tmp_path/'dest', 'Destination', '<p>old</p>')
    opened_in_legacy_style = Notebook.load(dest)  # holds the adjacent .lock
    before = dest.read_bytes()
    try:
        with pytest.raises(NotebookInUseError):
            save_copy_as(src, dest, backup_directory=tmp_path/'backups')
    finally:
        opened_in_legacy_style.close()
    assert dest.read_bytes() == before


def test_save_copy_as_rejects_live_sqlite_wal_sidecars(tmp_path, monkeypatch):
    import yomunote.safe_overwrite as mod
    monkeypatch.setattr(mod, 'working_root', lambda: tmp_path/'working')
    src = make_notebook(tmp_path/'src', 'Source', '<p>new</p>')
    dest = make_notebook(tmp_path/'dest', 'Destination', '<p>old</p>')
    original = dest.read_bytes()
    sidecar = dest.with_name(dest.name + '-wal')
    sidecar.write_bytes(b'pending transactions')
    try:
        with pytest.raises(OSError, match='journal or WAL'):
            save_copy_as(src, dest, backup_directory=tmp_path/'backups')
    finally:
        sidecar.unlink()
    assert dest.read_bytes() == original
