"""Prevent release version mismatches when preparing Yomu Note v0.8.6b."""
from pathlib import Path

from yomunote import __version__

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_version_and_windows_upgrade_id():
    # The release contract must match the current source version.
    assert __version__ == '0.8.7c'
    iss = read('PinbuNote_Installer.iss')
    assert '#define MyAppVersion "0.8.7c"' in iss
    assert 'VersionInfoVersion=0.8.7.3' in iss
    assert 'OutputBaseFilename=PinbuNote_Setup_v0.8.7c' in iss
    # Preserve the stable Inno Setup AppId so upgrades use the same installation.
    assert 'AppId={{974AD665-3F47-4CC5-9AAE-0A5F43565469}' in iss
    assert 'PinbuNote_Setup_v0.8.7c.exe' in read('build-installer-windows.ps1')


def test_release_asset_names_agree_with_builders():
    workflow = read('.github/workflows/release.yml')
    for name in (
        'PinbuNote_Setup_v0.8.7c.exe',
        'PinbuNote-0.8.7c-macOS-arm64-unsigned.dmg',
        'PinbuNote-0.8.7c-macOS-x86_64-unsigned.dmg',
    ):
        assert name in workflow
    assert '--draft --prerelease' in workflow
    assert '--notes-file RELEASE_NOTES_v0.8.7c.md' in workflow
    assert 'needs: [windows, macos]' in workflow
    assert 'version="0.8.7c"' in read('scripts/package-macos-dmg.sh')
    assert 'PinbuNote_Setup_v0.8.7c.exe' in read('RELEASE_NOTES_v0.8.7c.md')


def test_readme_keeps_existing_published_installer_live_until_new_one_is_published():
    readme = read('README.md')
    assert 'v0.8.3b' in readme
    assert 'v0.8.6b' in readme
    assert 'Reading View Memory' in readme
    assert 'docs/screenshots/01-interface.png' in readme
    assert 'docs/screenshots/02-ocr.png' in readme
    assert 'docs/screenshots/03-reading-progress.png' in readme
