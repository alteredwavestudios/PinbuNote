from pathlib import Path

from PySide6.QtCore import QDir

import yomunote.pinbuboard.web as web


def test_python_resource_fallback_registers_frontend(monkeypatch):
    """The playable bundle remains loadable when binary RCC is unavailable."""
    monkeypatch.setattr(web, "_resource_candidates", lambda: [])
    assert web._load_resources()
    assert QDir(":/pinbu-playable").exists()


def test_source_bundle_is_inside_repository():
    assert (Path(web.SOURCE_ROOT) / "frontend/pinbuboard/board.rcc").is_file()
    assert (Path(web.SOURCE_ROOT) / "frontend/pinbuboard/board_resources.py").is_file()
