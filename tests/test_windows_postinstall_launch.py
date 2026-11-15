"""Installer first launch must happen from Start, not Inno Setup's context."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_windows_setup_does_not_launch_gui_postinstall():
    source = (ROOT / 'PinbuNote_Installer.iss').read_text(encoding='utf-8')
    match = re.search(r'(?ms)^\[Run\]\s*\n(.*?)(?=^\[|\Z)', source)
    if match:
        active = [line.strip() for line in match.group(1).splitlines()
                  if line.strip() and not line.lstrip().startswith(';')]
        assert not any('Yomu Note' in line or 'MyAppExeName' in line for line in active)
    assert 'Name: "{group}\\{#MyAppName}"' in source
    assert 'AppId={{974AD665-3F47-4CC5-9AAE-0A5F43565469}' in source


def test_windows_instructions_explain_manual_first_launch():
    install = (ROOT / 'docs' / 'INSTALL.md').read_text(encoding='utf-8')
    assert 'close the Setup wizard' in install
    assert 'Windows Start menu' in install
