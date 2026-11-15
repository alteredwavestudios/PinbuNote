"""Native Qt smoke checks; skipped where the GUI runtime is unavailable."""
from pathlib import Path
import pytest

QtWidgets = pytest.importorskip('PySide6.QtWidgets')
QtGui = pytest.importorskip('PySide6.QtGui')
from yomunote.window import ImageCanvas


def test_short_page_can_scroll_past_top_without_moving_annotations(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    path = tmp_path / 'slide.png'
    image = QtGui.QImage(800, 450, QtGui.QImage.Format.Format_RGB888)
    image.fill(QtGui.QColor('white'))
    assert image.save(str(path))
    canvas = ImageCanvas()
    canvas.resize(1000, 900)
    canvas.show()
    app.processEvents()
    assert canvas.show_image(path)
    app.processEvents()
    assert canvas.canvas_scene.sceneRect().top() == 0
    original_page_bounds = canvas._page_bounds()
    canvas.set_extra_vertical_scroll(True)
    app.processEvents()
    assert canvas.canvas_scene.sceneRect().top() < 0
    assert canvas._page_bounds() == original_page_bounds
    canvas.centre_page_vertically()
    app.processEvents()
    position = canvas.mapFromScene(original_page_bounds.center())
    assert abs(position.y() - canvas.viewport().height() / 2) < 15
    canvas.set_extra_vertical_scroll(False)
    app.processEvents()
    assert canvas.canvas_scene.sceneRect().top() == 0
    canvas.close()
