"""Migration must be safe, idempotent, and preserve old full snapshots."""
import json
import shutil

from yomunote.backup_migration import scan_legacy_backups, migrate_legacy_backups
from yomunote.notebook import Notebook
from yomunote.project import Project
from yomunote.safe_backup import BACKUP_MARKER, BACKUP_README, create_snapshot, list_snapshots, restore_snapshot


def _book(tmp_path):
    nb = Notebook.create(tmp_path/'live', 'Literature', extension='.pinbunote')
    p = nb.project(nb.active_id)
    p.notes_html = '<p>First draft</p>'
    p.asset_path('originals/my.pdf').write_bytes(b'%PDF-1.4 example pdf content' * 100)
    p.pages = [{'id': 'page-one', 'kind': 'pdf', 'title': 'Reading',
                'source': 'originals/my.pdf', 'render_source': 'originals/my.pdf', 'source_page':1}]
    p.save()
    nb.save()
    return nb


def test_import_old_complete_backups_keeps_originals_and_versions(tmp_path):
    nb = _book(tmp_path)
    source = tmp_path/'Old backups'
    source.mkdir()
    first = source / f'{nb.identifier}_20261110-143000-000001.pinbunote'
    shutil.copyfile(nb.path, first)
    p = nb.project(nb.active_id)
    p.notes_html = '<p>Second draft</p>'
    p.save()
    nb.save()
    second = source / f'{nb.identifier}_20261111-143000-000001.pinbunote'
    shutil.copyfile(nb.path, second)
    nb.close()

    target = tmp_path/'Backups'
    items, issues = scan_legacy_backups(source)
    assert not issues and len(items) == 2
    assert {x.kind for x in items} == {'notebook-file'}
    outcome = migrate_legacy_backups(items, target)
    assert outcome.converted == 2 and outcome.failed == 0, outcome.failures
    assert first.is_file() and second.is_file()
    roots = [p for p in target.iterdir() if (p / BACKUP_MARKER).exists()]
    assert len(roots) == 1
    root = roots[0]
    assert root.name == 'Literature'
    assert (root / BACKUP_README).exists()
    assert len(list_snapshots(root)) == 2
    assert len(list((root / 'assets').glob('*/*.bin'))) == 1
    stamps = [x['timestamp'] for x in list_snapshots(root)]
    assert '2026-11-10' in ''.join(stamps) and '2026-11-11' in ''.join(stamps)
    snapshots = list_snapshots(root)
    restored = tmp_path/'Restored.pinbunote'
    restore_snapshot(root, restored, snapshot_id=snapshots[1]['id'])
    back = Notebook.load(restored)
    assert back.project(back.active_id).notes_html == '<p>First draft</p>'
    back.close()
    again = migrate_legacy_backups(items, target)
    assert again.converted == 0 and again.already_imported == 2 and again.failed == 0
    assert len(list_snapshots(root)) == 2


def test_convert_old_indexed_backup_and_keep_original_folder(tmp_path):
    nb = _book(tmp_path)
    rootdir = tmp_path/'Backups'
    _, root = create_snapshot(nb.path, rootdir)
    marker = json.loads((root/BACKUP_MARKER).read_text())
    legacy = rootdir/f"Literature--{marker['source_key']}--{nb.identifier}"
    root.rename(legacy)
    nb.close()
    items, issues = scan_legacy_backups(rootdir)
    assert not issues and len(items) == 1
    assert items[0].kind == 'indexed-project'
    result = migrate_legacy_backups(items, rootdir)
    assert result.converted == 1 and not result.failed, result.failures
    new = rootdir/'Literature'
    assert (new/BACKUP_MARKER).is_file()
    assert (new/BACKUP_README).is_file()
    assert len(list_snapshots(new)) == 1
    preserved = rootdir/'_Legacy Originals (kept)'/legacy.name
    assert preserved.is_dir() and (preserved/BACKUP_MARKER).is_file()
    restored = tmp_path/'Recovered.pinbunote'
    restore_snapshot(new, restored)
    out = Notebook.load(restored)
    assert out.project(out.active_id).pages[0]['id'] == 'page-one'
    out.close()
    # Archive is excluded from another migration scan.
    assert scan_legacy_backups(rootdir)[0] == []


def test_import_very_old_project_folder_and_retry(tmp_path):
    original = Project.create(tmp_path/'Legacy', 'Ancient module')
    original.notes_html = '<p>Old notes</p>'
    original.save()
    source = tmp_path/'Legacy'
    items, issues = scan_legacy_backups(source)
    assert len(items) == 1 and not issues
    assert items[0].kind == 'legacy-folder'
    dest = tmp_path/'New backups'
    result = migrate_legacy_backups(items, dest)
    assert result.converted == 1 and result.failed == 0, result.failures
    root = result.output_folders[0]
    assert len(list_snapshots(root)) == 1
    retry = migrate_legacy_backups(items, dest)
    assert retry.already_imported == 1 and retry.failed == 0, retry.failures
    assert len(list_snapshots(root)) == 1
    restored = tmp_path/'Old recovered.pinbunote'
    restore_snapshot(root, restored)
    nb = Notebook.load(restored)
    assert nb.project(nb.active_id).notes_html == '<p>Old notes</p>'
    nb.close()
    assert (original.path/'project.json').exists()


def test_invalid_backup_is_skipped_without_impacting_valid_one(tmp_path):
    nb = _book(tmp_path)
    source = tmp_path/'Old'
    source.mkdir()
    valid = source/'valid.pinbunote'
    shutil.copyfile(nb.path, valid)
    (source/'broken.pinbunote').write_text('not a notebook')
    nb.close()
    items, issues = scan_legacy_backups(source)
    assert len(items) == 1 and len(issues) == 1
    result = migrate_legacy_backups(items, tmp_path/'converted')
    assert result.converted == 1 and result.failed == 0


def test_ui_migration_button_exists_in_preferences():
    from pathlib import Path
    source = (Path(__file__).parents[1]/'yomunote'/'window.py').read_text()
    assert "QPushButton('Migrate Legacy Backups…')" in source
    assert 'def show_backup_migration(' in source
    assert 'start_task(self, worker, finished' in source
