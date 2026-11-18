"""Pinbu Note v7 notebook container: one portable, incremental SQLite file.

Each tab uses an ordinary v5 Project in a temporary working directory. PDF
raster caches never enter the container or its backup snapshots. Only altered
source files/manifests are written to SQLite on each debounce save, so saving
huge PDFs does NOT require re-zipping the entire notebook.

The on-disk format is deliberately distinct from legacy v2-v4 .yominote
DIRECTORIES. Opening a legacy directory creates a new portable FILE alongside
it; legacy sources are never overwritten or deleted.
"""
from __future__ import annotations

import json
import hashlib
import re
import copy
import os
import shutil
import sqlite3
import tempfile
import sys
from contextlib import closing
from dataclasses import dataclass
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .research import effective_reference, effective_tags, effective_page_label
from .project import Project, safe_name, unique_project_path, short_id
from .reading_view import clean_reading_view
from .snapshot_save import (SaveGuard, FrozenFile, SaveSnapshot,
                            MAX_SNAPSHOT_JSON_BYTES)
from .notebook_lock import (NotebookLease, NotebookInUseError,
                            NotebookExternallyModifiedError, disk_signature)

NOTEBOOK_VERSION = 7
READABLE_NOTEBOOK_VERSIONS = (5, 6, 7)
MAGIC_FORMAT = 'yomu-notebook'
MAX_TABS = 256
MAX_ASSET_BYTES = 1024 * 1024 * 1024
BACKUP_STORAGE_SAFETY_BYTES = 2 * 1024 * 1024 * 1024

class NotebookNewerVersionError(ValueError):
    """A future application release wrote this notebook; prevent unsafe edits."""


def _version_sortkey(value):
    # Both 0.95 (our stability release) and historical 0.9.2b are valid.
    # The second number is a *number*, not a decimal fraction: 0.95 > 0.9.2b.
    # Always return five comparable integers, including for pre-release names.
    match = re.fullmatch(r'(\d+)\.(\d+)(?:\.(\d+))?([a-z]?)(\d*)', str(value))
    if match is None:
        return None
    a, b, c, suffix, number = match.groups()
    return (int(a), int(b), int(c or 0),
            27 if suffix == '' else ord(suffix) - ord('a') + 1,
            int(number or 0))
# Untrusted notebook files may lie about record counts/sizes. These are
# generous upper limits on the TEMPORARY extraction workspace, not limits on
# how much free space a user may have on their computer. They prevent a
# deliberately crafted notebook from filling a disk with millions of entries.
MAX_LOADED_FILES = 200_000
MAX_LOADED_BYTES = 32 * 1024 * 1024 * 1024
MAX_MANIFEST_BYTES = 32 * 1024 * 1024


def read_bounded_manifest(conn):
    """Read the top-level notebook metadata without loading huge hostile data.

    A .pinbunote is just SQLite and might originate outside this app. Reading
    ``SELECT value`` first gives SQLite permission to transfer an arbitrarily
    large string into Python before our validator ever sees it. Even JSON
    rejected immediately afterwards can waste a surprising amount of memory.

    Instead, ask SQLite to measure the *UTF-8 byte length* and return the value
    only when it fits. The CASE expression also makes the decision and fetch
    part of one statement, so a concurrent database edit cannot change the row
    between two separate queries. We intentionally don't validate the app
    version here: some callers must inspect newer notebooks without editing.
    """
    row = conn.execute(
        "SELECT CASE WHEN typeof(value) = 'text' "
        "AND length(CAST(value AS BLOB)) BETWEEN 1 AND ? "
        "THEN value ELSE NULL END "
        "FROM meta WHERE key=?",
        (MAX_MANIFEST_BYTES, 'manifest'),
    ).fetchone()
    if row is None or not isinstance(row[0], str):
        raise ValueError('Notebook has no valid manifest or its metadata is too large.')
    try:
        data = json.loads(row[0])
    except (ValueError, TypeError) as exc:
        raise ValueError('Notebook metadata is not valid JSON.') from exc
    if not isinstance(data, dict):
        raise ValueError('Notebook metadata must be an object.')
    return data

# These names are reserved by Windows, even with a file extension.
# We reject them on every OS so notebooks stay portable.
_WINDOWS_RESERVED = re.compile(
    r'^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$',
    re.IGNORECASE,
)


def _safe_file_segment(part: str) -> bool:
    """Check one path component before creating a file.

    A component is just the text between two '/' characters.
    ':' is dangerous on Windows because it can name a drive
    or an alternate data stream, not an ordinary file.
    """
    return (
        part not in ('', '.', '..')
        and not any(ord(char) < 32 for char in part)
        and not any(char in part for char in '<>:"|?*')
        and not part.endswith((' ', '.'))
        and not _WINDOWS_RESERVED.fullmatch(part)
    )



def _safe_tab_id(value):
    """Accept only a 32-character lowercase hexadecimal tab identifier."""
    return (isinstance(value, str) and len(value) == 32 and
            all(c in '0123456789abcdef' for c in value))


def _safe_relative(value, allowed_ids):
    """Accept ONLY a tab manifest or an asset within a tab's allowed roots."""
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('Unsafe notebook entry path.')
    parts = value.split('/')
    if (len(parts) < 3 or parts[0] != 'tabs' or parts[1] not in allowed_ids
            or not all(_safe_file_segment(part) for part in parts)):
        raise ValueError('Unsafe notebook entry path.')
    if len(parts) == 3:
        valid = parts[2] in ('project.json', 'project.v2.backup.json', 'project.v3.backup.json')
    else:
        valid = parts[2] in ('originals', 'pages')
    if not valid:
        raise ValueError('Unsafe notebook entry path.')
    return Path(*parts)


def default_backup_folder():
    """User-writable Pinbu Note backups (legacy Yomu backups remain untouched)."""
    import sys
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        return Path(base) / 'Pinbu Note' / 'Backups'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Pinbu Note' / 'Backups'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'Pinbu Note' / 'Backups'



# Snapshot only page-related metadata. Notes text, page setup and other tab
# settings are deliberately NOT overwritten by cross-tab Undo/Redo.
_TRANSFER_FIELDS = (
    'pages', 'page_groups', 'read_page_ids', 'annotations',
    'reading_view', 'selected_page', 'research',
)


def _page_state(project: Project) -> dict:
    return {field: copy.deepcopy(getattr(project, field))
            for field in _TRANSFER_FIELDS}


def _set_page_state(project: Project, state: dict,
                    expected: dict | None = None) -> None:
    """Restore page structure without erasing unrelated reading positions.

    Scroll positions do not create Undo commands. If someone has read a
    DIFFERENT page since a transfer, undoing that transfer must not rewind
    their more recent scroll position. Only view keys that actually differ
    between the before/after transfer snapshots are restored.
    """
    for field in _TRANSFER_FIELDS:
        if field != 'reading_view':
            setattr(project, field, copy.deepcopy(state[field]))
    if expected is None:
        project.reading_view = copy.deepcopy(state['reading_view'])
        return
    current = project.reading_view if isinstance(project.reading_view, dict) else {}
    old = expected.get('reading_view') or {}
    desired = state.get('reading_view') or {}
    merged = copy.deepcopy(current)
    for field in ('positions', 'page_zooms', 'group_zooms'):
        old_map = old.get(field, {})
        new_map = desired.get(field, {})
        old_map = old_map if isinstance(old_map, dict) else {}
        new_map = new_map if isinstance(new_map, dict) else {}
        present = merged.setdefault(field, {})
        for key in set(old_map) | set(new_map):
            if old_map.get(key) == new_map.get(key):
                continue
            if key in new_map:
                present[key] = copy.deepcopy(new_map[key])
            else:
                present.pop(key, None)
    for field in ('independent_pages', 'unshared_roots'):
        old_ids = set(old.get(field) or [])
        new_ids = set(desired.get(field) or [])
        current_ids = set(merged.get(field) or [])
        merged[field] = sorted((current_ids - (old_ids - new_ids))
                               | (new_ids - old_ids))
    project.reading_view = merged


@dataclass
class PageTransferChange:
    """One reversible notebook-wide page transfer, without duplicating media."""
    notebook_id: str
    source_id: str
    target_id: str
    source_before: dict
    target_before: dict
    source_after: dict
    target_after: dict
    created_assets: tuple[str, ...]
    move: bool

    @property
    def estimated_bytes(self) -> int:
        return sum(len(json.dumps(state, ensure_ascii=False).encode('utf-8'))
                   for state in (self.source_before, self.target_before,
                                 self.source_after, self.target_after)) + 512



class Notebook:
    """Own one portable study notebook and its temporary editing workspace.

    Beginner's picture: ``self.path`` is the SQLite file the user saves;
    ``self.workspace`` is a temporary folder of editable tab projects.
    ``self.tabs`` is the ordered list shown across the top of the window.
    Calling ``save`` reconciles live project files into the SQLite database.
    Closing removes the temporary workspace, not the user's notebook file.
    """
    def __init__(self, path: Path, name: str, tabs: list[dict], active_id: str,
                 identifier: str, temporary: tempfile.TemporaryDirectory):
        self.path = Path(path).resolve()
        self.name = name
        self.tabs = tabs
        self.active_id = active_id
        self.identifier = identifier
        self._temporary = temporary
        self.workspace = Path(temporary.name)
        self._saved_stats = {}
        self._saved_manifest_hashes = {}
        self.recovery_warnings = []
        self._saved_manifest = None
        self.backup_dirty = False
        self._closed = False
        self._origin_path = None  # set only for explicit-publish local sessions
        self._origin_lease = None
        self._session_dir = None
        self._session_backed_up = False
        self._session_status = None  # active / closed; no cloud writes on close
        self._unpublished = False
        # Acquire before the workspace is used and before any SQLite write.
        # Keep the OS handle alive for the whole editable session.
        self._lease = NotebookLease(self.path).acquire()
        self._save_guard = SaveGuard()
        self._save_guard.disk_identity = disk_signature(self.path)

    @classmethod
    def _new_workspace(cls, path, name, tabs, active_id, identifier):
        temporary = tempfile.TemporaryDirectory(prefix='yomu-notebook-')
        try:
            return cls(path, name, tabs, active_id, identifier, temporary)
        except BaseException:
            temporary.cleanup()
            raise

    @classmethod
    def open_session(cls, path: Path, working_base: Path | None = None):
        """GUI entry point: isolate all autosaves from the published original."""
        source = Path(path).expanduser().resolve()
        if source.is_dir():
            # Migrating a v2-v4 folder produces a NEW v7 notebook alongside
            # the old folder, then stages that notebook locally as usual.
            migrated = cls.load(source)
            migrated_path = migrated.path
            migrated.close()
            source = migrated_path
        from .safe_session import open_working_copy
        return open_working_copy(source, working_base)

    @property
    def display_path(self):
        """The user-selected external notebook path, never its local cache."""
        return self._origin_path or self.path

    def publish(self):
        """Explicit Save only: write the verified local version to its origin."""
        from .safe_session import publish
        return publish(self)

    @classmethod
    def create(cls, parent: Path, name: str, *, extension='.yomunote'):
        parent = Path(parent).expanduser()
        parent.mkdir(parents=True, exist_ok=True)
        path = unique_project_path(parent, name, extension=extension)
        identifier = uuid.uuid4().hex
        tabid = uuid.uuid4().hex
        tab = {'id': tabid, 'title': 'My Notes'}
        nb = cls._new_workspace(path, safe_name(name), [tab], tabid, identifier)
        nb._prepare_project(tabid, tab['title'])
        nb.save()
        return nb

    def _prepare_project(self, tabid, title):
        directory = self.workspace / 'tabs' / tabid
        for name in ('originals', 'pages', 'cache/thumbs', 'cache/previews'):
            (directory / name).mkdir(parents=True, exist_ok=True)
        project = Project(path=directory, name=title)
        project.save()
        return project

    @classmethod
    def load(cls, path: Path, *, recover_cosmetic: bool = False):
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            return cls.migrate_legacy(path)
        if not path.is_file():
            raise ValueError('Choose an existing Pinbu Note or legacy Yomu Note notebook file.')
        if path.suffix.lower() not in ('.pinbunote', '.yomunote', '.yominote'):
            raise ValueError('Choose a .pinbunote or legacy .yomunote/.yominote notebook.')
        try:
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
                meta = read_bounded_manifest(conn)
                cls._check_manifest(meta)
                nb = cls._new_workspace(path, meta['name'], meta['tabs'],
                                        meta['active_id'], meta['id'])
                nb._saved_manifest = json.dumps(meta, sort_keys=True, ensure_ascii=False)
                try:
                    # SQLite BLOBs stay on disk while we check the index.
                    # This is a fast guard against hostile files claiming an
                    # enormous number of files or total extraction size.
                    inventory = conn.execute(
                        'SELECT count(*),sum(size),sum(length(data)) FROM files'
                    ).fetchone()
                    file_count, stated_bytes, actual_bytes = inventory
                    if (file_count > MAX_LOADED_FILES or stated_bytes is None
                            or actual_bytes is None or stated_bytes < 0
                            or actual_bytes < 0 or stated_bytes > MAX_LOADED_BYTES
                            or actual_bytes > MAX_LOADED_BYTES
                            or stated_bytes != actual_bytes):
                        raise ValueError('Notebook exceeds safe extraction limits or has invalid asset sizes.')
                    ids = {t['id'] for t in meta['tabs']}
                    # Read blobs in 1 MiB chunks. A user may import a 1 GB
                    # source PDF; never allocate the entire file in RAM.
                    for rowid, rel, size, mtime in conn.execute(
                            'SELECT rowid, path, size, mtime_ns FROM files'):
                        local = _safe_relative(rel, ids)
                        if type(size) is not int or not 0 <= size <= MAX_ASSET_BYTES:
                            raise ValueError('Invalid notebook entry size.')
                        # A malicious timestamp can be negative, nonnumeric,
                        # or beyond what Windows/macOS can represent.
                        if type(mtime) is not int or not 0 <= mtime <= 9_223_372_036_854_775_807:
                            raise ValueError('Invalid notebook entry timestamp.')
                        # Resolve before writing to prevent path traversal.
                        # This also rejects any unexpected symlink escape.
                        dest = (nb.workspace / local).resolve()
                        if not dest.is_relative_to(nb.workspace.resolve()):
                            raise ValueError('Unsafe notebook entry path.')
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with conn.blobopen('files', 'data', rowid, readonly=True) as blob, dest.open('wb') as out:
                            if len(blob) != size:
                                raise ValueError('Corrupted notebook asset length.')
                            while True:
                                chunk = blob.read(1024 * 1024)
                                if not chunk:
                                    break
                                out.write(chunk)
                        os.utime(dest, ns=(int(mtime), int(mtime)))
                        nb._saved_stats[rel] = (int(mtime), size)
                        if local.name.endswith('.json'):
                            nb._saved_manifest_hashes[rel] = hashlib.sha256(
                                dest.read_bytes()).hexdigest()
                    for tab in meta['tabs']:
                        project = Project.load(
                            nb.workspace / 'tabs' / tab['id'],
                            recover_cosmetic=recover_cosmetic,
                            recovery_warnings=nb.recovery_warnings,
                        )
                        # Old versions could silently omit live assets. Do not
                        # pretend a notebook opened successfully if an original
                        # or a converted render file is missing from its ZIP-like
                        # SQLite container. The original file remains untouched.
                        for page in project.pages:
                            for field in ('source', 'render_source', 'file'):
                                relative = page.get(field)
                                if relative:
                                    entry = project.asset_path(relative)
                                    if not entry.is_file() or entry.is_symlink():
                                        raise ValueError(
                                            f'Notebook is missing a page asset in tab '
                                            f'"{project.name}": {relative}. '
                                            'Try restoring a known-good backup.')
                        if recover_cosmetic and nb.recovery_warnings:
                            # The ORIGINAL notebook file is never altered.
                            # Recovery is only allowed on a separate copy.
                            project.save()
                    if recover_cosmetic and nb.recovery_warnings:
                        nb.save()
                    if disk_signature(path) != nb._save_guard.disk_identity:
                        raise NotebookExternallyModifiedError(
                            'Notebook changed externally while its pages were being loaded.')
                    nb.upgrade_legacy_extension()
                    return nb
                except Exception:
                    nb.close()
                    raise
        except sqlite3.DatabaseError as exc:
            raise ValueError('This file is not a supported Pinbu Note notebook.') from exc

    @staticmethod
    def _check_manifest(meta, *, allow_newer_app=False):
        if not isinstance(meta, dict) or meta.get('format') != MAGIC_FORMAT:
            raise ValueError('Unsupported notebook container format.')
        if meta.get('version') not in READABLE_NOTEBOOK_VERSIONS:
            raise NotebookNewerVersionError(
                f"This notebook uses format v{meta.get('version')} but this "
                f"Pinbu Note supports up to format v{NOTEBOOK_VERSION}. Please update "
                'the app. Do not overwrite this notebook with an older version.')
        saved_version = _version_sortkey(meta.get('app_version'))
        current_version = _version_sortkey(__version__)
        if (not allow_newer_app and saved_version and current_version
                and saved_version > current_version):
            raise NotebookNewerVersionError(
                f"This notebook was saved by newer Pinbu Note "
                f"v{meta.get('app_version')} (installed: v{__version__}). "
                'Some features or annotations may not work correctly in this older '
                'version. We strongly recommend upgrading Pinbu Note. '
                'The notebook has been left untouched; do not edit or autosave '
                'over a newer-version notebook with an older app.')
        tabs = meta.get('tabs')
        if not isinstance(tabs, list) or not 1 <= len(tabs) <= MAX_TABS:
            raise ValueError('Invalid number of notebook tabs.')
        ids = [t.get('id') for t in tabs if isinstance(t, dict)]
        if len(ids) != len(tabs) or not all(_safe_tab_id(x) for x in ids) or len(set(ids)) != len(ids):
            raise ValueError('Invalid tab identifiers.')
        if any(not isinstance(t.get('title'), str) or not 1 <= len(t['title']) <= 100 for t in tabs):
            raise ValueError('Invalid tab names.')
        if meta.get('active_id') not in ids or not _safe_tab_id(meta.get('id')):
            raise ValueError('Invalid notebook identifiers.')
        if not isinstance(meta.get('name'), str) or len(meta['name']) > 240:
            raise ValueError('Invalid notebook name.')

    @classmethod
    def migrate_legacy(cls, folder: Path):
        """Safe COPY of v2-v4 folder; never touch the user's original folder."""
        original = Project.load(folder)
        nb = cls.create(folder.parent, original.name)
        tabid = nb.tabs[0]['id']
        target = nb.workspace / 'tabs' / tabid
        for base in ('originals', 'pages'):
            source = original.path / base
            if not source.exists():
                continue
            for entry in source.rglob('*'):
                if entry.is_symlink():
                    nb.close()
                    raise ValueError('Refusing to import a symlink from a legacy project.')
                if entry.is_file():
                    dest = target / base / entry.relative_to(source)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(entry, dest)
        shutil.copy2(original.path / 'project.json', target / 'project.json')
        restored = Project.load(target)
        nb.tabs[0]['title'] = restored.name
        nb.name = original.name
        nb.save()
        return nb

    def project(self, tabid: str):
        if tabid not in {t['id'] for t in self.tabs}:
            raise KeyError('Tab does not exist.')
        return Project.load(self.workspace / 'tabs' / tabid)

    def add_tab(self, title: str = 'New Tab'):
        if len(self.tabs) >= MAX_TABS:
            raise ValueError('This notebook has reached its tab limit.')
        title = title.strip()[:100]
        if not title:
            raise ValueError('Tab name cannot be empty.')
        tabid = uuid.uuid4().hex
        self._prepare_project(tabid, title)
        self.tabs.append({'id': tabid, 'title': title})
        self.active_id = tabid
        return tabid

    def rename_tab(self, tabid: str, title: str):
        title = title.strip()[:100]
        if not title:
            raise ValueError('Tab name cannot be empty.')
        tab = next(t for t in self.tabs if t['id'] == tabid)
        tab['title'] = title
        project = self.project(tabid)
        project.name = title
        project.save()

    def delete_tab(self, tabid: str):
        if len(self.tabs) <= 1:
            raise ValueError('A notebook must have at least one tab.')
        index = next(i for i, tab in enumerate(self.tabs) if tab['id'] == tabid)
        tab = self.tabs.pop(index)
        if self.active_id == tabid:
            self.active_id = self.tabs[min(index, len(self.tabs)-1)]['id']
        # Tab files stay in temporary workspace for in-session Undo; they do
        # NOT go into the saved notebook after this edit.
        return index, tab

    def restore_tab(self, index: int, tab: dict):
        if tab['id'] in {t['id'] for t in self.tabs}:
            raise ValueError('Tab is already in notebook.')
        self.tabs.insert(max(0, min(index, len(self.tabs))), dict(tab))
        self.active_id = tab['id']

    def move_tab(self, source: int, destination: int):
        item = self.tabs.pop(source)
        self.tabs.insert(destination, item)

    def transfer_pages(self, source_id: str, target_id: str,
                       page_ids: list[str], move: bool = False,
                       *, return_change: bool = False):
        """Commit a copy/move as ONE notebook transaction.

        Files are copied to a staging directory first, then installed under
        unique names. The two temporary project manifests are restored if
        any stage, manifest write, or SQLite commit fails. SQLite itself
        supplies crash-safe all-or-nothing durability for the portable file.
        """
        if source_id == target_id:
            raise ValueError('Choose another tab as the destination.')
        source = self.project(source_id)
        target = self.project(target_id)
        selected_ids = set(page_ids)
        selected = [p for p in source.pages if p['id'] in selected_ids]
        if not selected:
            return (0, None) if return_change else 0
        if len(selected) + len(target.pages) > 20_000:
            raise ValueError('Destination tab would exceed the 20,000-page limit.')

        source_before = _page_state(source)
        target_before = _page_state(target)
        promoted: list[Path] = []
        mapping: dict[str, str] = {}
        new_pages = []
        stage = Path(tempfile.mkdtemp(prefix='.yomu-transfer-', dir=target.path))
        backup_source = stage / 'source-project.json'
        backup_target = stage / 'target-project.json'
        try:
            # Create on-disk rollback manifests BEFORE changing either tab.
            # os.replace restores them without allocating additional space,
            # even if the transfer failed because the disk filled up.
            shutil.copyfile(source.path / 'project.json', backup_source)
            shutil.copyfile(target.path / 'project.json', backup_target)
            for original in selected:
                item = copy.deepcopy(original)
                old_id = item['id']
                item['id'] = short_id()
                for field in ('source', 'render_source', 'file'):
                    old_relative = item.get(field)
                    if not old_relative:
                        continue
                    if old_relative not in mapping:
                        rel = Path(old_relative)
                        if rel.parts[0] not in ('originals', 'pages'):
                            raise ValueError('Cannot transfer cached files as page sources.')
                        origin = source.asset_path(old_relative)
                        if not origin.is_file() or origin.is_symlink():
                            raise ValueError(f'Source document is missing or unsafe: {old_relative}')
                        before = origin.stat()
                        if before.st_size > MAX_ASSET_BYTES:
                            raise ValueError('Page source exceeds the 1 GB safety limit.')
                        new_relative = f'{rel.parts[0]}/{short_id()}{rel.suffix.lower()}'
                        destination = target.asset_path(new_relative)
                        staged_file = stage / str(len(mapping))
                        shutil.copy2(origin, staged_file)
                        after = origin.stat()
                        if (after.st_size != before.st_size or
                                after.st_mtime_ns != before.st_mtime_ns or
                                staged_file.stat().st_size != before.st_size):
                            raise IOError('Page source changed during transfer; please retry.')
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if destination.exists():
                            raise FileExistsError('Destination asset already exists.')
                        os.replace(staged_file, destination)
                        promoted.append(destination)
                        mapping[old_relative] = new_relative
                    item[field] = mapping[old_relative]
                # Copy the EFFECTIVE citation/tag/locator from the source
                # navigator, not just direct per-page assignments. The
                # receiving tab may have no corresponding parent group.
                research = source.research
                copied_ref = effective_reference(research, source.page_groups, old_id)
                if copied_ref:
                    def ensure_reference(ref_id):
                        record = copy.deepcopy(research['references'][ref_id])
                        parent = record.get('parent_id')
                        if parent:
                            ensure_reference(parent)
                        previous = target.research['references'].get(ref_id)
                        if previous is not None and previous != record:
                            raise ValueError('Reference ID collision during page transfer.')
                        target.research['references'][ref_id] = record
                    ensure_reference(copied_ref)
                    target.research['reference_assignments']['pages'][item['id']] = copied_ref
                elif (old_id in research['reference_assignments']['pages']
                      and research['reference_assignments']['pages'][old_id] is None):
                    # Preserve an intentional 'no citation', without adding
                    # redundant nulls for every unreferenced copied page.
                    target.research['reference_assignments']['pages'][item['id']] = None
                effective = effective_tags(research, source.page_groups, old_id)
                for tag_id in effective:
                    tag = copy.deepcopy(research['tags'][tag_id])
                    existing = target.research['tags'].get(tag_id)
                    if existing is not None and existing != tag:
                        raise ValueError('Tag ID collision during page transfer.')
                    target.research['tags'][tag_id] = tag
                if effective:
                    target.research['tag_assignments']['pages'][item['id']] = sorted(effective)
                original_label = effective_page_label(research, source.page_groups, original)
                if original_label != str(original.get('source_page') or 1):
                    target.research['numbering']['pages'][item['id']] = original_label
                if old_id in source.annotations:
                    target.annotations[item['id']] = copy.deepcopy(source.annotations[old_id])
                if move and old_id in source.read_page_ids:
                    target.read_page_ids.append(item['id'])
                # Transfer reading position/zoom with a MOVE. Copies begin at
                # their own reading position, avoiding surprising shared state.
                if move and isinstance(source.reading_view, dict):
                    target.reading_view = (target.reading_view if
                                           isinstance(target.reading_view, dict) else {})
                    for field in ('positions', 'page_zooms'):
                        original_values = source.reading_view.get(field, {})
                        if isinstance(original_values, dict) and old_id in original_values:
                            target.reading_view.setdefault(field, {})[item['id']] = copy.deepcopy(
                                original_values[old_id])
                    if old_id in source.reading_view.get('independent_pages', []):
                        target.reading_view.setdefault('independent_pages', []).append(item['id'])
                new_pages.append(item)

            target.pages.extend(new_pages)
            target.selected_page = new_pages[0]['id']
            if move:
                moved_ids = {p['id'] for p in selected}
                source.pages = [p for p in source.pages if p['id'] not in moved_ids]
                for pid in moved_ids:
                    source.annotations.pop(pid, None)
                source.read_page_ids = [pid for pid in source.read_page_ids
                                        if pid not in moved_ids]
                if source.selected_page in moved_ids:
                    source.selected_page = source.pages[0]['id'] if source.pages else None
                if isinstance(source.reading_view, dict):
                    for field in ('positions', 'page_zooms'):
                        if isinstance(source.reading_view.get(field), dict):
                            for pid in moved_ids:
                                source.reading_view[field].pop(pid, None)
                    if isinstance(source.reading_view.get('independent_pages'), list):
                        source.reading_view['independent_pages'] = [
                            pid for pid in source.reading_view['independent_pages']
                            if pid not in moved_ids]
            # Project.save reconciles page groups before the SQLite transaction.
            # Persist the actual sorted/reconciled model before recording Undo.
            # Otherwise an Undo could compare an in-memory list order with
            # the normalised read_page_ids from a subsequently loaded tab.
            if move:
                source.save(prune_orphan_annotations=True)
            target.save(prune_orphan_annotations=True)
            source_after = _page_state(self.project(source_id))
            target_after = _page_state(self.project(target_id))
            change = PageTransferChange(
                self.identifier, source_id, target_id, source_before, target_before,
                source_after, target_after,
                # Project.asset_path() canonicalises paths with .resolve(), but
                # TemporaryDirectory may report an equivalent non-canonical
                # spelling: /var vs /private/var on macOS, or 8.3 short names
                # vs long names on Windows. Canonicalise BOTH operands before
                # deriving relative asset paths for Undo/Redo. relative_to()
                # still rejects a destination outside the workspace.
                tuple(path.resolve().relative_to(self.workspace.resolve()).as_posix()
                      for path in promoted),
                bool(move),
            )
            self.save()  # BOTH page lists and the media become durable together.
        except BaseException:
            # An interrupted SQLite transaction leaves the last committed
            # notebook intact. Restore both live manifests via rename, which
            # also works under low-disk-space conditions.
            try:
                if backup_source.is_file():
                    os.replace(backup_source, source.path / 'project.json')
                if backup_target.is_file():
                    os.replace(backup_target, target.path / 'project.json')
            finally:
                for destination in promoted:
                    destination.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        return (len(new_pages), change) if return_change else len(new_pages)

    def replay_page_transfer(self, change: PageTransferChange, *, undo: bool):
        """One atomic cross-tab Undo/Redo, preserving unrelated notes text."""
        if change.notebook_id != self.identifier:
            raise ValueError('The transfer belongs to a different notebook.')
        source = self.project(change.source_id)
        target = self.project(change.target_id)
        expected = (change.source_after, change.target_after) if undo else (
            change.source_before, change.target_before)
        desired = (change.source_before, change.target_before) if undo else (
            change.source_after, change.target_after)
        # Undo must not discard a more recent annotation, reading tick or
        # navigator reorganisation from either tab. These are structural
        # conflicts; notes text remains independent and is always preserved.
        for project, expected_state in zip((source, target), expected):
            if any(getattr(project, field) != expected_state[field]
                   for field in ('pages', 'page_groups',
                                 'annotations', 'read_page_ids', 'research')):
                raise ValueError(
                    'Pages or annotations changed since this transfer; '
                    'cannot safely undo/redo it.')
        # Redo requires the media retained in the temporary workspace. Undo
        # deliberately keeps it there for Redo, but excludes it from the
        # portable notebook when no living page references it.
        if not undo:
            for relative in change.created_assets:
                entry = self.workspace / _safe_relative(relative, {
                    t['id'] for t in self.tabs})
                if not entry.is_file() or entry.is_symlink():
                    raise IOError('Transferred page source was removed; cannot redo.')
        stage = Path(tempfile.mkdtemp(prefix='.yomu-undo-', dir=target.path))
        backup_source = stage / 'source-project.json'
        backup_target = stage / 'target-project.json'
        try:
            shutil.copyfile(source.path / 'project.json', backup_source)
            shutil.copyfile(target.path / 'project.json', backup_target)
            _set_page_state(source, desired[0], expected[0])
            _set_page_state(target, desired[1], expected[1])
            source.save()
            target.save()
            self.save()
        except BaseException:
            if backup_source.is_file():
                os.replace(backup_source, source.path / 'project.json')
            if backup_target.is_file():
                os.replace(backup_target, target.path / 'project.json')
            raise
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    def _manifest(self):
        # App release is informational; the integer 'version' is the stable
        # on-disk format version used for backward compatibility.
        return {'format': MAGIC_FORMAT, 'version': NOTEBOOK_VERSION,
                'app_version': __version__,
                'id': self.identifier, 'name': self.name,
                'tabs': self.tabs, 'active_id': self.active_id}

    def _files(self):
        """Yield exactly the living assets and manifests (never raster caches).

        Checking each reference, instead of searching directories for files
        that happen to exist, prevents a damaged notebook from being silently
        saved without its source PDF/image or converted render file.
        """
        ids = {t['id'] for t in self.tabs}
        for tabid in ids:
            base = self.workspace / 'tabs' / tabid
            project = Project.load(base)
            live_page_ids = {page['id'] for page in project.pages}
            if set(project.annotations) - live_page_ids:
                project.save(prune_orphan_annotations=True)
            referenced = {
                value for page in project.pages
                for field in ('source', 'render_source', 'file')
                if (value := page.get(field))
            }
            for relative_source in sorted(referenced):
                if Path(relative_source).parts[0] not in ('originals', 'pages'):
                    raise ValueError('A live page refers to an unsupported source folder.')
                item = base / relative_source
                # Symlinks at any ancestor are forbidden even when they point
                # back into the notebook workspace.
                unsafe = any(part.is_symlink()
                             for part in (item, *list(item.parents)[:len(Path(relative_source).parts)]))
                if unsafe or not item.is_file():
                    cause = ('unsafe symbolic link' if unsafe else 'missing file')
                    raise ValueError(
                        f'Cannot save notebook: missing or unsafe page asset '
                        f'in tab "{project.name}": {relative_source} '
                        f'({cause}). Restore the original from a backup or reimport it.')
                rel = item.relative_to(self.workspace).as_posix()
                _safe_relative(rel, ids)
                yield rel, item
            for name in ('project.json', 'project.v2.backup.json',
                         'project.v3.backup.json'):
                item = base / name
                if item.exists():
                    if not item.is_file() or item.is_symlink():
                        raise ValueError('Unsafe notebook project manifest.')
                    yield item.relative_to(self.workspace).as_posix(), item

    def upgrade_legacy_extension(self):
        """Make a separate .yomunote copy; never rename/delete the old file.

        This is a filename migration, NOT a schema conversion. We first copy
        the complete SQLite database to a temporary sibling with bounded RAM,
        then atomically install the new filename and switch this session to it.
        It is safe to open an old copy again; we never overwrite new files.
        """
        if self.path.suffix.lower() != '.yominote':
            return False
        old = self.path
        suffix = 1
        destination = old.with_suffix('.yomunote')
        while destination.exists():
            suffix += 1
            destination = old.with_name(f'{old.stem} ({suffix}).yomunote')
        temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with old.open('rb') as source, temporary.open('xb') as out:
                shutil.copyfileobj(source, out, length=1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        new_lease = NotebookLease(destination).acquire()
        old_lease = self._lease
        self._lease = new_lease
        self.path = destination
        self._save_guard.disk_identity = disk_signature(destination)
        old_lease.release()
        self.backup_dirty = True
        return True

    def capture_save_snapshot(self):
        """On GUI thread: freeze metadata; list assets without reading PDF bytes."""
        import json
        import hashlib
        with self._save_guard.lock:
            if self._closed:
                raise RuntimeError('Cannot snapshot a closed notebook.')
            self.upgrade_legacy_extension()
            meta = self._manifest()
            self._check_manifest(meta)
            serial = json.dumps(meta, ensure_ascii=False, sort_keys=True)
            files = []
            metadata_bytes = 0
            for relative, item in self._files():
                fs = item.stat()
                if fs.st_size > MAX_ASSET_BYTES:
                    raise ValueError('A notebook asset exceeds the 1 GB safety limit.')
                is_json = item.suffix == '.json'
                data = item.read_bytes() if is_json else None
                if data is not None:
                    if len(data) > MAX_MANIFEST_BYTES:
                        raise ValueError('A notebook metadata file is too large.')
                    metadata_bytes += len(data)
                    if metadata_bytes > MAX_SNAPSHOT_JSON_BYTES:
                        from .snapshot_save import SnapshotTooLarge
                        raise SnapshotTooLarge('Notebook metadata exceeds the safe background snapshot budget.')
                files.append(FrozenFile(
                    relative, item, fs.st_size, fs.st_mtime_ns, fs.st_dev,
                    fs.st_ino, data,
                    hashlib.sha256(data).hexdigest() if data is not None else None))
            return SaveSnapshot(
                self.path, serial, tuple(files), dict(self._saved_stats),
                dict(self._saved_manifest_hashes), self._saved_manifest,
                self._save_guard, self._save_guard.generation, self.workspace)

    def accept_background_save(self, result):
        """Called on GUI thread. Ignore stale completions after newer saves."""
        with self._save_guard.lock:
            if (not result.applied or self._closed or
                    result.generation != self._save_guard.generation):
                return False
            self._saved_stats = result.stats
            self._saved_manifest_hashes = result.hashes
            self._saved_manifest = result.manifest
            if result.changed:
                self.backup_dirty = True
                if self._origin_path is not None:
                    self._unpublished = True
                    from .safe_session import _write_descriptor
                    _write_descriptor(self)
            return True

    def save(self):
        """Synchronous safety path; serialized against background workers."""
        with self._save_guard.lock:
            if self._closed:
                raise RuntimeError('Notebook has been closed.')
            changed = self._save_synchronous()
            self._save_guard.generation += 1
            if changed and self._origin_path is not None:
                self._unpublished = True
                from .safe_session import _write_descriptor
                _write_descriptor(self)
            return changed

    def _save_synchronous(self):
        """Original incremental SQLite save, retained for explicit operations."""
        if self._closed:
            raise RuntimeError('Notebook has been closed.')
        if disk_signature(self.path) != self._save_guard.disk_identity:
            raise NotebookExternallyModifiedError(
                'This notebook was modified on disk by another application or '
                'an older Pinbu Note version. Saving has been blocked to prevent '
                'overwriting changes. Close both copies and restore a known-good backup.')
        self.upgrade_legacy_extension()
        meta = self._manifest()
        self._check_manifest(meta)
        serial = json.dumps(meta, ensure_ascii=False, sort_keys=True)
        present = set()
        changed = serial != self._saved_manifest
        new_stats = dict(self._saved_stats)
        new_hashes = dict(self._saved_manifest_hashes)
        # Use a transaction so the manifest and every changed file appear
        # together; do not mutate our tracking state until commit succeeds.
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute('PRAGMA synchronous=FULL')
            # Overwrite freed SQLite cells instead of retaining the
            # raw bytes of documents that users have deleted.
            conn.execute('PRAGMA secure_delete=ON')
            with conn:
                conn.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                conn.execute('CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, data BLOB NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL)')
                for relative, item in self._files():
                    present.add(relative)
                    stat = item.stat()
                    size = stat.st_size
                    if size > MAX_ASSET_BYTES:
                        raise ValueError('A notebook file is larger than the 1 GB safety limit.')
                    record = (stat.st_mtime_ns, size)
                    is_manifest = item.suffix == '.json'
                    # Timestamps can have coarse resolution on USB disks.
                    # Hash small JSON metadata to catch same-size edits.
                    digest = (hashlib.sha256(item.read_bytes()).hexdigest()
                              if is_manifest else None)
                    if is_manifest and digest == self._saved_manifest_hashes.get(relative) \
                            and relative in self._saved_stats:
                        # Replacing a project.json can change its mtime without
                        # changing its contents (e.g. rollback after a failed
                        # transfer). Do not rewrite an identical SQLite BLOB.
                        new_stats[relative] = record
                        continue
                    if not is_manifest and record == self._saved_stats.get(relative):
                        continue
                    # sqlite3.blobopen writes in bounded chunks. The old
                    # read_bytes() path would temporarily allocate up to 1 GB.
                    conn.execute('INSERT OR REPLACE INTO files(path,data,size,mtime_ns) '
                                 'VALUES(?,zeroblob(?),?,?)',
                                 (relative, size, size, stat.st_mtime_ns))
                    row = conn.execute('SELECT rowid FROM files WHERE path=?', (relative,)).fetchone()
                    if row is None:
                        raise IOError('Could not allocate SQLite file entry.')
                    bytes_written = 0
                    with conn.blobopen('files', 'data', row[0]) as blob, item.open('rb') as original:
                        while bytes_written < size:
                            chunk = original.read(min(1024 * 1024, size - bytes_written))
                            if not chunk:
                                raise IOError('An imported file was truncated during save; try again.')
                            blob.write(chunk)
                            bytes_written += len(chunk)
                        # A file that grows during the copy must not be stored
                        # as a valid-looking truncated SQLite asset.
                        if original.read(1):
                            raise IOError('An imported file grew during save; try again.')
                    after = item.stat()
                    if after.st_size != size or after.st_mtime_ns != stat.st_mtime_ns:
                        raise IOError('An imported file changed during save; try again.')
                    new_stats[relative] = record
                    if is_manifest:
                        new_hashes[relative] = digest
                    changed = True
                removed = set(self._saved_stats) - present
                for rel in removed:
                    conn.execute('DELETE FROM files WHERE path=?', (rel,))
                    new_stats.pop(rel, None)
                    new_hashes.pop(rel, None)
                    changed = True
                if changed:
                    conn.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)', ('manifest', serial))
        self._save_guard.disk_identity = disk_signature(self.path)
        self._saved_stats = new_stats
        self._saved_manifest_hashes = new_hashes
        self._saved_manifest = serial
        if changed:
            self.backup_dirty = True
        return changed

    def safesave_backup(self, directory: Path | None = None, *, limit: int = 100,
                        force: bool = False, reason: str = 'automatic'):
        """Deduplicated per-project snapshots; separate assets and state folders."""
        from .safe_backup import create_snapshot, prune_snapshots
        from .safe_session import _write_descriptor
        self.save()  # atomic local commit before any snapshot is considered valid
        snapshot, project_dir = create_snapshot(
            self.path, Path(directory or default_backup_folder()),
            force=force, reason=reason, logical_source=self.display_path)
        if snapshot is not None:
            prune_snapshots(project_dir, max_snapshots=limit)
            self._session_backed_up = True
            self.backup_dirty = False
            _write_descriptor(self)
        return snapshot

    def backup(self, directory: Path | None = None, limit: int = 30):
        """Create a consistent snapshot, retaining at most limit per notebook."""
        directory = Path(directory or default_backup_folder()).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        limit = max(1, min(int(limit), 100))
        if not self.backup_dirty:
            return None
        self.save()
        prefix = f'{self.identifier}_'
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        output = directory / f'{prefix}{stamp}{self.path.suffix.lower()}'
        temp = output.with_suffix('.tmp')
        try:
            with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(temp)) as destination:
                source.backup(destination)
            os.replace(temp, output)
        finally:
            temp.unlink(missing_ok=True)
        # The name can change without breaking backup rotation.
        # Also include legacy snapshots prefixed with the old name.
        previous = sorted(
            (p for p in directory.iterdir()
             if p.suffix.lower() in ('.pinbunote', '.yomunote', '.yominote')
             and (p.name.startswith(prefix)
                  or f'_{self.identifier}_' in p.name)),
            key=lambda p: p.stat().st_mtime_ns,
        )
        # Respect both the user's count AND a conservative 2 GiB total cap.
        # Keep at least the most recent snapshot even for a large notebook.
        while len(previous) > 1 and (len(previous) > limit or
              sum(p.stat().st_size for p in previous) > BACKUP_STORAGE_SAFETY_BYTES):
            previous.pop(0).unlink()
        self.backup_dirty = False
        return output

    @staticmethod
    def restore_copy(source: Path, destination: Path):
        """Never overwrite the live notebook, even if user selected its path."""
        source = Path(source).expanduser().resolve()
        destination = Path(destination).expanduser().resolve()
        if destination.exists():
            raise FileExistsError('Choose a NEW file name to restore a backup safely.')
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as conn:
            Notebook._check_manifest(read_bounded_manifest(conn))
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with source.open('rb') as input_file, destination.open('xb') as output_file:
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            # This restored/copied notebook is independent of the original,
            # including its rotating backup history and displayed name.
            with closing(sqlite3.connect(destination)) as conn:
                with conn:
                    meta = read_bounded_manifest(conn)
                    meta['id'] = uuid.uuid4().hex
                    meta['name'] = safe_name(destination.stem)
                    conn.execute('UPDATE meta SET value=? WHERE key=?',
                                 (json.dumps(meta, ensure_ascii=False, sort_keys=True), 'manifest'))
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return destination

    @staticmethod
    def create_clean_share_copy(source: Path, destination: Path):
        """Create a compact copy with no deleted SQLite pages.

        Removing a document from a database does not always
        shrink the database file immediately. SQLite's VACUUM
        operation rebuilds the database using only *live* rows.

        VACUUM INTO writes this clean database to a NEW file.
        It does not modify the notebook the user is editing.

        Internal legacy project-manifest backups are removed from this
        *share copy* because they can contain historic deleted note text.
        Separate automatic recovery backups are not modified.
        """
        source = Path(source).expanduser().resolve()
        destination = Path(destination).expanduser().resolve()
        if source == destination or destination.exists():
            raise FileExistsError('Choose a NEW file name for the cleaned copy.')
        if destination.suffix.lower() not in ('.pinbunote', '.yomunote'):
            raise ValueError('Cleaned copies must have a supported notebook extension.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            # A read-only connection gets a consistent snapshot while
            # the user can continue working in the original notebook.
            with closing(sqlite3.connect(
                    source.as_uri() + '?mode=ro', uri=True)) as conn:
                # Validate the *source* before VACUUM creates an entire copy.
                # Without this preflight, a huge hostile notebook might consume
                # disk space even though its manifest would fail validation
                # when we inspect the destination a few lines below.
                Notebook._check_manifest(read_bounded_manifest(conn))
                conn.execute('VACUUM INTO ?', (str(destination),))
            # The copy gets its own identity for independent backups.
            with closing(sqlite3.connect(destination)) as conn:
                with conn:
                    meta = read_bounded_manifest(conn)
                    Notebook._check_manifest(meta)
                    meta['id'] = uuid.uuid4().hex
                    meta['name'] = safe_name(destination.stem)
                    conn.execute(
                        'UPDATE meta SET value=? WHERE key=?',
                        (json.dumps(meta, sort_keys=True,
                                    ensure_ascii=False), 'manifest'),
                    )
                    # Older migrations can leave backup manifests with note
                    # text that has since been removed from live pages.
                    # Keep them in the ORIGINAL/recovery backups, but never
                    # disclose them in a deliberately cleaned share copy.
                    conn.execute("DELETE FROM files WHERE path LIKE ? OR path LIKE ?",
                                 ('tabs/%/project.v2.backup.json',
                                  'tabs/%/project.v3.backup.json'))
                # A DELETE alone can leave historic bytes in SQLite free pages;
                # rebuild only the newly created share copy to erase them.
                conn.execute('VACUUM')
            return destination
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    @classmethod
    def recover_copy(cls, source: Path):
        """Recover cosmetic metadata damage into a NEW notebook.

        The user's original file is never overwritten.
        Any invalid annotations are omitted ONLY from this
        recovered copy. The original remains available for
        later inspection or more advanced repair tools.

        Structural corruption and unsafe paths still fail.
        """
        source = Path(source).expanduser().resolve()
        number = 1
        while True:
            suffix = ' Recovered' if number == 1 else f' Recovered {number}'
            output = source.with_name(source.stem + suffix + source.suffix.lower())
            if not output.exists():
                break
            number += 1
        cls.restore_copy(source, output)
        try:
            return cls.load(output, recover_cosmetic=True)
        except Exception:
            # Never leave behind a misleading partial recovered file.
            output.unlink(missing_ok=True)
            raise

    def close(self):
        # Closing must not delete source assets while a worker is reading.
        with self._save_guard.lock:
            if not self._closed:
                if self._session_dir is not None:
                    from .safe_session import mark_normal_close
                    mark_normal_close(self)
                self._save_guard.closed = True
                self._save_guard.generation += 1
                try:
                    self._temporary.cleanup()
                finally:
                    self._lease.release()
                    if self._origin_lease is not None:
                        self._origin_lease.release()
                        self._origin_lease = None
                    # A staged copy is only disposable after a verified local
                    # history snapshot AND after explicit publishing. Otherwise
                    # it is retained for recovery after an unclean exit.
                    if (self._session_dir is not None and self._session_backed_up
                            and not self._unpublished):
                        shutil.rmtree(self._session_dir, ignore_errors=True)
                    self._closed = True
