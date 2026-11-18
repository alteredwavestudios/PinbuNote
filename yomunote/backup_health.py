"""SafeSave health and optional independent secondary backup storage.

No Qt imports. All inspection/verification can run on a worker thread.
No backup file is treated as valid merely because it exists on disk.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .safe_backup import (BACKUP_MARKER, list_snapshots, project_folder,
                          restore_snapshot, verify_snapshot)


class SecondaryBackupError(IOError):
    """Primary backup was committed; secondary destination could not be updated."""

    def __init__(self, primary_snapshot: Path | None, reason: BaseException):
        self.primary_snapshot = primary_snapshot
        self.reason = reason
        super().__init__(f'Primary local backup was saved, but the optional '
                         f'second backup FAILED: {reason}')


class PrimaryBackupError(IOError):
    """Mandatory primary failed; secondary may still contain a useful snapshot."""

    def __init__(self, secondary_snapshot: Path | None, reason: BaseException,
                 secondary_error: BaseException | None = None):
        self.secondary_snapshot = secondary_snapshot
        self.reason = reason
        self.secondary_error = secondary_error
        state = ('A new secondary snapshot was saved.' if secondary_snapshot
                 else 'No new secondary snapshot could be confirmed.')
        if secondary_error is not None:
            state += f' Secondary also failed: {secondary_error}'
        super().__init__(f'PRIMARY local backup FAILED: {reason}. {state}')


def distinct_backup_paths(primary: Path, secondary: Path) -> bool:
    """Reject equal/nested roots (including symlink aliases) and Windows case aliases.

    Keeping both stores in the same tree makes backup pruning/migration unsafe
    and offers no meaningful location independence.
    """
    first = Path(primary).expanduser().resolve()
    second = Path(secondary).expanduser().resolve()
    # Be deliberately conservative on all OSes: even a Linux case-sensitive
    # path should not silently become an alias when moved onto macOS/Windows.
    a, b = str(first).casefold(), str(second).casefold()
    if a == b:
        return False
    if first == second or first in second.parents or second in first.parents:
        return False
    return not (a in (str(p).casefold() for p in second.parents) or
                b in (str(p).casefold() for p in first.parents))


def backup_to_destinations(notebook, primary: Path, secondary: Path | None = None,
                           *, limit=100, force=False, reason='automatic'):
    """Commit the primary backup first, then a fully independent secondary one.

    Never copy partially written archive files from one destination to another:
    each store uses the *committed notebook* as its source. If the second store
    fails, preserve and report the primary snapshot as successful.
    """
    primary = Path(primary).expanduser()
    if secondary is not None and not distinct_backup_paths(primary, secondary):
        raise ValueError('Primary and secondary backup folders must be separate, '
                         'non-nested locations.')
    first = second = None
    primary_error = secondary_error = None
    try:
        first = notebook.safesave_backup(primary, limit=limit, force=force,
                                         reason=reason)
    except Exception as exc:
        primary_error = exc
    # A failed primary disk must never prevent attempting a configured,
    # separate second disk. It could be the user's only new recovery point.
    if secondary is not None:
        try:
            second_root = Path(secondary).expanduser()
            # Never silently recreate a vanished external-drive folder on
            # another disk and mistake that for a successful secondary backup.
            if not second_root.is_dir() or second_root.is_symlink():
                raise FileNotFoundError(
                    'Second backup location is not an available ordinary folder; '
                    'reconnect the backup drive or choose another destination.')
            second = notebook.safesave_backup(
                second_root, limit=limit, force=force,
                reason=reason)
        except Exception as exc:
            secondary_error = exc
    if primary_error is not None:
        raise PrimaryBackupError(second, primary_error, secondary_error) from primary_error
    if secondary_error is not None:
        raise SecondaryBackupError(first, secondary_error) from secondary_error
    return first, second



@dataclass(frozen=True)
class StoreHealth:
    destination: str
    marker: str | None
    snapshot_count: int
    latest: str | None
    bytes_used: int
    error: str | None = None


def notebook_history_path(root: Path, notebook_id: str, title: str,
                          source_path: Path) -> Path:
    """Resolve a specific project history without creating or altering files."""
    source = Path(source_path).expanduser().resolve()
    key = hashlib.sha256(str(source).encode('utf-8')).hexdigest()[:12]
    return project_folder(Path(root), notebook_id, title, key) / BACKUP_MARKER


def inspect_store(root: Path, notebook_id: str, title: str,
                  source_path: Path) -> StoreHealth:
    """Read snapshot inventory and storage consumed; no writable DB opens."""
    root = Path(root).expanduser()
    try:
        marker = notebook_history_path(root, notebook_id, title, source_path)
        if not marker.is_file():
            return StoreHealth(str(root), None, 0, None, 0)
        if marker.is_symlink():
            raise ValueError('Backup marker is a symlink.')
        snapshots = list_snapshots(marker)
        size = 0
        for path in marker.parent.rglob('*'):
            if path.is_symlink():
                raise ValueError('Backup contains an unexpected symlink.')
            if path.is_file():
                size += path.stat().st_size
        return StoreHealth(str(root), str(marker), len(snapshots),
                           snapshots[0]['timestamp'] if snapshots else None,
                           size)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return StoreHealth(str(root), None, 0, None, 0, str(exc))


def verify_history(marker: Path, *, all_snapshots=False):
    """Hash-check chosen snapshots; perform a real restore of the latest one.

    'all_snapshots=True' is deliberately exhaustive and potentially slow;
    call from a GUI worker, not on the main thread. The temporary restored
    notebook is thrown away, never placed beside a user's live notebook.
    """
    marker = Path(marker)
    snapshots = list_snapshots(marker)
    if not snapshots:
        raise ValueError('No snapshots exist in this history.')
    chosen = snapshots if all_snapshots else snapshots[:1]
    for snap in chosen:
        verify_snapshot(marker, snap['id'])
    with tempfile.TemporaryDirectory(prefix='pinbu-verify-') as tmp:
        restored = Path(tmp) / 'Verified Restore.pinbunote'
        restore_snapshot(marker, restored, snapshot_id=snapshots[0]['id'])
        if not restored.is_file() or restored.stat().st_size == 0:
            raise IOError('Restored notebook is missing or empty.')
    return len(chosen), len(snapshots)
