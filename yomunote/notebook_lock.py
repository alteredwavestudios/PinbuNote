"""Cross-process single-writer notebook leases (no Qt dependency).

A durable adjacent lockfile is never unlinked: unlinking a held flock inode
would let another process acquire a new inode and falsely believe it had
exclusive ownership. The byte lock itself is released by the OS on exit or
crash. Instances of this version can open different notebooks concurrently.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path


class NotebookInUseError(RuntimeError):
    """Another Pinbu Note session is editing the requested notebook."""


class NotebookExternallyModifiedError(RuntimeError):
    """Another application altered the SQLite notebook after it was opened."""


_active_paths: set[str] = set()
_active_lock = threading.Lock()


def disk_signature(path):
    """Cheap external-write signal, including SQLite's change counter.

    It is a conflict detector, not a cryptographic integrity guarantee.
    Include WAL metadata for externally opened databases using WAL mode.
    """
    path = Path(path)
    try:
        st = path.stat()
    except FileNotFoundError:
        return None
    with path.open('rb') as fh:
        fh.seek(24)
        change_counter = fh.read(4)
    wal = path.with_name(path.name + '-wal')
    try:
        ws = wal.stat()
        wal_info = (ws.st_size, ws.st_mtime_ns)
    except FileNotFoundError:
        wal_info = None
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
            change_counter, wal_info)


class NotebookLease:
    def __init__(self, notebook_path):
        self.notebook_path = Path(notebook_path).expanduser().resolve()
        self.path_key = os.path.normcase(str(self.notebook_path))
        self.lock_path = self.notebook_path.with_name(self.notebook_path.name + '.lock')
        self._handle = None
        self._locked = False

    def acquire(self):
        with _active_lock:
            if self.path_key in _active_paths:
                raise NotebookInUseError(
                    f'This notebook is already open in Pinbu Note:\n{self.notebook_path}\n\n'
                    'Switch to its existing window instead of opening another editable copy.')
            _active_paths.add(self.path_key)
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.lock_path.open('a+b')
            if sys.platform == 'win32':
                import msvcrt
                # Windows byte-range locks are mandatory: reading the first
                # byte while another instance owns it may fail *before* the
                # lock attempt. Use fstat to initialise only a NEW lockfile.
                if os.fstat(self._handle.fileno()).st_size == 0:
                    self._handle.write(b'\0')
                    self._handle.flush()
                self._handle.seek(0)
                try:
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise NotebookInUseError(
                        f'This notebook is already being edited in another Pinbu Note window:\n'
                        f'{self.notebook_path}\n\nClose the other session first.') from exc
            else:
                import fcntl
                try:
                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise NotebookInUseError(
                        f'This notebook is already being edited in another Pinbu Note window:\n'
                        f'{self.notebook_path}\n\nClose the other session first.') from exc
            self._locked = True
            return self
        except BaseException:
            self.release()
            raise

    def release(self):
        handle, self._handle = self._handle, None
        locked, self._locked = self._locked, False
        try:
            if handle is not None:
                try:
                    # Never unlock a byte-range we failed to acquire. On
                    # Windows this can mask the real NotebookInUseError.
                    if locked:
                        if sys.platform == 'win32':
                            import msvcrt
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    handle.close()
        finally:
            with _active_lock:
                _active_paths.discard(self.path_key)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *_):
        self.release()
