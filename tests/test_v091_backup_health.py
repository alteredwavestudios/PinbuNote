"""Pinbu v0.9.1: optional independent second backups and honest health reports."""
from pathlib import Path

import pytest

from yomunote.notebook import Notebook
from yomunote.backup_health import (
    SecondaryBackupError, PrimaryBackupError, backup_to_destinations, distinct_backup_paths,
    inspect_store, verify_history,
)
from yomunote.safe_backup import restore_snapshot, list_snapshots


def make_notebook(tmp_path):
    nb = Notebook.create(tmp_path / 'cloud', 'Sociology', extension='.pinbunote')
    path = nb.path
    nb.close()
    return Notebook.open_session(path, tmp_path / 'working')


def test_optional_secondary_backs_up_independently_and_deduplicates(tmp_path):
    session = make_notebook(tmp_path)
    try:
        project = session.project(session.active_id)
        original = project.asset_path('originals/notes.pdf')
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(b'%PDF-1.4\nSample immutable teaching slides')
        project.pages.append({'id':'p1','kind':'pdf','title':'Intro',
                              'source':'originals/notes.pdf',
                              'render_source':'originals/notes.pdf', 'source_page': 1})
        project.notes_html = '<p>First</p>'
        project.save()
        first = tmp_path / 'internal_backup'
        second = tmp_path / 'external_backup'
        second.mkdir()
        a,b = backup_to_destinations(session, first, second, force=True, reason='close')
        assert a and b and a.is_file() and b.is_file() and a != b
        first_health = inspect_store(first, session.identifier, session.name, session.display_path)
        second_health = inspect_store(second, session.identifier, session.name, session.display_path)
        assert first_health.snapshot_count == second_health.snapshot_count == 1
        assert first_health.marker != second_health.marker
        assert verify_history(Path(first_health.marker)) == (1, 1)
        assert verify_history(Path(second_health.marker)) == (1, 1)
        assert verify_history(Path(first_health.marker), all_snapshots=True) == (1, 1)
        project.notes_html = '<p>Second</p>'
        project.save()
        a2,b2 = backup_to_destinations(session, first, second)
        assert a2 and b2
        one = list_snapshots(Path(first_health.marker))
        two = list_snapshots(Path(second_health.marker))
        assert len(one) == len(two) == 2
        # Each root has exactly one asset blob for the unchanged PDF.
        for health in (first_health, second_health):
            root = Path(health.marker).parent
            assert len(list((root / 'assets').glob('*/*.bin'))) == 1
            assert verify_history(Path(health.marker), all_snapshots=True) == (2, 2)
        dest = tmp_path / 'restored.pinbunote'
        restore_snapshot(Path(second_health.marker), dest, snapshot_id=two[-1]['id'])
        loaded = Notebook.load(dest)
        assert loaded.project(loaded.active_id).notes_html == '<p>First</p>'
        loaded.close()
    finally:
        session.close()


def test_disabled_secondary_creates_only_primary(tmp_path):
    nb = make_notebook(tmp_path)
    try:
        a,b = backup_to_destinations(nb, tmp_path/'primary', force=True)
        assert a and b is None
        assert not (tmp_path/'other').exists()
    finally:
        nb.close()


def test_second_backup_failure_does_not_remove_primary(tmp_path, monkeypatch):
    nb = make_notebook(tmp_path)
    primary, secondary = tmp_path/'primary', tmp_path/'secondary'
    secondary.mkdir()
    original = nb.safesave_backup
    def fail_secondary(directory, **kwargs):
        if Path(directory) == secondary:
            raise PermissionError('Second disk unplugged')
        return original(directory, **kwargs)
    monkeypatch.setattr(nb, 'safesave_backup', fail_secondary)
    try:
        with pytest.raises(SecondaryBackupError, match='second backup FAILED') as exc:
            backup_to_destinations(nb, primary, secondary, force=True, reason='close')
        assert exc.value.primary_snapshot.is_file()
        assert inspect_store(primary, nb.identifier, nb.name, nb.display_path).snapshot_count == 1
        assert verify_history(exc.value.primary_snapshot.parent.parent.parent) == (1,1)
    finally:
        nb.close()


def test_same_or_nested_roots_blocked_without_writing(tmp_path):
    a=tmp_path/'a'
    assert not distinct_backup_paths(a,a)
    assert not distinct_backup_paths(a,a/'sub')
    assert not distinct_backup_paths(a/'sub',a)
    assert distinct_backup_paths(a,tmp_path/'other')
    nb=make_notebook(tmp_path)
    try:
        with pytest.raises(ValueError,match='separate'):
            backup_to_destinations(nb,a,a/'sub')
        assert not a.exists()
    finally:
        nb.close()


def test_health_checks_detect_asset_damage(tmp_path):
    nb=make_notebook(tmp_path)
    try:
        root=tmp_path/'backups'
        snap,_ = backup_to_destinations(nb, root, force=True)
        info=inspect_store(root, nb.identifier, nb.name, nb.display_path)
        assert info.marker and info.latest and info.snapshot_count==1
        assert verify_history(Path(info.marker))==(1,1)
        # Removing the backing object must not be reported as 'verified'.
        obj=next((Path(info.marker).parent/'data'/'objects').glob('*/*'))
        obj.unlink()
        with pytest.raises(Exception):
            verify_history(Path(info.marker))
    finally:
        nb.close()


def test_source_has_discreet_footer_health_and_settings_controls():
    src = (Path(__file__).resolve().parents[1]/'yomunote'/'window.py').read_text(encoding='utf-8')
    assert "QLabel('Autosave · —'" in src
    assert 'self.statusBar().addPermanentWidget(self._autosave_footer)' in src
    assert 'secondaryBackupEnabled' in src
    assert 'secondaryBackupDirectory' in src
    assert 'SafeSave Health & Verify Backups…' in src
    assert "self._backup_to_both(notebook, force=True, reason='close')" in src
    assert "self._backup_to_both(self.notebook, reason='automatic')" in src


def test_primary_backup_disk_full_still_attempts_secondary(tmp_path, monkeypatch):
    nb=make_notebook(tmp_path)
    primary,secondary=tmp_path/'primary',tmp_path/'secondary'
    secondary.mkdir()
    original=nb.safesave_backup
    def fail_primary(directory, **kwargs):
        if Path(directory)==primary:
            raise OSError(28,'No space left on device')
        return original(directory, **kwargs)
    monkeypatch.setattr(nb,'safesave_backup',fail_primary)
    try:
        with pytest.raises(PrimaryBackupError,match='PRIMARY local backup FAILED') as error:
            backup_to_destinations(nb,primary,secondary,force=True,reason='close')
        assert error.value.secondary_snapshot.is_file()
        h=inspect_store(secondary,nb.identifier,nb.name,nb.display_path)
        assert h.snapshot_count==1
        assert verify_history(Path(h.marker))==(1,1)
    finally:
        nb.close()


def test_missing_secondary_drive_is_reported_never_recreated(tmp_path):
    nb=make_notebook(tmp_path)
    primary=tmp_path/'primary'
    missing=tmp_path/'unplugged_drive'
    try:
        with pytest.raises(SecondaryBackupError,match='second backup FAILED') as err:
            backup_to_destinations(nb,primary,missing,force=True,reason='close')
        assert err.value.primary_snapshot.is_file()
        assert not missing.exists(), 'Never recreate a disappeared removable drive path'
    finally:
        nb.close()
