"""Local sessions never autosave onto the cloud-facing original."""
import sqlite3
from contextlib import closing
from pathlib import Path
import pytest
from yomunote.notebook import Notebook, NotebookNewerVersionError
from yomunote.notebook_lock import NotebookExternallyModifiedError
from yomunote.safe_session import recoverable_sessions
from yomunote.safe_backup import create_snapshot, restore_snapshot, list_snapshots


def test_session_autosaves_only_locally_and_publishes_on_explicit_save(tmp_path):
    original = Notebook.create(tmp_path/'cloud', 'Film', extension='.pinbunote')
    source = original.path
    original.close()
    initial = source.read_bytes()
    session = Notebook.open_session(source, tmp_path/'local')
    assert session.path != source and session.display_path == source
    project = session.project(session.active_id)
    project.notes_html = '<p>From laptop</p>'
    project.save()
    session.save()
    assert session._unpublished
    assert source.read_bytes() == initial
    session.safesave_backup(tmp_path/'backups', force=True, reason='close')
    assert recoverable_sessions(tmp_path/'local')
    session.publish()
    assert not session._unpublished
    session.close()
    assert not session._session_dir.exists()
    read = Notebook.load(source)
    assert read.project(read.active_id).notes_html == '<p>From laptop</p>'
    read.close()


def test_external_change_blocks_publish_but_preserves_local_work(tmp_path):
    nb = Notebook.create(tmp_path/'cloud', 'Math', extension='.pinbunote')
    source = nb.path
    nb.close()
    s = Notebook.open_session(source, tmp_path/'local')
    project = s.project(s.active_id)
    project.notes_html = '<p>Keep this!</p>'
    project.save(); s.save()
    # Simulate Dropbox replacing the original file from another device.
    other = Notebook.create(tmp_path/'other', 'External', extension='.pinbunote')
    other.close()
    source.write_bytes(other.path.read_bytes())
    existing = source.read_bytes()
    with pytest.raises(NotebookExternallyModifiedError):
        s.publish()
    assert source.read_bytes() == existing
    assert s.path.exists()
    snapshot = s.safesave_backup(tmp_path/'backups', force=True, reason='close')
    assert snapshot
    s.close()
    assert s._session_dir.exists()  # unpublished working copy retained
    # The last backup remains independently restorable.
    recovered = tmp_path/'recovery.pinbunote'
    restore_snapshot(snapshot.parent.parent.parent, recovered)
    copy = Notebook.load(recovered)
    assert copy.project(copy.active_id).notes_html == '<p>Keep this!</p>'
    copy.close()


def test_open_same_cloud_notebook_twice_locally_is_rejected(tmp_path):
    original = Notebook.create(tmp_path/'cloud','Shared',extension='.pinbunote')
    source = original.path
    original.close()
    s = Notebook.open_session(source, tmp_path/'local')
    with pytest.raises(Exception, match='already open|Close the other|open'):
        Notebook.open_session(source, tmp_path/'local')
    s.close()


def test_newer_app_version_is_rejected_with_advice(tmp_path):
    nb = Notebook.create(tmp_path, 'Ahead', extension='.pinbunote')
    nb.close()
    with closing(sqlite3.connect(nb.path)) as db, db:
        import json
        data = json.loads(db.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()[0])
        data['app_version'] = '99.0.0'
        db.execute("UPDATE meta SET value=? WHERE key='manifest'", (json.dumps(data),))
    with pytest.raises(NotebookNewerVersionError, match='newer Pinbu Note'):
        Notebook.load(nb.path)


def test_repeated_save_without_changes_does_not_replace_cloud_file(tmp_path):
    original = Notebook.create(tmp_path/'cloud', 'Save once', extension='.pinbunote')
    source = original.path
    original.close()
    s = Notebook.open_session(source, tmp_path/'local')
    project = s.project(s.active_id)
    project.notes_html = '<p>Test</p>'
    project.save(); s.save(); s.publish()
    original_sig = s._origin_signature
    assert s.publish() == source
    assert s._origin_signature == original_sig
    s.close()


def test_local_lock_is_not_created_in_dropbox_folder(tmp_path):
    src = Notebook.create(tmp_path/'Dropbox', 'Locked', extension='.pinbunote')
    original = src.path
    src.close()
    # Notebook.create (pre-SafeSave API) intentionally leaves its durable
    # historical adjacent lockfile; staging must not touch or change it.
    adjacent = original.parent / (original.name + '.lock')
    prior = (adjacent.stat().st_mtime_ns, adjacent.stat().st_size)
    s = Notebook.open_session(original, tmp_path/'local')
    try:
        assert (adjacent.stat().st_mtime_ns, adjacent.stat().st_size) == prior
    finally:
        s.close()


def test_publish_uses_writable_descriptor_for_windows_fsync(tmp_path, monkeypatch):
    """Windows os.fsync -> CRT _commit rejects a read-only fd with EBADF.

    Simulate that Windows-only restriction on Linux in CI, so the bug cannot
    return just because POSIX accepts fsync on read-only file descriptors.
    """
    import os
    import errno
    original = Notebook.create(tmp_path/'cloud', 'Windows publish', extension='.pinbunote')
    source = original.path
    original.close()
    session = Notebook.open_session(source, tmp_path/'local')
    try:
        project = session.project(session.active_id)
        project.notes_html = '<p>Windows publication test</p>'
        project.save()
        session.save()
        source_before = source.read_bytes()
        real_open = Path.open
        real_fsync = os.fsync
        opened_modes = {}
        flushed_publish_file = []

        def observe_open(path, mode='r', *args, **kwargs):
            stream = real_open(path, mode, *args, **kwargs)
            if '.pinbu-publish-' in path.name:
                opened_modes[stream.fileno()] = mode
            return stream

        def windows_fsync(fd):
            mode = opened_modes.get(fd)
            if mode == 'rb':
                raise OSError(errno.EBADF, 'Bad file descriptor')
            if mode == 'r+b':
                flushed_publish_file.append(True)
            return real_fsync(fd)

        monkeypatch.setattr(Path, 'open', observe_open)
        monkeypatch.setattr(os, 'fsync', windows_fsync)
        assert session.publish() == source
        assert flushed_publish_file, 'Publishing must sync its temporary file'
        assert source.read_bytes() != source_before
        assert not session._unpublished
    finally:
        session.close()


def test_publish_fsync_failure_retains_original_and_local_edits(tmp_path, monkeypatch):
    """A failed pre-publish flush must never damage the original notebook."""
    import os
    import errno
    original = Notebook.create(tmp_path/'cloud', 'Fail-safe publish', extension='.pinbunote')
    source = original.path
    original.close()
    session = Notebook.open_session(source, tmp_path/'local')
    try:
        project = session.project(session.active_id)
        project.notes_html = '<p>Unpublished edits must survive</p>'
        project.save()
        session.save()
        source_before = source.read_bytes()
        real_open = Path.open
        real_fsync = os.fsync
        temporary_handles = set()

        def observe_open(path, mode='r', *args, **kwargs):
            stream = real_open(path, mode, *args, **kwargs)
            if '.pinbu-publish-' in path.name:
                temporary_handles.add(stream.fileno())
            return stream

        def fail_temp_fsync(fd):
            if fd in temporary_handles:
                raise OSError(errno.EIO, 'Simulated disk flush failure')
            return real_fsync(fd)

        monkeypatch.setattr(Path, 'open', observe_open)
        monkeypatch.setattr(os, 'fsync', fail_temp_fsync)
        with pytest.raises(OSError, match='Simulated disk flush failure'):
            session.publish()
        assert source.read_bytes() == source_before
        assert session._unpublished
        assert session.path.exists()
        assert not list(source.parent.glob('*.pinbu-publish-*.tmp'))
    finally:
        session.close()


def test_project_noop_save_does_not_create_false_unpublished_changes(tmp_path):
    """Project.save used to rewrite updated_at every time it was called."""
    original = Notebook.create(tmp_path/'cloud', 'Noop', extension='.pinbunote')
    source = original.path
    original.close()
    s = Notebook.open_session(source, tmp_path/'local')
    try:
        p = s.project(s.active_id)
        p.save()
        assert s.save() is False  # Repeated no-op save must not create a commit.
        s.publish()
        assert not s._unpublished
        saved = (p.path/'project.json').read_bytes()
        p.save()
        assert (p.path/'project.json').read_bytes() == saved
        assert s.save() is False
        assert not s._unpublished, 'A no-op close must not invent an unpublished edit'
    finally:
        s.close()


def test_crashed_session_is_detected_but_live_session_is_not(tmp_path):
    from yomunote.safe_session import interrupted_sessions
    origin = Notebook.create(tmp_path/'cloud', 'Interrupted', extension='.pinbunote')
    path = origin.path
    origin.close()
    s = Notebook.open_session(path, tmp_path/'local')
    project = s.project(s.active_id)
    project.notes_html = '<p>Crash before cloud publish</p>'
    project.save()
    s.save()
    assert not interrupted_sessions(tmp_path/'local'), 'A live editing process is not a crash'
    # Emulate operating system release of OS locks when a process is killed.
    s._lease.release()
    s._origin_lease.release()
    candidates = interrupted_sessions(tmp_path/'local')
    assert len(candidates) == 1
    assert candidates[0]['unpublished']
    recovered_path = tmp_path/'recovery.pinbunote'
    Notebook.restore_copy(Path(candidates[0]['working']), recovered_path)
    recovered = Notebook.load(recovered_path)
    assert recovered.project(recovered.active_id).notes_html == '<p>Crash before cloud publish</p>'
    recovered.close()
    # Close the simulated session to avoid leaving temporary resources.
    s.close()
    assert not interrupted_sessions(tmp_path/'local')


def test_normal_unpublished_close_does_not_trigger_crash_prompt(tmp_path):
    from yomunote.safe_session import interrupted_sessions
    origin = Notebook.create(tmp_path/'cloud', 'Intentional', extension='.pinbunote')
    path = origin.path
    origin.close()
    s = Notebook.open_session(path, tmp_path/'local')
    p = s.project(s.active_id)
    p.notes_html = '<p>Intentionally not published</p>'
    p.save()
    s.save()
    s.safesave_backup(tmp_path/'backups', force=True, reason='close')
    s.close()
    assert not interrupted_sessions(tmp_path/'local')
    records = recoverable_sessions(tmp_path/'local')
    assert len(records) == 1
    assert records[0]['status'] == 'closed'
    assert records[0]['unpublished'], 'User can still recover unsynced edits manually'


def test_not_now_acknowledges_crash_without_deleting_recovery(tmp_path):
    from yomunote.safe_session import interrupted_sessions, acknowledge_interrupted_session
    origin = Notebook.create(tmp_path/'cloud', 'Not now', extension='.pinbunote')
    path = origin.path
    origin.close()
    s = Notebook.open_session(path, tmp_path/'local')
    p = s.project(s.active_id)
    p.notes_html = 'Important'
    p.save()
    s.save()
    s._lease.release()
    s._origin_lease.release()
    latest = interrupted_sessions(tmp_path/'local')[0]
    assert acknowledge_interrupted_session(latest)
    assert not interrupted_sessions(tmp_path/'local')
    records = recoverable_sessions(tmp_path/'local')
    assert len(records) == 1 and records[0]['status'] == 'interrupted'
    assert Path(records[0]['working']).exists()
    s.close()


def test_old_session_without_close_marker_is_not_misdiagnosed(tmp_path):
    from yomunote.safe_session import interrupted_sessions
    import json
    origin = Notebook.create(tmp_path/'cloud', 'Legacy markers', extension='.pinbunote')
    path = origin.path
    origin.close()
    s = Notebook.open_session(path, tmp_path/'local')
    descriptor = s._session_dir/'session.json'
    state = json.loads(descriptor.read_text())
    state.pop('status', None)
    descriptor.write_text(json.dumps(state))
    s._lease.release()
    s._origin_lease.release()
    assert not interrupted_sessions(tmp_path/'local')
    assert len(recoverable_sessions(tmp_path/'local')) == 1
    s.close()


def test_gui_exit_dialog_contract_is_explicit_and_non_destructive():
    from pathlib import Path
    window = (Path(__file__).resolve().parents[1] / 'yomunote/window.py').read_text(encoding='utf-8')
    assert "dialog.addButton('Save & Close'" in window
    assert "dialog.addButton('Close Without Saving'" in window
    assert "dialog.addButton('Go back'" in window
    assert 'self.notebook.publish()' in window
    assert 'mark_normal_close(self.notebook)' in window
    assert 'self._offer_crash_recovery' in window


def test_open_from_previous_release_does_not_invent_unsaved_changes(tmp_path):
    """An app-version stamp alone must not mark an otherwise clean notebook."""
    import json
    original = Notebook.create(tmp_path/'cloud', 'OldRelease', extension='.pinbunote')
    path = original.path
    original.close()
    with closing(sqlite3.connect(path)) as db, db:
        row = db.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()
        header = json.loads(row[0])
        header['app_version'] = '0.9.0b1'
        db.execute("UPDATE meta SET value=? WHERE key='manifest'", (json.dumps(header),))
        for rel, payload in db.execute("SELECT path, data FROM files WHERE path LIKE '%/project.json'").fetchall():
            project = json.loads(payload)
            project['app_version'] = '0.9.0b1'
            data = json.dumps(project, ensure_ascii=False, indent=2).encode('utf-8')
            db.execute("UPDATE files SET data=?, size=? WHERE path=?", (data, len(data), rel))
    before = path.read_bytes()
    s = Notebook.open_session(path, tmp_path/'local')
    try:
        p = s.project(s.active_id)
        p.save()
        assert s.save() is False
        assert not s._unpublished
        s.publish()
        assert path.read_bytes() == before, 'Save with no edits must not rewrite Dropbox'
        p.notes_html = '<p>Now this is a real edit</p>'
        p.save()
        assert s.save()
        assert s._unpublished
        s.publish()
        assert path.read_bytes() != before
        with closing(sqlite3.connect(path)) as db, db:
            manifest = json.loads(db.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()[0])
        assert manifest['app_version'] == '1.0'
    finally:
        s.close()
