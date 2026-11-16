"""Local-only notebook working copies and explicit checked publishing.

Only the *published* path is synced with Dropbox/OneDrive. Routine autosave
always targets an independent SQLite database in application local data.

IMPORTANT: ordinary filesystem signatures are not distributed compare-and-swap.
Cross-device simultaneous publishing can still race; caller must display this
limitation. Never silently republish after a conflict.
"""
from __future__ import annotations

import json
import hashlib
import os
import shutil
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .notebook_lock import NotebookLease, NotebookExternallyModifiedError, disk_signature


def working_root():
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        return Path(base) / 'Pinbu Note' / 'WorkingCopies'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Pinbu Note' / 'WorkingCopies'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'Pinbu Note' / 'WorkingCopies'


def _write_descriptor(notebook):
    if not getattr(notebook, '_session_dir', None):
        return
    target = notebook._session_dir / 'session.json'
    data = {'format': 'pinbu-local-working-session', 'version': 1,
            'original': str(notebook._origin_path), 'working': str(notebook.path),
            'notebook_id': notebook.identifier, 'opened_at': notebook._session_opened_at,
            'app_version': notebook._session_app_version,
            'unpublished': bool(notebook._unpublished),
            'backup_verified': bool(getattr(notebook, '_session_backed_up', False)),
            # The marker is persisted with each local save. If Python is killed
            # or the machine loses power, it remains 'active'. Normal close
            # explicitly changes it to 'closed' after the verified backup.
            'status': getattr(notebook, '_session_status', 'active') or 'active'}
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, target)


def open_working_copy(source: Path, base: Path | None = None):
    """Safely copy one complete SQLite transaction into private local storage."""
    from .notebook import Notebook
    from . import __version__
    source = Path(source).expanduser().resolve()
    if not source.is_file() or source.is_symlink():
        raise ValueError('Choose an existing, ordinary notebook file.')
    # Lock ONLY in app-local storage. An adjacent .lock beside the Dropbox
    # source would itself be cloud-synchronised but provide no distributed lock.
    canonical = str(source).casefold() if sys.platform == 'win32' else str(source)
    lock_key = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    local_lock_name = working_root() / 'origin-locks' / (lock_key + '.pinbunote')
    lease = NotebookLease(local_lock_name).acquire()
    directory = None
    try:
        baseline = disk_signature(source)
        if baseline is None:
            raise FileNotFoundError(source)
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as orig:
            row = orig.execute("SELECT value FROM meta WHERE key='manifest'").fetchone()
            if not row:
                raise ValueError('Notebook has no manifest.')
            meta = json.loads(row[0])
            Notebook._check_manifest(meta)
            directory = Path(base or working_root()) / meta['id'] / uuid.uuid4().hex
            directory.mkdir(parents=True, exist_ok=False)
            local_file = directory / (source.stem + '.pinbunote')
            with closing(sqlite3.connect(local_file)) as dest:
                orig.backup(dest)
        if disk_signature(source) != baseline:
            raise NotebookExternallyModifiedError(
                'The original notebook changed while it was being copied. '
                'No editable session was opened; let cloud syncing finish.')
        notebook = Notebook.load(local_file)
        # Do not count an *application-only* version update as a user edit.
        # If the original was last saved by a previous release, stage our
        # informational app_version field ONLY in the private local DB. Its
        # byte-for-byte external original is unchanged until a real edit and
        # explicit Save. Otherwise the first Close in every update would show
        # an erroneous 'unpublished changes' dialog.
        with notebook._save_guard.lock:
            with closing(sqlite3.connect(local_file)) as local_db:
                row = local_db.execute(
                    "SELECT value FROM meta WHERE key='manifest'").fetchone()
                staged_manifest = json.loads(row[0])
                if staged_manifest.get('app_version') != __version__:
                    staged_manifest['app_version'] = __version__
                    serial = json.dumps(staged_manifest, ensure_ascii=False,
                                        sort_keys=True)
                    with local_db:
                        local_db.execute(
                            "UPDATE meta SET value=? WHERE key='manifest'", (serial,))
                    notebook._saved_manifest = serial
                    notebook._save_guard.disk_identity = disk_signature(local_file)
        notebook._origin_path = source
        notebook._origin_lease = lease
        notebook._origin_signature = baseline
        notebook._session_dir = directory
        notebook._session_opened_at = datetime.now(timezone.utc).isoformat()
        notebook._session_app_version = __version__
        notebook._session_backed_up = False
        notebook._session_status = 'active'
        notebook._unpublished = False
        _write_descriptor(notebook)
        return notebook
    except BaseException:
        lease.release()
        if directory is not None and directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
        raise


def publish(notebook):
    """Explicitly publish a validated snapshot only if original is unchanged."""
    if not getattr(notebook, '_origin_path', None):
        notebook.save()
        return notebook.path
    notebook.save()  # local SQLite always first
    origin = notebook._origin_path
    current = disk_signature(origin)
    if current != notebook._origin_signature:
        # A newer app on another device must be reported as a VERSION problem,
        # not a generic timestamp conflict. Never overwrite in either case.
        from .safe_overwrite import read_destination_info
        from .notebook import NotebookNewerVersionError
        if current is not None:
            info = read_destination_info(origin)
            if info.newer_application:
                raise NotebookNewerVersionError(
                    f'The original notebook was saved by newer Pinbu Note '
                    f'v{info.app_version}. This older version must not publish '
                    'over it. We strongly recommend UPGRADING Pinbu Note, or '
                    'using Save Copy As to create a separate file. Your local '
                    'autosaves and backups are preserved.')
        raise NotebookExternallyModifiedError(
            'Original notebook changed on another device. Publishing is blocked. '
            'Your edits remain saved in the local working copy and backup history. '
            'Use Save Copy As to avoid replacing either version.')
    if not notebook._unpublished:
        # No change since the last publish: avoid rewriting a huge PDF-backed
        # SQLite file and making Dropbox re-upload identical material.
        return origin
    temporary = origin.with_name('.' + origin.name + '.pinbu-publish-' + uuid.uuid4().hex + '.tmp')
    try:
        with closing(sqlite3.connect(notebook.path.as_uri() + '?mode=ro', uri=True)) as source:
            with closing(sqlite3.connect(temporary)) as dest:
                dest.execute('PRAGMA synchronous=FULL')
                source.backup(dest)
                if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise IOError('Published notebook failed SQLite integrity verification.')
        # Windows os.fsync() uses CRT _commit(), which requires a writable
        # descriptor.  Opening the completed temporary SQLite copy with 'rb'
        # raises [Errno 9] Bad file descriptor on Windows when publishing.
        # 'r+b' does not modify its bytes; it permits the durability flush.
        with temporary.open('r+b') as fh:
            os.fsync(fh.fileno())
        # Last-moment guard. This reduces, but cannot eliminate, cross-device races.
        if disk_signature(origin) != notebook._origin_signature:
            raise NotebookExternallyModifiedError(
                'The original notebook changed while preparing the save. '
                'Publishing was blocked and your local copy was preserved.')
        os.replace(temporary, origin)
        notebook._origin_signature = disk_signature(origin)
        notebook._unpublished = False
        _write_descriptor(notebook)
        return origin
    finally:
        temporary.unlink(missing_ok=True)


def recoverable_sessions(base: Path | None = None):
    """List durable local working copies after a crash or unpublished close."""
    root = Path(base or working_root())
    if not root.exists():
        return []
    found = []
    for descriptor in root.glob('*/*/session.json'):
        try:
            data = json.loads(descriptor.read_text(encoding='utf-8'))
            file = Path(data.get('working', ''))
            if (data.get('format') == 'pinbu-local-working-session'
                    and file.is_file() and not file.is_symlink()
                    and file.parent.resolve() == descriptor.parent.resolve()):
                found.append(data)
        except (OSError, ValueError, TypeError):
            continue
    return found


def mark_normal_close(notebook):
    """Mark a verified session as intentionally closed (even if unpublished).

    This is deliberately separate from publishing to the original file. A
    normal 'Close Without Saving' still keeps its recoverable working copy.
    """
    if not getattr(notebook, '_session_dir', None):
        return
    notebook._session_status = 'closed'
    try:
        _write_descriptor(notebook)
    except BaseException:
        notebook._session_status = 'active'
        raise


def interrupted_sessions(base: Path | None = None):
    """Only abandoned, unlocked ACTIVE sessions warrant a startup prompt.

    Previous builds had no reliable close marker: their sessions remain in the
    manual Recovery Centre, but cannot reliably be classified as crashes.
    """
    found = []
    for record in recoverable_sessions(base):
        if record.get('status') != 'active':
            continue
        path = Path(record['working'])
        try:
            # An active Pinbu process holds this lock; do NOT report it as a
            # crash just because another window was opened on this machine.
            lease = NotebookLease(path).acquire()
        except (OSError, RuntimeError):
            continue
        else:
            lease.release()
            found.append(record)
    return sorted(found, key=lambda x: Path(x['working']).stat().st_mtime_ns,
                  reverse=True)


def acknowledge_interrupted_session(record):
    """Stop repeat startup prompts without deleting a recoverable copy."""
    path = Path(record['working'])
    descriptor = path.parent / 'session.json'
    if not path.is_file() or not descriptor.is_file():
        return False
    lease = NotebookLease(path).acquire()
    try:
        data = json.loads(descriptor.read_text(encoding='utf-8'))
        if data.get('status') != 'active' or data.get('working') != str(path):
            return False
        data['status'] = 'interrupted'  # Still shown in manual recovery menu.
        data['recovery_acknowledged'] = datetime.now(timezone.utc).isoformat()
        temp = descriptor.with_name('session.' + uuid.uuid4().hex + '.tmp')
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, descriptor)
        finally:
            temp.unlink(missing_ok=True)
        return True
    finally:
        lease.release()


def cleanup_fully_published_sessions(base: Path | None = None):
    """Prune only unmodified, backed-up, unlocked stale local working copies.

    Any uncertain, unpublished or unsnapshotted session is retained.
    This can be called at the next application startup, not from a Qt worker.
    """
    removed = 0
    root = Path(base or working_root())
    if not root.is_dir():
        return 0
    for item in recoverable_sessions(root):
        # Never discard a session abandoned by a crash before the user has
        # been offered recovery, even if its last backup was verified.
        if item.get('status') != 'closed':
            continue
        if item.get('unpublished') or not item.get('backup_verified'):
            continue
        target = Path(item['working'])
        if not target.is_file() or not target.parent.is_relative_to(root.resolve()):
            continue
        try:
            lease = NotebookLease(target).acquire()
        except Exception:
            continue  # another running process may still be using it
        try:
            directory = target.parent
            # Do not remove unexpected extra user files in the session folder.
            allowed = {target.name, target.name + '.lock', 'session.json'}
            if all(p.name in allowed for p in directory.iterdir()):
                shutil.rmtree(directory, ignore_errors=True)
                removed += 1
        finally:
            lease.release()
    return removed
