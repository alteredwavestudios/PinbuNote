"""Paint a tiny notebook-bookmark ribbon without caching or changing a page."""
from __future__ import annotations
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen


def paint_bookmark_ribbon(painter, x: float, y: float, accent, scale=1.0):
    """A distinct folded ribbon that remains visible over light or dark pages."""
    width, height = 12.0 * scale, 17.0 * scale
    path = QPainterPath(QPointF(x, y))
    path.lineTo(x + width, y)
    path.lineTo(x + width, y + height)
    path.lineTo(x + width*.5, y + height*.70)
    path.lineTo(x, y + height)
    path.closeSubpath()
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor('#FFFFFF'), 1.7*scale))
    painter.setBrush(QColor(accent))
    painter.drawPath(path)
    painter.restore()
