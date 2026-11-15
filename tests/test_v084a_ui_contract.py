"""No-GUI checks ensuring transactional page moves are wired to shared Undo."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOW = (ROOT / 'yomunote' / 'window.py').read_text(encoding='utf-8')
CODE = ast.parse(WINDOW)
MAIN = next(node for node in CODE.body if isinstance(node, ast.ClassDef)
            and node.name == 'MainWindow')


def method(name):
    return next(node for node in MAIN.body if isinstance(node, ast.FunctionDef)
                and node.name == name)


def test_cross_tab_source_is_atomic_and_shared_undo():
    source = ast.get_source_segment(WINDOW, method('_transfer_tab_pages'))
    assert 'return_change=True' in source
    assert 'self._save_panes_in_one_commit(' in source  # flush both tabs once
    assert 'self.notebook.transfer_pages(' in source
    assert 'self._notebook_history.record_applied(CallbackAction(' in source
    assert 'change.estimated_bytes' in source
    assert 'self._replay_tab_page_transfer' in source


def test_replay_is_one_notebook_wide_change_without_editor_reload():
    replay = ast.get_source_segment(WINDOW, method('_replay_tab_page_transfer'))
    refresh = ast.get_source_segment(WINDOW, method('_refresh_transferred_tabs'))
    assert 'self.notebook.replay_page_transfer(' in replay
    assert 'self._refresh_transferred_tabs(' in replay
    assert 'pane.project = self.notebook.project(' in refresh
    assert 'pane.load_pages()' in refresh
    assert '.setHtml(' not in refresh + replay


def test_production_installer_guards_unchanged():
    installer = (ROOT / 'YomuNote_v050_Installer.iss').read_text()
    build = (ROOT / 'build-installer-windows.ps1').read_text()
    assert 'AppId={{974AD665-3F47-4CC5-9AAE-0A5F43565469}' in installer
    assert '[Run]' not in '\n'.join(line.strip() for line in installer.splitlines()
                                      if not line.lstrip().startswith(';'))
    assert 'Start-Process -FilePath $output -ArgumentList $installArgs -Wait -PassThru' in build
    assert 'verify_windows_frozen.py --dist $installDir' in build
    assert 'verify_ocr_bundle.py --target windows' in build


def test_safe_development_launcher_keeps_production_prefs():
    script = (ROOT / 'RUN_DEV_SAFELY.cmd').read_text()
    assert 'set YOMU_INTEGRATION_DEV=1' in script
    assert 'call run-windows.bat' in script
