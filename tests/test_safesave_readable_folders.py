"""v0.9.0b4: readable, source-safe, non-destructive backup folders."""
import json
import shutil

import pytest

from yomunote.notebook import Notebook
from yomunote.safe_backup import (
    BACKUP_MARKER, BACKUP_README, BackupFormatError,
    _safe_name, create_snapshot, export_portable, list_snapshots,
    project_folder, restore_snapshot,
)


def _book(tmp_path, title='Sociology'):
    nb = Notebook.create(tmp_path/'originals', title, extension='.pinbunote')
    p = nb.project(nb.active_id)
    asset = p.asset_path('originals/example.pdf')
    asset.write_bytes(b'%PDF same file'*1024)
    p.pages.append({'id':'page1', 'kind':'pdf', 'title':'Reading',
                    'source':'originals/example.pdf',
                    'render_source':'originals/example.pdf', 'source_page':1})
    p.save()
    nb.save()
    return nb


def test_readable_index_and_preservation_of_readme(tmp_path):
    nb = _book(tmp_path)
    snapshots = tmp_path/'backups'
    first, root = create_snapshot(nb.path, snapshots)
    assert root.name == 'Sociology'
    readme = root / BACKUP_README
    content = readme.read_text()
    assert 'PLEASE DO NOT rename, move or delete individual files' in content
    assert 'Restore From Backup' in content
    marker = json.loads((root / BACKUP_MARKER).read_text())
    assert marker['notebook_id'] == nb.identifier
    assert marker['source_key'] and len(marker['source_key']) == 12
    readme.write_text('User added a personal note')
    second, root2 = create_snapshot(nb.path, snapshots, force=True, reason='close')
    assert root2 == root
    assert readme.read_text() == 'User added a personal note'
    assert second != first
    assert len(list((root/'assets').glob('*/*.bin'))) == 1
    nb.close()


def test_legacy_history_migrates_with_unchanged_assets_and_restores(tmp_path):
    nb = _book(tmp_path)
    backups = tmp_path/'backups'
    first, root = create_snapshot(nb.path, backups)
    original_snapshot = first.read_bytes()
    asset = next((root/'assets').glob('*/*.bin'))
    original_asset = asset.read_bytes()
    from yomunote.safe_backup import _verify_marker
    source_key = _verify_marker(root)['source_key']
    old = backups / f'Sociology--{source_key}--{nb.identifier}'
    root.rename(old)
    assert old.exists()
    second, migrated = create_snapshot(nb.path, backups, force=True, reason='close')
    assert migrated == root
    assert not old.exists()
    assert second != first
    assert (migrated/'data'/'snapshots'/first.name).read_bytes() == original_snapshot
    assert next((migrated/'assets').glob('*/*.bin')).read_bytes() == original_asset
    nb.close()
    target = tmp_path/'restored.pinbunote'
    restore_snapshot(migrated, target, snapshot_id=first.stem)
    opened = Notebook.load(target)
    try:
        assert opened.project(opened.active_id).pages[0]['id'] == 'page1'
        assert opened.project(opened.active_id).asset_path('originals/example.pdf').read_bytes() == original_asset
    finally:
        opened.close()


def test_legacy_migration_handles_existing_readable_folder_safely(tmp_path):
    nb = _book(tmp_path)
    backups = tmp_path/'backups'
    _, root = create_snapshot(nb.path, backups)
    marker = json.loads((root / BACKUP_MARKER).read_text())
    legacy = backups / f'Sociology--{marker["source_key"]}--{nb.identifier}'
    root.rename(legacy)
    root.mkdir()
    (root/'Important.txt').write_text('DO NOT TOUCH')
    _, migrated = create_snapshot(nb.path, backups, force=True)
    assert migrated.name == 'Sociology (2)'
    assert (root/'Important.txt').read_text() == 'DO NOT TOUCH'
    assert not legacy.exists()
    nb.close()


def test_two_copies_same_uuid_separate_index_not_name(tmp_path):
    nb = _book(tmp_path)
    nb.close()
    second_path = tmp_path/'other'/'Copied.pinbunote'
    second_path.parent.mkdir()
    shutil.copyfile(nb.path, second_path)
    backups = tmp_path/'backups'
    _, a = create_snapshot(nb.path, backups)
    _, b = create_snapshot(second_path, backups)
    assert {a.name,b.name} == {'Sociology', 'Sociology (2)'}
    assert a != b
    assert json.loads((a/BACKUP_MARKER).read_text())['source_key'] != json.loads((b/BACKUP_MARKER).read_text())['source_key']
    with pytest.raises(BackupFormatError, match='Multiple backup histories'):
        project_folder(backups, nb.identifier, 'Sociology')


def test_manual_folder_rename_keeps_history(tmp_path):
    nb = _book(tmp_path)
    backups = tmp_path/'backups'
    _, root = create_snapshot(nb.path, backups)
    custom = backups/'My own backup folder'
    root.rename(custom)
    _, next_root = create_snapshot(nb.path, backups, force=True)
    assert next_root == custom
    assert len(list_snapshots(custom)) == 2
    nb.close()


def test_duplicate_indexes_block_silent_merging(tmp_path):
    nb = _book(tmp_path)
    backups = tmp_path/'backups'
    _, root = create_snapshot(nb.path, backups)
    duplicate = backups/'Accidental second history'
    shutil.copytree(root, duplicate)
    with pytest.raises(BackupFormatError, match='Duplicate backup histories'):
        create_snapshot(nb.path, backups)
    assert root.is_dir() and duplicate.is_dir()
    nb.close()


def test_portable_archive_with_readme_restores(tmp_path):
    nb = _book(tmp_path)
    _, root = create_snapshot(nb.path, tmp_path/'backups')
    out = tmp_path/'portable.pinbubackup'
    export_portable(root, out)
    shutil.rmtree(root)
    assert list_snapshots(out)
    nb.close()
    dest = tmp_path/'new.pinbunote'
    restore_snapshot(out, dest)
    opened = Notebook.load(dest)
    assert opened.project(opened.active_id).pages[0]['id'] == 'page1'
    opened.close()


def test_cross_platform_folder_names():
    assert _safe_name('CON') == '_CON'
    assert _safe_name('A:B/C?*D') == 'A_B_C__D'
    assert _safe_name('My Notes.   ') == 'My Notes'
    assert _safe_name('  ') == 'Notebook'
    assert _safe_name('FMSU9A3 Copy') == 'FMSU9A3 Copy'
