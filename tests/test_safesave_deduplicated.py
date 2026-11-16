"""Pinbu SafeSave: per-project, deduplicated assets and immutable snapshots."""
import json
import sqlite3
from pathlib import Path

import pytest

from yomunote.notebook import Notebook
from yomunote.vector_marks import make_shape
from yomunote.safe_backup import (
    BACKUP_MARKER, BACKUP_README, BackupFormatError, create_snapshot, list_snapshots,
    prune_snapshots, restore_snapshot, project_folder, export_portable,
)


def _add_pdf(notebook, name='book.pdf', contents=b'%PDF example' * 5000):
    project = notebook.project(notebook.active_id)
    source = project.asset_path('originals/' + name)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(contents)
    project.pages.append({'id': 'page-1', 'kind': 'pdf', 'title': 'Reading',
                          'source': 'originals/' + name,
                          'render_source': 'originals/' + name,
                          'source_page': 1})
    project.save()
    notebook.save()
    return contents


def test_per_project_folders_share_assets_and_restore_deleted_page(tmp_path):
    original = Notebook.create(tmp_path, 'Sociology', extension='.pinbunote')
    pdf = _add_pdf(original)
    backup_base = tmp_path / 'Backups'
    first, root = create_snapshot(original.path, backup_base, reason='manual')
    assert root.name == 'Sociology'
    assert (root / BACKUP_MARKER).is_file()
    assert (root / BACKUP_README).is_file()
    assert (root / 'data' / 'snapshots').is_dir()
    assert len(list((root / 'assets').glob('*/*.bin'))) == 1
    project = original.project(original.active_id)
    project.notes_html = '<p>Important annotation</p>'
    project.annotations = {'page-1': [make_shape('rectangle', (.2,.2), (.5,.5), '#ee9834', .006)]}
    project.save()
    original.save()
    second, second_root = create_snapshot(original.path, backup_base, reason='automatic')
    assert second_root == root
    assert first != second
    assert len(list((root / 'assets').glob('*/*.bin'))) == 1
    # Delete an actual imported page. Its old snapshot must survive.
    project.pages.clear()
    project.annotations.clear()
    project.save()
    original.save()
    third, _ = create_snapshot(original.path, backup_base, reason='automatic')
    assert len(list((root / 'assets').glob('*/*.bin'))) == 1
    original.close()
    old_path = tmp_path / 'Restored Previous.pinbunote'
    restore_snapshot(root / BACKUP_MARKER, old_path, snapshot_id=second.stem)
    recovered = Notebook.load(old_path)
    assert recovered.project(recovered.active_id).notes_html == '<p>Important annotation</p>'
    assert recovered.project(recovered.active_id).pages[0]['id'] == 'page-1'
    assert recovered.project(recovered.active_id).asset_path('originals/book.pdf').read_bytes() == pdf
    recovered.close()
    latest_path = tmp_path / 'Restored Latest.pinbunote'
    restore_snapshot(root, latest_path, snapshot_id=third.stem)
    latest = Notebook.load(latest_path)
    assert not latest.project(latest.active_id).pages
    latest.close()


def test_same_title_projects_do_not_share_backup_data(tmp_path):
    folder = tmp_path / 'Backups'
    one = Notebook.create(tmp_path / 'A', 'Sociology', extension='.pinbunote')
    two = Notebook.create(tmp_path / 'B', 'Sociology', extension='.pinbunote')
    a, ar = create_snapshot(one.path, folder)
    b, br = create_snapshot(two.path, folder)
    assert ar != br
    assert a != b
    assert project_folder(folder, one.identifier, one.name) == ar
    one.close(); two.close()


def test_unchanged_skips_automatic_but_close_creates_distinct_snapshot(tmp_path):
    nb = Notebook.create(tmp_path, 'Books', extension='.pinbunote')
    rootbase = tmp_path / 'Backups'
    first, root = create_snapshot(nb.path, rootbase)
    none, _ = create_snapshot(nb.path, rootbase)
    assert none is None
    latest, _ = create_snapshot(nb.path, rootbase, force=True, reason='close')
    assert latest and latest != first
    assert list_snapshots(root)[0]['reason'] == 'close'
    nb.close()


def test_reject_tampered_blob_and_existing_restoration(tmp_path):
    nb = Notebook.create(tmp_path, 'Maths', extension='.pinbunote')
    _add_pdf(nb)
    snap, root = create_snapshot(nb.path, tmp_path / 'Backups')
    file = next((root / 'assets').glob('*/*.bin'))
    file.write_bytes(b'corrupted')
    dest = tmp_path / 'Not Restorable.pinbunote'
    with pytest.raises(BackupFormatError):
        restore_snapshot(root, dest, snapshot_id=snap.stem)
    assert not dest.exists()
    dest.write_bytes(b'keep me')
    with pytest.raises(FileExistsError):
        restore_snapshot(root, dest, snapshot_id=snap.stem)
    assert dest.read_bytes() == b'keep me'
    nb.close()


def test_portable_export_preserves_directory_layout(tmp_path):
    nb = Notebook.create(tmp_path, 'Physics', extension='.pinbunote')
    _add_pdf(nb)
    snap, root = create_snapshot(nb.path, tmp_path/'Backups')
    out = tmp_path / 'Physics.pinbubackup'
    export_portable(root, out)
    from zipfile import ZipFile
    with ZipFile(out) as z:
        names = z.namelist()
    assert BACKUP_MARKER in names
    assert BACKUP_README in names
    assert any(x.startswith('assets/') for x in names)
    assert any(x.startswith('data/snapshots/') for x in names)
    nb.close()


def test_portable_backup_file_can_restore_independently(tmp_path):
    nb = Notebook.create(tmp_path, 'Politics', extension='.pinbunote')
    pdf = _add_pdf(nb)
    _, root = create_snapshot(nb.path, tmp_path/'Backups')
    archive = tmp_path/'Politics.pinbubackup'
    export_portable(root, archive)
    nb.close()
    # Removing the entire original project history must not affect export.
    import shutil
    shutil.rmtree(root)
    versions = list_snapshots(archive)
    assert len(versions) == 1
    recovered = tmp_path/'Politics Restored.pinbunote'
    restore_snapshot(archive, recovered)
    opened = Notebook.load(recovered)
    assert opened.project(opened.active_id).asset_path('originals/book.pdf').read_bytes() == pdf
    opened.close()


def test_copied_project_same_uuid_keeps_separate_history_per_source(tmp_path):
    nb = Notebook.create(tmp_path/'A', 'Books', extension='.pinbunote')
    source = nb.path
    nb.close()
    copy = tmp_path/'B'/'Copied.pinbunote'
    copy.parent.mkdir()
    copy.write_bytes(source.read_bytes())
    first, root_first = create_snapshot(source, tmp_path/'Backups')
    second, root_second = create_snapshot(copy, tmp_path/'Backups')
    assert root_first != root_second
    assert root_first.parent == root_second.parent
    assert {root_first.name, root_second.name} == {'Books', 'Books (2)'}
