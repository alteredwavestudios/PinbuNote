"""Protected Save Copy As replacement with independently verified recovery.

A notebook destination is never replaced until its *own* pre-overwrite snapshot
has been committed and every referenced object has been hash-verified. The
SQLite replacement is prepared separately. Unsupported future notebook formats
cannot be overwritten. A newer app release on a compatible format requires
an explicit, informed GUI confirmation before this module is called.

Filesystem signatures cannot implement distributed Dropbox compare-and-swap.
This module also uses Pinbu's machine-local origin lock, but cannot prevent
simultaneous cloud publishing on another unsynchronised device.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .notebook import (Notebook, NotebookNewerVersionError, NOTEBOOK_VERSION,
                       READABLE_NOTEBOOK_VERSIONS, MAGIC_FORMAT,
                       MAX_MANIFEST_BYTES, _version_sortkey, default_backup_folder,
                       read_bounded_manifest)
from .notebook_lock import NotebookLease, NotebookExternallyModifiedError, disk_signature
from .safe_backup import create_snapshot, verify_snapshot
from .safe_session import working_root


@dataclass(frozen=True)
class DestinationInfo:
    path: Path
    app_version: str
    format_version: int
    newer_application: bool


def read_destination_info(path: Path) -> DestinationInfo:
    """Inspect a non-symlink SQLite notebook, without opening it for writing.

    Checking a compatible future *app* version is allowed for the purpose of
    making a safety backup. Incompatible future *formats* are NEVER allowed.
    """
    path = Path(path).expanduser().absolute()
    if not path.is_file() or path.is_symlink():
        raise ValueError('The destination is not a regular notebook file.')
    if path.suffix.lower() not in ('.pinbunote', '.yomunote', '.yominote'):
        raise ValueError('Choose a Pinbu Note notebook destination.')
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
            data = read_bounded_manifest(db)
            if not isinstance(data, dict) or data.get('format') != MAGIC_FORMAT:
                raise ValueError('The destination is not a supported Pinbu notebook.')
            fmt = data.get('version')
            if fmt not in READABLE_NOTEBOOK_VERSIONS:
                raise NotebookNewerVersionError(
                    f'This notebook uses format v{fmt}; this build supports up to '
                    f'v{NOTEBOOK_VERSION}. The notebook must NOT be overwritten '
                    'by an older version. Update Pinbu Note or choose a new filename.')
            Notebook._check_manifest(data, allow_newer_app=True)
            # A corrupt original is not safe to replace until it can be backed up.
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Destination notebook failed SQLite integrity validation.')
    except sqlite3.DatabaseError as exc:
        raise ValueError('Could not safely inspect the destination notebook.') from exc
    current = _version_sortkey(__version__)
    saved = _version_sortkey(data.get('app_version'))
    version = str(data.get('app_version') or 'unknown')
    if version != 'unknown' and saved is None:
        raise NotebookNewerVersionError(
            'The destination has an unrecognised Pinbu version label. '
            'Choose a new filename or update Pinbu Note; its compatibility cannot be verified.')
    return DestinationInfo(path, version, fmt, bool(saved and current and saved > current))


def _local_origin_lock(path: Path) -> NotebookLease:
    """Match the local origin-lock identity of open_working_copy exactly."""
    resolved = path.expanduser().resolve()
    canonical = str(resolved).casefold() if sys.platform == 'win32' else str(resolved)
    key = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    local = working_root() / 'origin-locks' / (key + '.pinbunote')
    return NotebookLease(local).acquire()


def _ensure_no_sqlite_sidecars(destination: Path) -> None:
    # Replacing a live database while SQLite has outstanding WAL/journal state
    # could attach a previous session's transactions to the NEW file. Block it.
    for suffix in ('-wal', '-shm', '-journal'):
        sidecar = destination.with_name(destination.name + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            raise OSError('Cannot overwrite while the destination has an active '
                          'SQLite journal or WAL sidecar. Close other programs, '
                          'allow cloud sync to finish, and try again: ' + str(sidecar))


def save_copy_as(source: Path, destination: Path, *, backup_directory: Path | None = None,
                 allow_newer_application: bool = False,
                 protected_paths=()) -> tuple[Path, Path | None]:
    """Save an independent notebook, optionally replacing another safely.

    Return (destination, pre_overwrite_snapshot_or_None). GUI must prompt before
    calling with allow_newer_application=True and must offer Save As New Copy.
    A failed backup, verification, lock, copy or recheck preserves the target.
    """
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().absolute()
    if destination.is_symlink():
        raise ValueError('Refusing to replace a notebook through a symbolic link.')
    if destination.suffix.lower() not in ('.pinbunote', '.yomunote'):
        raise ValueError('Save copies as a .pinbunote or .yomunote notebook.')
    if source == destination.resolve() or any(
            destination.resolve() == Path(p).expanduser().resolve() for p in protected_paths if p):
        raise ValueError('Save Copy As cannot replace the currently open notebook. Use Save instead.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # For new filenames, Notebook.restore_copy uses open(..., 'xb'): never
    # replace a file created by another process after the Save dialog closed.
    if not destination.exists():
        return Notebook.restore_copy(source, destination), None

    lease = _local_origin_lock(destination)
    historical_lease = None
    snapshot = None
    temp = destination.with_name('.' + destination.stem + '.pinbu-copy-' +
                                 uuid.uuid4().hex + '.pinbunote')
    try:
        # Also respect historical Pinbu/Yomu builds that used an ADJACENT
        # lockfile. Probe only an already-existing lock: do not create a new
        # cloud-synchronised .lock just for Save Copy As.
        legacy_lock = destination.with_name(destination.name + '.lock')
        if legacy_lock.is_file() and not legacy_lock.is_symlink():
            historical_lease = NotebookLease(destination).acquire()
        _ensure_no_sqlite_sidecars(destination)
        # Read the destination version while holding the same local lock used
        # for GUI-opened notebooks. Do not create a cloud-synchronised lockfile.
        signature = disk_signature(destination)
        info = read_destination_info(destination)
        if info.newer_application and not allow_newer_application:
            raise NotebookNewerVersionError(
                f'This file was saved with newer Pinbu Note v{info.app_version}. '
                'We STRONGLY recommend saving a new copy instead of overwriting it. '
                'The original has not been changed.')
        if disk_signature(destination) != signature:
            raise NotebookExternallyModifiedError(
                'Destination changed during compatibility inspection. No overwrite was attempted.')

        # The PRE-OVERWRITE snapshot belongs to the EXISTING destination
        # notebook's own project ID/source-key history, not the current source.
        snapshot, root = create_snapshot(
            destination, Path(backup_directory or default_backup_folder()),
            force=True, reason='pre-overwrite', logical_source=destination,
            allow_newer_app=True, strict_assets=True)
        if snapshot is None or not snapshot.exists():
            raise IOError('Could not commit a pre-overwrite backup. The original is untouched.')
        verify_snapshot(root, snapshot.stem, allow_newer_app=True)
        if disk_signature(destination) != signature:
            raise NotebookExternallyModifiedError(
                'Destination changed while making its backup. No overwrite was attempted.')

        # Build the *new* notebook fully independently first; restore_copy
        # assigns a fresh project identity and refuses existing output paths.
        Notebook.restore_copy(source, temp)
        with temp.open('r+b') as fh:
            os.fsync(fh.fileno())  # writable descriptor required on Windows
        with closing(sqlite3.connect(temp.as_uri() + '?mode=ro', uri=True)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise IOError('Replacement notebook failed integrity verification.')
        # Last-moment guard cannot be atomic on Dropbox, but catches ordinary
        # local or already-synchronised changes; the verified backup survives.
        if disk_signature(destination) != signature:
            raise NotebookExternallyModifiedError(
                'Destination changed while preparing replacement. Original preserved.')
        _ensure_no_sqlite_sidecars(destination)
        os.replace(temp, destination)
        return destination, snapshot
    finally:
        temp.unlink(missing_ok=True)
        if historical_lease is not None:
            historical_lease.release()
        lease.release()
