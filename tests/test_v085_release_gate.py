"""v0.8.6b release-gate checks for upgrade-safe packaging."""
from pathlib import Path
from yomunote import __version__

ROOT=Path(__file__).resolve().parents[1]
read=lambda name:(ROOT/name).read_text(encoding='utf-8')


def test_release_version_and_v5_compatibility():
    # The release contract must match the current source version.
    assert __version__ == '1.0'
    assert 'NOTEBOOK_VERSION = 7' in read('yomunote/notebook.py')


def test_windows_sqlite_fix_ocr_and_upgrader_identity():
    iss=read('PinbuNote_Installer.iss')
    assert 'AppId={{974AD665-3F47-4CC5-9AAE-0A5F43565469}' in iss
    assert 'VersionInfoVersion=1.0.0.0' in iss
    assert 'OutputBaseFilename=PinbuNote_Setup_v{#MyAppVersion}' in iss
    assert not any(line.strip().lower()=='[run]' for line in iss.splitlines())
    builder=read('build-installer-windows.ps1')
    assert 'Start-Process -FilePath $output' in builder
    assert 'verify_windows_frozen.py --dist $installDir' in builder
    assert 'verify_ocr_bundle.py' in builder
    assert 'sqlite3.dll' in read('scripts/verify_windows_frozen.py')


def test_release_workflow_is_draft_and_asset_consistent():
    w=read('.github/workflows/release.yml')
    for asset in ('PinbuNote_Setup_v${version}.exe',
                  'PinbuNote-${version}-macOS-arm64-unsigned.dmg'):
        assert asset in w
    assert 'macOS-x86_64-unsigned.dmg' not in w
    assert 'RELEASE_NOTES_v1.0.md' in w
    assert '--verify-tag --draft --prerelease' in w
    assert 'needs: [windows, macos]' in w
    assert 'from yomunote import __version__' in read('scripts/package-macos-dmg.sh')
