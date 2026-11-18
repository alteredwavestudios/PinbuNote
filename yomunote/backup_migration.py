"""Explicit, non-destructive conversion of older Pinbu/Yomu backups.

Scans only folders the user chooses (normally the configured local Backups
folder). Older complete SQLite snapshots become deduplicated .pinbubackup
versions. Earlier folder-backed notebooks can be staged and imported as well.
Old indexed project histories are copied and verified before being given a
readable name; originals remain available in _Legacy Originals (kept).

No GUI dependency. No network, no deletion of a legacy source. Running twice
is safe: migrated SQLite snapshots carry a stable import fingerprint.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .safe_backup import (BACKUP_MARKER, BACKUP_README, BackupFormatError,
                          _readable_path, _readme_once, _verify_marker,
                          create_snapshot, list_snapshots, verify_snapshot)

LEGACY_EXTS = {'.pinbunote', '.yomunote', '.yominote'}
# Earlier versions wrote full copies called <id>_<UTC>.yomunote.
OLD_TIMESTAMP = re.compile(r'(\d{8}-\d{6}-\d{6})')
MAX_SCAN_ITEMS = 30000


@dataclass(frozen=True)
class MigrationItem:
    path: Path
    kind: str                         # indexed-project, notebook-file, legacy-folder
    title: str
    notebook_id: str
    size: int
    saved_version: str = ''
    warning: str = ''


@dataclass
class MigrationReport:
    converted: int = 0
    already_imported: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[str] | None = None
    output_folders: list[str] | None = None

    def __post_init__(self):
        self.failures = [] if self.failures is None else self.failures
        self.output_folders = [] if self.output_folders is None else self.output_folders


def _manifest(path: Path):
    from .notebook import Notebook, read_bounded_manifest
    uri = path.resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=1)) as db:
        db.execute('PRAGMA query_only=ON')
        try:
            obj = read_bounded_manifest(db)
        except ValueError as exc:
            raise BackupFormatError('Missing, invalid or oversized notebook manifest.') from exc
        # Do not modify newer-app snapshots, but prohibit unknown formats.
        Notebook._check_manifest(obj, allow_newer_app=True)
        return obj


def _file_item(path: Path):
    manifest = _manifest(path)
    stat = path.stat()
    app_version = str(manifest.get('app_version') or '')
    from .notebook import _version_sortkey
    from . import __version__
    warning = ('Saved with a newer Pinbu release; upgrade before restoring it.'
               if (_version_sortkey(app_version) and _version_sortkey(__version__)
                   and _version_sortkey(app_version) > _version_sortkey(__version__))
               else '')
    return MigrationItem(path, 'notebook-file', manifest['name'], manifest['id'],
                         stat.st_size, app_version, warning)


def _folder_item(path: Path):
    # A legacy folder-backed .yominote project has project.json, originals/, etc.
    # Its original contents are never edited: conversion occurs in a temp copy.
    manifest = path / 'project.json'
    if manifest.is_symlink() or not manifest.is_file():
        raise BackupFormatError('Missing or unsafe legacy project.json.')
    if manifest.stat().st_size > 32 * 1024 * 1024:
        raise BackupFormatError('Legacy project metadata exceeds the size limit.')
    data = json.loads(manifest.read_text('utf-8'))
    title = str(data.get('name') or path.stem)[:120]
    synthetic_id = uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve())).hex
    return MigrationItem(path, 'legacy-folder', title, synthetic_id, 0,
                         'legacy directory project')


def scan_legacy_backups(source_dir: Path):
    """Return (candidates, problems), never opening live notebook locations.

    Scans no further than three directory levels. Existing SafeSave assets,
    snapshots, and retained original histories are excluded.
    """
    base = Path(source_dir).expanduser().resolve()
    if not base.is_dir():
        raise NotADirectoryError(f'Backup folder does not exist: {base}')
    found, issues = [], []
    checked = 0
    for foldername, dirs, files in os.walk(base, topdown=True, followlinks=False):
        folder = Path(foldername)
        depth = len(folder.relative_to(base).parts)
        dirs[:] = sorted(d for d in dirs if (depth < 3 and
                         d not in ('assets', 'data', '_Legacy Originals (kept)',
                                   '_Migration Staging', '__pycache__') and
                         not (folder / d).is_symlink()))
        checked += len(files) + len(dirs)
        if checked > MAX_SCAN_ITEMS:
            issues.append('Scan stopped after the safety limit of 30,000 entries.')
            break
        if (folder / BACKUP_MARKER).is_file():
            dirs.clear()
            if folder.name.startswith('.'):
                continue
            try:
                marker = _verify_marker(folder)
                if folder.name.endswith('--' + marker['notebook_id']):
                    found.append(MigrationItem(folder, 'indexed-project',
                                marker.get('notebook_name', folder.name),
                                marker['notebook_id'], 0,
                                str(marker.get('created_by', ''))))
            except Exception as exc:
                issues.append(f'{folder}: {exc}')
            continue
        if (folder / 'project.json').is_file() and folder != base:
            try:
                found.append(_folder_item(folder))
                dirs.clear()
                continue
            except Exception as exc:
                issues.append(f'{folder}: {exc}')
        for name in sorted(files):
            path = folder / name
            if path.is_symlink() or path.suffix.lower() not in LEGACY_EXTS:
                continue
            try:
                found.append(_file_item(path))
            except (OSError, ValueError, KeyError, TypeError, sqlite3.DatabaseError) as exc:
                issues.append(f'{path.name}: {exc}')
    return found, issues


def _legacy_time(source: Path):
    match = OLD_TIMESTAMP.search(source.name)
    if match:
        try:
            return datetime.strptime(match[1], '%Y%m%d-%H%M%S-%f').replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.fromtimestamp(source.stat().st_mtime, tz=timezone.utc)


def _file_key(item: MigrationItem):
    st = item.path.stat()
    value = f'{item.path.resolve()}\n{st.st_size}\n{st.st_mtime_ns}\n{item.notebook_id}'
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _verify_all(root):
    snaps = list_snapshots(root)
    if not snaps:
        raise BackupFormatError('Backup project has no recoverable snapshots.')
    for item in snaps:
        verify_snapshot(root, item['id'], allow_newer_app=True)
    return len(snaps)


def _unique_archived_location(archive: Path, basename: str):
    candidate = archive / basename
    n = 2
    while candidate.exists():
        candidate = archive / f'{basename} ({n})'
        n += 1
    return candidate


def _migrate_indexed(item: MigrationItem, destination: Path):
    """Copy, verify all snapshots, expose readable folder, retain old folder.

    If source is outside the new backup root, we leave it entirely untouched.
    Inside the root we place the original under _Legacy Originals (kept) to
    prevent two visible histories with identical internal identity.
    """
    source = item.path.resolve()
    dest = destination.resolve()
    marker = _verify_marker(source)
    source_key = marker.get('source_key')
    for directory in dest.iterdir():
        if not directory.is_dir() or directory.is_symlink() or directory == source:
            continue
        index = directory / BACKUP_MARKER
        if index.is_file():
            other = _verify_marker(directory)
            if (other['notebook_id'], other.get('source_key')) == (item.notebook_id, source_key):
                # A complete copy may exist after an interrupted prior migration.
                old = {x['id'] for x in list_snapshots(source)}
                new = {x['id'] for x in list_snapshots(directory)}
                if not old.issubset(new):
                    raise BackupFormatError('Duplicate histories differ; refusing to merge.')
                _verify_all(directory)
                if source.parent == dest:
                    archive = dest / '_Legacy Originals (kept)'
                    archive.mkdir(exist_ok=True)
                    source.rename(_unique_archived_location(archive, source.name))
                return directory, True
    target = _readable_path(dest, item.title)
    staging = dest / '_Migration Staging'
    staging.mkdir(exist_ok=True)
    temp = staging / uuid.uuid4().hex
    try:
        if any(x.is_symlink() for x in source.rglob('*')):
            raise BackupFormatError('Legacy backup contains a symlink; import blocked.')
        before_snapshots = {x['id'] for x in list_snapshots(source)}
        shutil.copytree(source, temp, symlinks=True)
        _verify_all(temp)
        if {x['id'] for x in list_snapshots(source)} != before_snapshots:
            raise BackupFormatError('Legacy history changed while copying; please retry.')
        _readme_once(temp)
        temp.rename(target)
        if source.parent == dest:
            archive = dest / '_Legacy Originals (kept)'
            archive.mkdir(exist_ok=True)
            try:
                source.rename(_unique_archived_location(archive, source.name))
            except OSError as exc:
                # Remove visible duplicate on rollback, but leave both originals.
                # Never delete a verified target: store it in staging for recovery.
                target.rename(temp)
                raise BackupFormatError(f'Original kept; could not archive legacy folder: {exc}')
        return target, False
    finally:
        # A failed/midway import remains in staging for forensic recovery.
        # Never delete any pre-existing backup material here.
        pass


def _migrate_file(item: MigrationItem, destination: Path):
    source = item.path.resolve()
    before = source.stat()
    # Each old backup directory + stable notebook ID gets its own history;
    # this cannot accidentally merge with a currently active notebook copy.
    logical = source.parent / ('.legacy-backups-' + item.notebook_id)
    marker = create_snapshot(source, destination, force=True,
                             reason='Imported legacy backup', logical_source=logical,
                             allow_newer_app=True, strict_assets=True,
                             source_time=_legacy_time(source), migration_key=_file_key(item))
    snapshot, root = marker
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise BackupFormatError('Legacy backup changed during import; original left untouched.')
    if snapshot is None:
        return root, True
    verify_snapshot(root, snapshot.stem, allow_newer_app=True)
    return root, False


def _migrate_folder(item: MigrationItem, destination: Path):
    from .notebook import Notebook
    source = item.path.resolve()
    with tempfile.TemporaryDirectory(prefix='pinbu-legacy-restore-') as scratch:
        staged = Path(scratch) / source.name
        if any(x.is_symlink() for x in source.rglob('*')):
            raise BackupFormatError('Legacy folder contains a symlink; import blocked.')
        original_stat = (source / 'project.json').stat()
        shutil.copytree(source, staged, symlinks=True)
        nb = Notebook.migrate_legacy(staged)
        try:
            # Stable identity for retries; original folder is never changed.
            nb.identifier = item.notebook_id
            nb.save()
            source_manifest = source / 'project.json'
            current_stat = source_manifest.stat()
            if (current_stat.st_size, current_stat.st_mtime_ns) != (original_stat.st_size, original_stat.st_mtime_ns):
                raise BackupFormatError('Legacy folder changed while copying.')
            stable = hashlib.sha256((str(source) + '\n' + str(original_stat.st_size) +
                                     '\n' + str(original_stat.st_mtime_ns)).encode('utf-8')).hexdigest()
            result = create_snapshot(nb.path, destination, force=True,
                                     reason='Imported legacy folder project',
                                     logical_source=source,
                                     source_time=datetime.fromtimestamp(original_stat.st_mtime, timezone.utc),
                                     migration_key=stable, strict_assets=True)
            snapshot, root = result
            if snapshot is None:
                return root, True
            verify_snapshot(root, snapshot.stem, allow_newer_app=True)
            return root, False
        finally:
            nb.close()


def migrate_legacy_backups(items: list[MigrationItem], destination: Path):
    """Import explicit previewed candidates; never delete legacy files.

    One invalid backup does not block the remaining recoverable histories.
    Idempotent for full SQLite backups and old indexed backup folders.
    """
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    report = MigrationReport()
    for item in items:
        try:
            if item.kind == 'indexed-project':
                result, existing = _migrate_indexed(item, destination)
            elif item.kind == 'notebook-file':
                result, existing = _migrate_file(item, destination)
            elif item.kind == 'legacy-folder':
                result, existing = _migrate_folder(item, destination)
            else:
                raise ValueError('Unsupported backup migration source.')
            if existing:
                report.already_imported += 1
            else:
                report.converted += 1
            report.output_folders.append(str(result))
        except Exception as exc:
            report.failed += 1
            report.failures.append(f'{item.path.name}: {type(exc).__name__}: {exc}')
    return report
