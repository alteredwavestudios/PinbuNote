"""Pinbu SafeSave v1: independently verifiable, deduplicated project histories.

Disk layout (readable directory, identity stored inside the index)::

    Backups/Sociology/
        PLEASE READ - About Your Backups.txt
        history.pinbubackup       # tiny JSON file-format descriptor; NOT the data
        assets/ab/<sha256>.bin     # each original PDF / image saved only once
        data/objects/ab/<sha256>.z # compressed notes/manifests saved only if changed
        data/snapshots/<UTC>-<id>.json   # immutable versioned manifest/pointers

A directory (and its marker file) is a *local* backup store, not a portable
single-file export. ``export_portable`` packs it into a standalone .pinbubackup
ZIP that can later be opened independently on another computer.

No Qt dependency. All untrusted paths and blob lengths are validated before
reconstructing a notebook. Snapshot manifests are committed only AFTER every
referenced blob has been written and made durable.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
import zlib
import unicodedata
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

FORMAT = 'pinbu-safe-backup'
FORMAT_VERSION = 1
BACKUP_MARKER = 'history.pinbubackup'
BACKUP_README = 'PLEASE READ - About Your Backups.txt'
BACKUP_README_TEXT = '''PINBU NOTE - ABOUT YOUR BACKUPS
================================

Hello! These files keep your notes, annotations, PDFs and earlier versions
recoverable if something goes wrong. Please leave this folder's contents
together, even when their names look a little strange. :)

What's inside:
  history.pinbubackup   - identifies this backup history
  assets/               - shared PDFs, images and other source files
  data/                 - snapshot records, notes and references to assets

PLEASE DO NOT rename, move or delete individual files inside this folder.
They depend on each other; removing one might make past versions impossible
to restore. The folder's readable name is not the notebook's identity.

To restore: Pinbu Note > File > Restore From Backup...
Select the history.pinbubackup file and choose a snapshot.

To move your backups between computers, use Pinbu Note's
File > Export Portable Backup... instead of copying only the index file.

Thanks for keeping your notes safe!
'''
MAX_ASSET_BYTES = 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024 * 1024
MAX_FILES = 200_000
MAX_JSON_BYTES = 32 * 1024 * 1024
CHUNK = 1024 * 1024
SHA = re.compile(r'^[0-9a-f]{64}$')
SAFE_UUID = re.compile(r'^[0-9a-f]{32}$')

class BackupFormatError(ValueError):
    pass


def _json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def _write_atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _safe_name(text: str):
    """Readable folder names with conservative Windows/macOS/Linux rules."""
    cleaned = unicodedata.normalize('NFC', str(text))
    cleaned = re.sub(r'[^\w .()\-]', '_', cleaned, flags=re.UNICODE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ._')
    cleaned = (cleaned[:65].rstrip(' .') or 'Notebook')
    # Windows reserves these names even with a filename extension.
    stem = cleaned.split('.', 1)[0].upper()
    if stem in {'CON', 'PRN', 'AUX', 'NUL'} | {
            f'{device}{number}' for device in ('COM', 'LPT') for number in range(1, 10)}:
        cleaned = '_' + cleaned
    return cleaned


def _readme_once(root: Path):
    """Never overwrite the user's annotations to the explanatory text file."""
    readme = root / BACKUP_README
    if readme.is_symlink():
        raise BackupFormatError('Unsafe backup guidance file (symlink).')
    try:
        with readme.open('x', encoding='utf-8', newline='\n') as f:
            f.write(BACKUP_README_TEXT)
            f.flush()
            os.fsync(f.fileno())
    except FileExistsError:
        pass


def _readable_path(base: Path, title: str):
    """Allocate a human-readable folder; avoid case-only duplicates on Windows."""
    title = _safe_name(title)
    occupied = {unicodedata.normalize('NFC', path.name).casefold()
                for path in base.iterdir()} if base.exists() else set()
    for number in range(1, 100_001):
        label = title if number == 1 else f'{title} ({number})'
        if label.casefold() not in occupied:
            return base / label
    raise BackupFormatError('Too many folders with the same project name.')


def _existing_projects(base: Path):
    """Identify projects by their index, never by the directory name."""
    if not base.exists():
        return
    for folder in base.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        marker_file = folder / BACKUP_MARKER
        if not marker_file.exists() and not marker_file.is_symlink():
            continue
        try:
            yield folder, _verify_marker(folder)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            # A broken index must not be overwritten or silently repaired.
            # Another project can still back up safely into a new directory.
            logging.warning('Skipping damaged backup index %s: %s', marker_file, exc)


def _migrate_old_folder(root: Path, base: Path, notebook_id: str, title: str):
    """Rename legacy long-ID folders, retaining every asset/snapshot byte.

    Only migrate directories whose index was already checked and whose name
    ends with the precise legacy UUID convention. If a rename is unavailable
    (e.g. an older process still has a file open), continue using the old
    folder rather than risk copying or losing any history.
    """
    if not root.name.endswith('--' + notebook_id):
        return root
    target = _readable_path(base, title)
    try:
        # Directory rename is within the same parent/filesystem; don't merge.
        root.rename(target)
    except OSError as exc:
        logging.warning('Backup folder migration deferred for %s: %s', root, exc)
        return root
    return target


def _read_json(path: Path, maximum=MAX_JSON_BYTES):
    if path.stat().st_size > maximum:
        raise BackupFormatError('Backup metadata exceeds the safety limit.')
    return json.loads(path.read_text(encoding='utf-8'))


def _trusted_relative(name: str, tab_ids: set):
    # Delegate to the same restrictive extraction rules as .pinbunote.
    from .notebook import _safe_relative
    return _safe_relative(name, tab_ids)


def _blob_path(root: Path, digest: str, is_metadata: bool):
    if not SHA.fullmatch(digest):
        raise BackupFormatError('Invalid backup object digest.')
    if is_metadata:
        return root / 'data' / 'objects' / digest[:2] / (digest + '.z')
    return root / 'assets' / digest[:2] / (digest + '.bin')


def _verify_marker(root: Path):
    path = root / BACKUP_MARKER
    if root.is_symlink() or path.is_symlink():
        raise BackupFormatError('Backup project index must not be a symlink.')
    marker = _read_json(path)
    if (not isinstance(marker, dict) or marker.get('format') != FORMAT
            or marker.get('version') != FORMAT_VERSION
            or not SAFE_UUID.fullmatch(str(marker.get('notebook_id', '')))):
        raise BackupFormatError('Not a supported Pinbu project backup.')
    return marker


def project_folder(base: Path, notebook_id: str, notebook_name: str, source_key=None):
    """Locate a project by its *internal* ID and source, regardless of folder name.

    Multiple copies of a notebook may share a UUID, but different source paths
    must never be merged into one backup history.
    """
    if not SAFE_UUID.fullmatch(str(notebook_id)):
        raise ValueError('Invalid notebook identity for backup.')
    if source_key is not None and not re.fullmatch(r'[0-9a-f]{12}', str(source_key)):
        raise ValueError('Invalid backup source fingerprint.')
    base = Path(base).expanduser().resolve()
    matches = [(folder, marker) for folder, marker in _existing_projects(base)
               if marker['notebook_id'] == notebook_id]
    exact = [folder for folder, marker in matches
             if marker.get('source_key') == source_key]
    if len(exact) > 1:
        raise BackupFormatError('Duplicate backup histories for the same notebook/source. '
                                'Please reconcile them before creating a new snapshot.')
    if exact:
        return exact[0]
    if source_key is None:
        if len(matches) == 1:
            return matches[0][0]
        if len(matches) > 1:
            raise BackupFormatError('Multiple backup histories use this notebook ID. '
                                    'Specify the original file to choose the correct one.')
    return _readable_path(base, notebook_name)


def _initialize(base: Path, notebook_id: str, notebook_name: str, app_version: str, source_key):
    base = Path(base).expanduser().resolve()
    root = project_folder(base, notebook_id, notebook_name, source_key)
    if (root / BACKUP_MARKER).is_file():
        marker = _verify_marker(root)
        if (marker['notebook_id'] != notebook_id
                or marker.get('source_key') != source_key):
            raise BackupFormatError('Backup folder belongs to a different notebook/source.')
        root = _migrate_old_folder(root, base, notebook_id, notebook_name)
    else:
        # Reserve the new directory exclusively, never reuse a preexisting one.
        # A collision from another process must fail safely, not mix histories.
        try:
            root.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise BackupFormatError('Backup project folder was created concurrently; '
                                    'please retry the backup.') from exc
        marker = dict(format=FORMAT, version=FORMAT_VERSION,
                      notebook_id=notebook_id, notebook_name=notebook_name,
                      source_key=source_key, created_by=app_version,
                      created_at=datetime.now(timezone.utc).isoformat())
        _write_atomic(root / BACKUP_MARKER, _json_bytes(marker))
    (root / 'assets').mkdir(exist_ok=True)
    (root / 'data' / 'objects').mkdir(parents=True, exist_ok=True)
    (root / 'data' / 'snapshots').mkdir(parents=True, exist_ok=True)
    _readme_once(root)
    return root


def _store_db_file(root: Path, blob, size: int, metadata: bool):
    """Stream untrusted SQLite BLOBs; don't load large PDFs into memory."""
    if not 0 <= size <= MAX_ASSET_BYTES or len(blob) != size:
        raise BackupFormatError('Invalid notebook file length.')
    hashed = hashlib.sha256()
    with tempfile.TemporaryFile() as tmp:
        if metadata:
            if size > MAX_JSON_BYTES:
                raise BackupFormatError('Metadata entry too large.')
            # JSON is usually highly compressible. Reuse identical content.
            compressor = zlib.compressobj(level=6)
        copied = 0
        while copied < size:
            chunk = blob.read(min(CHUNK, size - copied))
            if not chunk:
                raise BackupFormatError('Notebook asset truncated while backing up.')
            hashed.update(chunk)
            tmp.write(compressor.compress(chunk) if metadata else chunk)
            copied += len(chunk)
        if metadata:
            tmp.write(compressor.flush())
        digest = hashed.hexdigest()
        path = _blob_path(root, digest, metadata)
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
            try:
                tmp.seek(0)
                with temp.open('xb') as output:
                    shutil.copyfileobj(tmp, output, CHUNK)
                    output.flush()
                    os.fsync(output.fileno())
                # A racing duplicate writer should not replace existing content.
                if path.is_file():
                    temp.unlink(missing_ok=True)
                else:
                    os.replace(temp, path)
            finally:
                temp.unlink(missing_ok=True)
    return digest


@contextmanager
def _archive_root(path: Path):
    """Interpret a local project index or a portable .pinbubackup ZIP."""
    path = Path(path).expanduser().resolve()
    if path.is_file() and path.name != BACKUP_MARKER and path.suffix == '.pinbubackup':
        with tempfile.TemporaryDirectory(prefix='pinbu-backup-restore-') as scratch:
            root = Path(scratch)
            with zipfile.ZipFile(path, 'r') as z:
                items = z.infolist()
                if len(items) > 2 * MAX_FILES:
                    raise BackupFormatError('Too many entries in portable backup.')
                if sum(i.file_size for i in items) > MAX_TOTAL_BYTES:
                    raise BackupFormatError('Portable backup extraction would exceed safety limits.')
                for item in items:
                    rel = Path(item.filename)
                    if (rel.is_absolute() or '\\' in item.filename
                            or not rel.parts or any(x in ('.', '..') for x in rel.parts)
                            or rel.parts[0] not in ('assets', 'data', BACKUP_MARKER, BACKUP_README)
                            or (rel.parts[0] in (BACKUP_MARKER, BACKUP_README)
                                and len(rel.parts) != 1)):
                        raise BackupFormatError('Unsafe path in portable backup.')
                    if (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise BackupFormatError('Portable backup contains a symlink.')
                    dest = root.joinpath(*rel.parts)
                    if item.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                        continue
                    if dest.exists():
                        raise BackupFormatError('Duplicate backup archive entry.')
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(item) as source, dest.open('xb') as target:
                        shutil.copyfileobj(source, target, CHUNK)
            _verify_marker(root)
            yield root
    else:
        root = _resolve_archive(path)
        _verify_marker(root)
        yield root


def _snapshots_from_root(root: Path):
    """List a previously validated, extracted project backup."""
    snapshots = []
    for path in sorted((root / 'data' / 'snapshots').glob('*.json'), reverse=True):
        try:
            data = _read_json(path)
            if data.get('format') != FORMAT or data.get('version') != FORMAT_VERSION:
                continue
            snapshots.append(dict(id=path.stem, timestamp=data['timestamp'],
                                  reason=data.get('reason', 'automatic'),
                                  app_version=data.get('app_version', 'unknown'),
                                  file_count=len(data['files'])))
        except (ValueError, OSError, KeyError, TypeError):
            continue
    return snapshots


def list_snapshots(marker_path: Path):
    with _archive_root(marker_path) as root:
        return _snapshots_from_root(root)


def _resolve_archive(path: Path):
    path = Path(path).expanduser().resolve()
    if path.is_dir():
        return path
    if path.name == BACKUP_MARKER:
        return path.parent
    raise BackupFormatError('Select a project backup folder or its history.pinbubackup index.')


def create_snapshot(notebook_path: Path, backup_base: Path, *, force=False, reason='automatic',
                    logical_source=None, allow_newer_app=False, strict_assets=False,
                    source_time=None, migration_key=None):
    """Create an immutable version and reuse unchanged PDFs and other assets.

    Input must be a fully committed notebook (use Notebook.save first).
    Returns the snapshot path and project folder. Never mutates the notebook.
    """
    from .notebook import Notebook, MAX_LOADED_FILES, MAX_LOADED_BYTES, read_bounded_manifest
    from . import __version__
    notebook_path = Path(notebook_path).expanduser().resolve()
    uri = notebook_path.as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        conn.execute('BEGIN')  # stable read transaction across all file rows
        try:
            manifest = read_bounded_manifest(conn)
        except ValueError as exc:
            raise BackupFormatError('Notebook has an invalid or oversized manifest.') from exc
        Notebook._check_manifest(manifest, allow_newer_app=allow_newer_app)
        file_count, declared_total, actual_total = conn.execute(
            'SELECT COUNT(*), COALESCE(SUM(size),0), COALESCE(SUM(LENGTH(data)),0) FROM files').fetchone()
        if (file_count < 0 or file_count > MAX_LOADED_FILES
                or declared_total < 0 or declared_total > MAX_LOADED_BYTES
                or declared_total != actual_total):
            raise BackupFormatError('Notebook file inventory failed validation.')
        source_path = Path(logical_source or notebook_path).expanduser().resolve()
        source_key = hashlib.sha256(str(source_path).encode('utf-8')).hexdigest()[:12]
        root = _initialize(backup_base, manifest['id'], manifest['name'], __version__, source_key)
        snapshots_dir = root / 'data' / 'snapshots'
        # Importing the same old snapshot again must not multiply history.
        # This check does not delete or rewrite any legacy source.
        if migration_key is not None:
            if not re.fullmatch(r'[0-9a-f]{64}', migration_key):
                raise BackupFormatError('Invalid migration identity.')
            for existing in snapshots_dir.glob('*.json'):
                prior = _read_json(existing)
                if prior.get('migration_key') == migration_key:
                    return None, root
        # Deduplicate snapshot state as well; forced close events remain distinct
        # even if their content is identical.
        entries = {}
        ids = {t['id'] for t in manifest['tabs']}
        latest = _snapshots_from_root(root)
        prior_files = {}
        if latest:
            previous = _read_json(snapshots_dir / (latest[0]['id'] + '.json'))
            prior_files = previous.get('files', {})
        for rowid, relative, size, mtime_ns in conn.execute(
                'SELECT rowid, path, size, mtime_ns FROM files ORDER BY path'):
            _trusted_relative(relative, ids)
            is_metadata = relative.endswith('.json')
            previous_item = prior_files.get(relative, {})
            # Reuse an unchanged large PDF without even re-reading it.
            # Metadata is small and always hashed to detect same-timestamp edits.
            can_reuse = (not strict_assets and not is_metadata and
                         previous_item.get('size') == size and
                         previous_item.get('mtime_ns') == mtime_ns and
                         previous_item.get('kind') == 'asset' and
                         _blob_path(root, str(previous_item.get('sha256', '')), False).is_file()
                         if SHA.fullmatch(str(previous_item.get('sha256', ''))) else False)
            if can_reuse:
                digest = previous_item['sha256']
            else:
                with conn.blobopen('files', 'data', rowid, readonly=True) as blob:
                    digest = _store_db_file(root, blob, size, is_metadata)
            entries[relative] = {'sha256': digest, 'size': size,
                                 'mtime_ns': mtime_ns,
                                 'kind': 'data' if is_metadata else 'asset'}
        state = {'manifest': manifest, 'files': entries}
        state_digest = hashlib.sha256(_json_bytes(state)).hexdigest()
        if latest and not force:
            previous = _read_json(snapshots_dir / (latest[0]['id'] + '.json'))
            if previous.get('state_sha256') == state_digest:
                return None, root
        snap_time = source_time or datetime.now(timezone.utc)
        if snap_time.tzinfo is None:
            raise ValueError('Backup timestamp needs a UTC offset.')
        snap_time = snap_time.astimezone(timezone.utc)
        snap_id = snap_time.strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:10]
        snapshot = dict(format=FORMAT, version=FORMAT_VERSION,
                        id=snap_id, timestamp=snap_time.isoformat(),
                        reason=reason,
                        app_version=(manifest.get('app_version', __version__)
                                     if migration_key else __version__),
                        notebook_version=manifest['version'],
                        state_sha256=state_digest, **state)
        if migration_key:
            snapshot['migration_key'] = migration_key
            snapshot['imported_by'] = __version__
        output = snapshots_dir / (snap_id + '.json')
        _write_atomic(output, _json_bytes(snapshot))
        return output, root


def _copy_object(root: Path, item, destination_blob):
    digest = item.get('sha256')
    size = item.get('size')
    metadata = item.get('kind') == 'data'
    if (not isinstance(size, int) or not 0 <= size <= MAX_ASSET_BYTES
            or not SHA.fullmatch(str(digest))
            or item.get('kind') not in ('data', 'asset')):
        raise BackupFormatError('Malformed backup file descriptor.')
    path = _blob_path(root, digest, metadata)
    if not path.is_file() or path.is_symlink():
        raise BackupFormatError('Backup object is missing or unsafe.')
    hashed = hashlib.sha256()
    count = 0
    decompressor = zlib.decompressobj() if metadata else None
    with path.open('rb') as source:
        while True:
            buf = source.read(CHUNK)
            if not buf:
                break
            unpacked = decompressor.decompress(buf, max(0, size-count)+1) if metadata else buf
            count += len(unpacked)
            if count > size:
                raise BackupFormatError('Backup object expanded beyond its declared length.')
            hashed.update(unpacked)
            destination_blob.write(unpacked)
        if metadata:
            tail = decompressor.flush()
            count += len(tail)
            hashed.update(tail)
            destination_blob.write(tail)
            if not decompressor.eof or decompressor.unused_data:
                raise BackupFormatError('Damaged compressed metadata object.')
    if count != size or hashed.hexdigest() != digest:
        raise BackupFormatError('Backup asset failed integrity verification.')


def verify_snapshot(marker_path: Path, snapshot_id: str, *, allow_newer_app=False):
    """Read and hash-check EVERY object before a dangerous replace operation.

    The verified snapshot includes all page assets plus note and annotation JSON.
    This performs bounded streaming validation and does NOT open the notebook
    for editing. A newer *app* may have created it, but a newer incompatible
    *file format* remains rejected. The caller must still re-check the source
    filesystem signature before replacing a destination.
    """
    from .notebook import Notebook, MAX_LOADED_FILES, MAX_LOADED_BYTES

    class DiscardWriter:
        def write(self, chunk):
            return len(chunk)

    with _archive_root(marker_path) as root:
        marker = _verify_marker(root)
        path = root / 'data' / 'snapshots' / (snapshot_id + '.json')
        if not snapshot_id or not re.fullmatch(r'[0-9A-Za-z_-]+', snapshot_id):
            raise BackupFormatError('Invalid snapshot identifier.')
        snap = _read_json(path)
        if snap.get('format') != FORMAT or snap.get('version') != FORMAT_VERSION:
            raise BackupFormatError('Unsupported backup snapshot version.')
        expected = hashlib.sha256(_json_bytes({
            'manifest': snap['manifest'], 'files': snap['files']})).hexdigest()
        if snap.get('state_sha256') != expected:
            raise BackupFormatError('Backup snapshot manifest checksum mismatch.')
        manifest = snap['manifest']
        Notebook._check_manifest(manifest, allow_newer_app=allow_newer_app)
        if marker['notebook_id'] != manifest['id']:
            raise BackupFormatError('Snapshot does not belong to this project.')
        entries = snap['files']
        if not isinstance(entries, dict) or len(entries) > MAX_LOADED_FILES:
            raise BackupFormatError('Invalid backup inventory.')
        total = 0
        ids = {t['id'] for t in manifest['tabs']}
        sink = DiscardWriter()
        for relative, entry in entries.items():
            _trusted_relative(relative, ids)
            if not isinstance(entry, dict):
                raise BackupFormatError('Invalid backup object.')
            size = entry.get('size')
            if type(size) is not int or not 0 <= size <= MAX_ASSET_BYTES:
                raise BackupFormatError('Invalid backup object size.')
            total += size
            if total > MAX_LOADED_BYTES:
                raise BackupFormatError('Backup exceeds the notebook safety limit.')
            if not isinstance(entry.get('mtime_ns'), int) or not 0 <= entry['mtime_ns'] < 2**63:
                raise BackupFormatError('Invalid backup timestamp.')
            if size:
                _copy_object(root, entry, sink)
            elif (entry.get('sha256') != hashlib.sha256(b'').hexdigest()
                  or not _blob_path(root, entry['sha256'],
                                    entry.get('kind') == 'data').is_file()):
                raise BackupFormatError('Missing or invalid zero-length asset.')

        # A hash-perfect archive of a BROKEN notebook is not sufficient as a
        # pre-overwrite recovery guarantee. Verify all live page references:
        # the old notebook's metadata must still point at real stored assets.
        for tab in manifest['tabs']:
            key = f"tabs/{tab['id']}/project.json"
            meta_entry = entries.get(key)
            if (not isinstance(meta_entry, dict)
                    or meta_entry.get('kind') != 'data'
                    or meta_entry.get('size', MAX_JSON_BYTES+1) > MAX_JSON_BYTES):
                raise BackupFormatError('Backup is missing tab project metadata.')
            path = _blob_path(root, meta_entry['sha256'], True)
            with path.open('rb') as source:
                compressed = source.read(MAX_JSON_BYTES + 1)
            if len(compressed) > MAX_JSON_BYTES:
                raise BackupFormatError('Project metadata is too large.')
            decoder = zlib.decompressobj()
            raw = decoder.decompress(compressed, MAX_JSON_BYTES + 1)
            raw += decoder.flush()
            if (not decoder.eof or decoder.unused_data
                    or len(raw) != meta_entry['size']):
                raise BackupFormatError('Broken project metadata in backup.')
            project = json.loads(raw)
            pages = project.get('pages') if isinstance(project, dict) else None
            if not isinstance(pages, list):
                raise BackupFormatError('Backup project contains invalid pages.')
            for page in pages:
                if not isinstance(page, dict):
                    raise BackupFormatError('Backup contains invalid page data.')
                for field in ('source', 'render_source', 'file'):
                    relative = page.get(field)
                    if relative:
                        if not isinstance(relative, str):
                            raise BackupFormatError('Invalid page source reference.')
                        full = f"tabs/{tab['id']}/{relative}"
                        _trusted_relative(full, ids)
                        if full not in entries:
                            raise BackupFormatError(
                                f'Cannot safely overwrite: the pre-overwrite '
                                f'backup is missing a page asset ({relative}).')
        return True


def restore_snapshot(marker_path: Path, destination: Path, *, snapshot_id=None):
    """Recreate a complete independent .pinbunote in a *new* destination."""
    with _archive_root(marker_path) as root:
        return _restore_from_root(root, destination, snapshot_id=snapshot_id)


def _restore_from_root(root: Path, destination: Path, *, snapshot_id=None):
    from .notebook import Notebook, MAX_LOADED_FILES, MAX_LOADED_BYTES
    snapshots = _snapshots_from_root(root)
    if not snapshots:
        raise BackupFormatError('There are no valid backup snapshots.')
    selection = snapshot_id or snapshots[0]['id']
    if selection not in {x['id'] for x in snapshots}:
        raise BackupFormatError('The selected snapshot was not found.')
    snapshot = _read_json(root / 'data' / 'snapshots' / (selection + '.json'))
    if snapshot.get('format') != FORMAT or snapshot.get('version') != FORMAT_VERSION:
        raise BackupFormatError('Unsupported backup snapshot version.')
    if snapshot.get('state_sha256') != hashlib.sha256(_json_bytes({
            'manifest': snapshot['manifest'], 'files': snapshot['files']})).hexdigest():
        raise BackupFormatError('Backup snapshot manifest checksum mismatch.')
    manifest = snapshot['manifest']
    Notebook._check_manifest(manifest)
    ids = {t['id'] for t in manifest['tabs']}
    entries = snapshot['files']
    if (not isinstance(entries, dict) or len(entries) > MAX_LOADED_FILES or
            sum(int(x.get('size', -1)) for x in entries.values()) > MAX_LOADED_BYTES):
        raise BackupFormatError('Backup snapshot inventory exceeds limits.')
    for relative in entries:
        _trusted_relative(relative, ids)
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise FileExistsError('Restore requires a new, unused notebook path.')
    if destination.suffix.lower() != '.pinbunote':
        raise ValueError('Restore a .pinbunote notebook.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with closing(sqlite3.connect(temp)) as conn:
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            conn.execute('CREATE TABLE files (path TEXT PRIMARY KEY, data BLOB NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL)')
            # Restored notebooks have their own identity and independent backups.
            manifest = dict(manifest)
            manifest['id'] = uuid.uuid4().hex
            manifest['name'] = destination.stem
            conn.execute('INSERT INTO meta(key,value) VALUES(?,?)', ('manifest', json.dumps(manifest, ensure_ascii=False, sort_keys=True)))
            for relative, item in entries.items():
                size = item['size']
                mtime_ns = item.get('mtime_ns', 0)
                if not isinstance(mtime_ns, int) or not 0 <= mtime_ns < 2**63:
                    raise BackupFormatError('Invalid backup object timestamp.')
                conn.execute('INSERT INTO files(path,data,size,mtime_ns) VALUES(?,zeroblob(?),?,?)',
                             (relative, size, size, mtime_ns))
                rowid = conn.execute('SELECT rowid FROM files WHERE path=?', (relative,)).fetchone()[0]
                if size:
                    with conn.blobopen('files', 'data', rowid) as blob:
                        _copy_object(root, item, blob)
                else:
                    if item['sha256'] != hashlib.sha256(b'').hexdigest():
                        raise BackupFormatError('Invalid empty asset digest.')
            conn.commit()
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise BackupFormatError('Restored notebook failed SQLite integrity check.')
        # Prevent clobbering if another process created the destination.
        with destination.open('xb') as output, temp.open('rb') as source:
            shutil.copyfileobj(source, output, CHUNK)
        test = Notebook.load(destination)
        test.close()
        return destination
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        temp.unlink(missing_ok=True)


def export_portable(marker_path: Path, destination: Path):
    """Portable self-contained ZIP; entries retain assets/data layout."""
    root = _resolve_archive(marker_path)
    _verify_marker(root)
    destination = Path(destination).expanduser().resolve()
    if destination.exists() or destination.suffix.lower() != '.pinbubackup':
        raise FileExistsError('Choose a new .pinbubackup archive filename.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name('.' + destination.name + '.tmp')
    try:
        with zipfile.ZipFile(temp, 'w', allowZip64=True) as z:
            for path in sorted(root.rglob('*')):
                if path.is_file():
                    if path.is_symlink():
                        raise BackupFormatError('Cannot export a symlink in backups.')
                    relative = path.relative_to(root).as_posix()
                    if '..' in Path(relative).parts:
                        raise BackupFormatError('Unsafe backup path.')
                    z.write(path, relative, compress_type=zipfile.ZIP_STORED)
        with destination.open('xb') as output, temp.open('rb') as source:
            shutil.copyfileobj(source, output, CHUNK)
        return destination
    finally:
        temp.unlink(missing_ok=True)


def prune_snapshots(marker_path: Path, max_snapshots: int = 100):
    """Discard old snapshot metadata and unreferenced objects, not live assets."""
    root = _resolve_archive(marker_path)
    snapshots = _snapshots_from_root(root)
    count = max(2, min(int(max_snapshots), 1000))
    if len(snapshots) <= count:
        return 0
    # Always keep the latest TWO independently restorable snapshots.
    old = snapshots[count:]
    preserved = snapshots[:count]
    referenced = set()
    for snap in preserved:
        data = _read_json(root / 'data' / 'snapshots' / (snap['id'] + '.json'))
        for item in data['files'].values():
            referenced.add((item['sha256'], item['kind']))
    for snap in old:
        (root / 'data' / 'snapshots' / (snap['id'] + '.json')).unlink()
    for category, top in (('data', root / 'data' / 'objects'),
                          ('asset', root / 'assets')):
        for path in top.glob('*/*'):
            digest = path.stem
            if (digest, category) not in referenced:
                path.unlink()
    return len(old)
