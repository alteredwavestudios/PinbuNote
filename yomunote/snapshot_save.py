"""Versioned, immutable-metadata SQLite saves for Yomu Note.

Only a GUI/main-thread caller may capture a notebook snapshot. The worker
receives plain bytes, paths and file identity; it never accesses a Qt object
or a mutable Notebook. SQLite connections are opened and closed on the
*worker* thread. Large page assets remain streamed in bounded chunks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import os
import sqlite3
import stat
import threading
from .notebook_lock import disk_signature, NotebookExternallyModifiedError
from contextlib import closing

CHUNK = 1024 * 1024
MAX_ASSET_BYTES = 1024 * 1024 * 1024
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_SNAPSHOT_JSON_BYTES = 96 * 1024 * 1024  # cap frozen metadata on 2 GB machines


class SnapshotTooLarge(RuntimeError):
    """Use the safe synchronous writer if a large notebook exceeds this cap."""




@dataclass
class SaveGuard:
    """Cross-thread ordering; never contains a SQLite connection."""
    lock: threading.RLock = field(default_factory=threading.RLock)
    generation: int = 0
    closed: bool = False
    disk_identity: tuple | None = None


@dataclass(frozen=True)
class FrozenFile:
    relative: str
    path: Path
    size: int
    mtime_ns: int
    device: int
    inode: int
    json_bytes: bytes | None = None
    digest: str | None = None


@dataclass(frozen=True)
class SaveSnapshot:
    """Immutable description of the data the user intended to save."""
    path: Path
    manifest: str
    files: tuple[FrozenFile, ...]
    saved_stats: dict
    saved_hashes: dict
    previous_manifest: str | None
    guard: SaveGuard
    generation: int
    workspace: Path


@dataclass(frozen=True)
class SaveResult:
    applied: bool
    changed: bool
    stats: dict
    hashes: dict
    manifest: str
    generation: int


def _unchanged_asset(path: Path, original: FrozenFile):
    """Refuse modified/replaced files rather than committing a torn PDF."""
    parent = path.parent
    workspace = original_workspace = None  # Parent guard below uses snapshot.workspace.
    fs = path.stat()
    if (not stat.S_ISREG(fs.st_mode) or fs.st_size != original.size
            or fs.st_mtime_ns != original.mtime_ns
            or fs.st_dev != original.device or fs.st_ino != original.inode):
        raise OSError(f'Page asset changed during background save: {original.relative}')


def _safe_asset(snapshot: SaveSnapshot, entry: FrozenFile):
    """Reject symlink swaps, including ancestor symlinks."""
    root = snapshot.workspace.resolve()
    path = entry.path
    if not path.resolve().is_relative_to(root):
        raise ValueError(f'Unsafe background-save file path: {entry.relative}')
    cursor = path
    while cursor != root and cursor.is_relative_to(root):
        if cursor.is_symlink():
            raise ValueError(f'Symlink swapped into notebook: {entry.relative}')
        cursor = cursor.parent
    _unchanged_asset(path, entry)


def write_snapshot(snapshot: SaveSnapshot) -> SaveResult:
    """Called on worker. A late snapshot cannot overwrite a newer save."""
    with snapshot.guard.lock:
        if snapshot.guard.closed or snapshot.guard.generation != snapshot.generation:
            return SaveResult(False, False, {}, {}, snapshot.manifest,
                              snapshot.guard.generation)
        if disk_signature(snapshot.path) != snapshot.guard.disk_identity:
            raise NotebookExternallyModifiedError(
                'The notebook changed on disk while it was open. Autosave was stopped '
                'to avoid overwriting edits from another version. Close the other '
                'application and recover from your backup before continuing.')
        changed = snapshot.manifest != snapshot.previous_manifest
        stats = dict(snapshot.saved_stats)
        hashes = dict(snapshot.saved_hashes)
        present = set()
        with closing(sqlite3.connect(snapshot.path)) as conn:
            conn.execute('PRAGMA synchronous=FULL')
            conn.execute('PRAGMA secure_delete=ON')
            with conn:
                conn.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                conn.execute('CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, data BLOB NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL)')
                for entry in snapshot.files:
                    present.add(entry.relative)
                    if entry.size < 0 or entry.size > MAX_ASSET_BYTES:
                        raise ValueError('A notebook asset exceeds the 1 GB safety limit.')
                    record = (entry.mtime_ns, entry.size)
                    if entry.json_bytes is not None:
                        if (entry.digest == snapshot.saved_hashes.get(entry.relative)
                                and entry.relative in snapshot.saved_stats):
                            stats[entry.relative] = record
                            continue
                        payload = entry.json_bytes
                        if len(payload) != entry.size or len(payload) > MAX_JSON_BYTES:
                            raise ValueError('Snapshot metadata size mismatch.')
                    else:
                        _safe_asset(snapshot, entry)
                        if record == snapshot.saved_stats.get(entry.relative):
                            continue
                        payload = None
                    size = entry.size
                    conn.execute('INSERT OR REPLACE INTO files(path,data,size,mtime_ns) '
                                 'VALUES(?,zeroblob(?),?,?)',
                                 (entry.relative, size, size, entry.mtime_ns))
                    row = conn.execute('SELECT rowid FROM files WHERE path=?',
                                       (entry.relative,)).fetchone()
                    if row is None:
                        raise OSError('Could not allocate SQLite snapshot entry.')
                    if size:
                        with conn.blobopen('files', 'data', row[0]) as blob:
                            if payload is not None:
                                blob.write(payload)
                            else:
                                # The path is constrained to the tab workspace and
                                # its file identity is verified before and after.
                                with entry.path.open('rb') as source:
                                    opened = os.fstat(source.fileno())
                                    if (opened.st_dev != entry.device
                                            or opened.st_ino != entry.inode
                                            or opened.st_size != entry.size):
                                        raise OSError('Source changed during background save.')
                                    remaining = size
                                    while remaining:
                                        chunk = source.read(min(CHUNK, remaining))
                                        if not chunk:
                                            raise OSError('Page asset truncated during save.')
                                        blob.write(chunk)
                                        remaining -= len(chunk)
                                    if source.read(1):
                                        raise OSError('Page asset grew during save.')
                                _safe_asset(snapshot, entry)
                    stats[entry.relative] = record
                    if payload is not None:
                        hashes[entry.relative] = entry.digest
                    changed = True
                for old in set(snapshot.saved_stats) - present:
                    conn.execute('DELETE FROM files WHERE path=?', (old,))
                    stats.pop(old, None)
                    hashes.pop(old, None)
                    changed = True
                if changed:
                    conn.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)',
                                 ('manifest', snapshot.manifest))
        snapshot.guard.disk_identity = disk_signature(snapshot.path)
        snapshot.guard.generation += 1
        return SaveResult(True, changed, stats, hashes, snapshot.manifest,
                          snapshot.guard.generation)
