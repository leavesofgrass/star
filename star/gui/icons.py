"""Hand-drawn vector toolbar icons (QPainter, theme-tinted, no asset files).

``make_icon(name)`` returns a crisp monochrome ``QIcon`` drawn from primitives in
a 22-px box, tinted with the chrome text colour so it reads on any platform's
toolbar.  Keeps star asset-free — no PNG/SVG files to bundle in the wheel/pyz.
Unknown names yield a small neutral dot so the toolbar never breaks.

Modelled on qcell's gui/icons.py for a consistent look across the apps.  The
toolbar shows icons only; each QAction keeps a descriptive text label (its
accessible name for screen readers) plus a tooltip — so simplifying the visuals
never costs accessibility.
"""
from __future__ import annotations

try:  # PyQt6 (base dependency)
    from PyQt6.QtCore import QPointF, QRectF, Qt
    from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
    from PyQt6.QtWidgets import QApplication
except ImportError:  # PyQt5 fallback
    from PyQt5.QtCore import QPointF, QRectF, Qt  # type: ignore
    from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap  # type: ignore
    from PyQt5.QtWidgets import QApplication  # type: ignore

# Resolve the enum spellings once (PyQt6 scoped enums vs PyQt5 flat).
try:
    _AA = QPainter.RenderHint.Antialiasing
    _TRANSPARENT = Qt.GlobalColor.transparent
    _ROUND_JOIN = Qt.PenJoinStyle.RoundJoin
    _ROUND_CAP = Qt.PenCapStyle.RoundCap
    _NO_BRUSH = Qt.BrushStyle.NoBrush
    _ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
except AttributeError:  # PyQt5
    _AA = QPainter.Antialiasing  # type: ignore
    _TRANSPARENT = Qt.transparent  # type: ignore
    _ROUND_JOIN = Qt.RoundJoin  # type: ignore
    _ROUND_CAP = Qt.RoundCap  # type: ignore
    _NO_BRUSH = Qt.NoBrush  # type: ignore
    _ALIGN_CENTER = Qt.AlignCenter  # type: ignore

_SIZE = 22


def _icon_color() -> QColor:
    app = QApplication.instance()
    if app is not None:
        return app.palette().windowText().color()
    return QColor("#c8d0da")


def _accent() -> QColor:
    c = _icon_color()
    return QColor(c.red(), c.green(), c.blue(), 70)  # faint fill for bands


def _poly(p, pts, fill=True):
    """Draw a closed polygon from (x, y) points — filled or stroked."""
    path = QPainterPath()
    path.moveTo(pts[0][0], pts[0][1])
    for x, y in pts[1:]:
        path.lineTo(x, y)
    path.closeSubpath()
    if fill:
        p.fillPath(path, _icon_color())
    else:
        p.drawPath(path)


# ── shared sub-glyphs ────────────────────────────────────────────────────────

def _tri_left(p, cx, cy, s=2.8):
    _poly(p, [(cx + s, cy - s), (cx - s, cy), (cx + s, cy + s)])


def _tri_right(p, cx, cy, s=2.8):
    _poly(p, [(cx - s, cy - s), (cx + s, cy), (cx - s, cy + s)])


def _replay(p, cx, cy, r=2.6):
    p.drawArc(QRectF(cx - r, cy - r, 2 * r, 2 * r), 60 * 16, 280 * 16)
    _tri_right(p, cx + r, cy - r + 0.5, 1.7)  # arrowhead


def _u_sentence(p):
    p.drawLine(QPointF(8, 11), QPointF(16, 11))   # one line of text


def _u_paragraph(p):
    for y in (8, 11, 14):
        p.drawLine(QPointF(8, y), QPointF(16, y))  # a block of lines


def _u_heading(p):
    p.drawLine(QPointF(9, 7), QPointF(9, 15))      # H
    p.drawLine(QPointF(15, 7), QPointF(15, 15))
    p.drawLine(QPointF(9, 11), QPointF(15, 11))


def _nav(unit, direction):
    """Compose a navigation glyph: centred *unit* + a direction badge."""
    def draw(p):
        unit(p)
        if direction == "prev":
            _tri_left(p, 5, 11)
        elif direction == "next":
            _tri_right(p, 17.2, 11)
        elif direction == "replay":
            _replay(p, 11, 4.4)
    return draw


# ── individual glyphs ────────────────────────────────────────────────────────

def _open(p):
    _poly(p, [(4, 7), (8, 7), (9.5, 9), (18, 9), (18, 17), (4, 17)], fill=False)


def _url(p):
    p.drawEllipse(QRectF(4, 4, 14, 14))
    p.drawEllipse(QRectF(8.5, 4, 5, 14))           # meridian
    p.drawLine(QPointF(4, 11), QPointF(18, 11))    # equator


def _play_pause(p):
    _poly(p, [(5, 5), (5, 17), (11, 11)])               # play triangle
    p.fillRect(QRectF(13, 5, 2.2, 12), _icon_color())   # pause bars
    p.fillRect(QRectF(16.2, 5, 2.2, 12), _icon_color())


def _stop(p):
    p.fillRect(QRectF(6, 6, 10, 10), _icon_color())


def _chevrons(p, direction):
    xs = (8, 13) if direction == "right" else (14, 9)
    tip = 3 if direction == "right" else -3
    for x in xs:
        path = QPainterPath()
        path.moveTo(x, 6)
        path.lineTo(x + tip, 11)
        path.lineTo(x, 16)
        p.drawPath(path)


def _slower(p):
    _chevrons(p, "left")


def _faster(p):
    _chevrons(p, "right")


def _voice(p):
    _poly(p, [(4, 9), (7, 9), (10, 6), (10, 16), (7, 13), (4, 13)])   # speaker cone
    p.drawArc(QRectF(10, 6, 6, 10), -60 * 16, 120 * 16)              # sound waves
    p.drawArc(QRectF(11, 3, 9, 16), -55 * 16, 110 * 16)


def _speech_cursor(p):
    p.drawLine(QPointF(5, 11), QPointF(13, 11))      # line of text
    p.drawLine(QPointF(9, 7), QPointF(9, 15))        # caret
    p.drawEllipse(QPointF(16, 11), 2.2, 2.2)         # the reading dot


def _copy(p):
    p.drawRoundedRect(QRectF(5, 4, 8, 10), 1.2, 1.2)
    p.drawRoundedRect(QRectF(9, 8, 8, 10), 1.2, 1.2)


def _highlight(p):
    p.fillRect(QRectF(4, 14, 14, 3), _accent())      # highlighted band
    _poly(p, [(6, 12), (13, 5), (16, 8), (9, 15)], fill=False)  # marker nib


def _clear_highlight(p):
    p.fillRect(QRectF(4, 14, 14, 3), _accent())
    p.drawLine(QPointF(6, 5), QPointF(16, 12))       # X over it
    p.drawLine(QPointF(16, 5), QPointF(6, 12))


def _edit(p):
    _poly(p, [(5, 17), (6.5, 13), (14, 5.5), (16.5, 8), (9, 15.5)], fill=False)  # pencil
    p.drawLine(QPointF(13, 6.5), QPointF(15.5, 9))


def _save(p):
    p.drawRoundedRect(QRectF(4, 4, 14, 14), 1.5, 1.5)
    p.drawRect(QRectF(7, 4, 8, 4))                   # slider
    p.drawRect(QRectF(7, 12, 8, 6))                  # label


def _theme(p):
    p.drawEllipse(QRectF(5, 5, 12, 12))
    path = QPainterPath()                            # half-filled (day/night)
    path.moveTo(11, 5)
    path.arcTo(QRectF(5, 5, 12, 12), 90, -180)
    path.closeSubpath()
    p.fillPath(path, _icon_color())


def _contents(p):
    for i, y in enumerate((6, 11, 16)):
        p.fillRect(QRectF(4, y - 1, 2, 2), _icon_color())   # bullet
        p.drawLine(QPointF(8, y), QPointF(18 - i, y))       # row


def _notes(p):
    _poly(p, [(5, 4), (14, 4), (17, 7), (17, 18), (5, 18)], fill=False)  # page
    p.drawLine(QPointF(14, 4), QPointF(14, 7))       # folded corner
    p.drawLine(QPointF(14, 7), QPointF(17, 7))
    p.drawLine(QPointF(8, 11), QPointF(14, 11))      # text lines
    p.drawLine(QPointF(8, 14), QPointF(13, 14))


def _add_note(p):
    _poly(p, [(5, 4), (12, 4), (12, 11), (5, 11)], fill=False)  # small page
    p.drawLine(QPointF(7, 7), QPointF(10, 7))
    p.drawLine(QPointF(7, 9), QPointF(10, 9))
    p.drawLine(QPointF(14, 14), QPointF(14, 19))     # plus
    p.drawLine(QPointF(11.5, 16.5), QPointF(16.5, 16.5))


def _level(p):
    for i, h in enumerate((4, 8, 12)):               # ascending bars
        x = 5 + i * 4.5
        p.fillRect(QRectF(x, 17 - h, 3, h), _icon_color())


def _glyph_text(p, ch, pt=13):
    f = QFont()
    f.setPointSize(pt)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(0, 0, _SIZE, _SIZE), _ALIGN_CENTER, ch)


def _font(p):
    _glyph_text(p, "A", 14)


def _help(p):
    p.drawEllipse(QRectF(4, 4, 14, 14))
    _glyph_text(p, "?", 11)


def _quit(p):
    p.drawArc(QRectF(5, 5, 12, 12), 70 * 16, 320 * 16)   # power ring (gap at top)
    p.drawLine(QPointF(11, 4), QPointF(11, 10))          # power stem


_GLYPHS = {
    "open": _open, "url": _url,
    "play_pause": _play_pause, "stop": _stop, "slower": _slower, "faster": _faster,
    "prev_sentence": _nav(_u_sentence, "prev"),
    "replay_sentence": _nav(_u_sentence, "replay"),
    "next_sentence": _nav(_u_sentence, "next"),
    "prev_paragraph": _nav(_u_paragraph, "prev"),
    "replay_paragraph": _nav(_u_paragraph, "replay"),
    "next_paragraph": _nav(_u_paragraph, "next"),
    "prev_heading": _nav(_u_heading, "prev"),
    "next_heading": _nav(_u_heading, "next"),
    "voice": _voice, "speech_cursor": _speech_cursor,
    "copy": _copy, "highlight": _highlight, "clear_highlight": _clear_highlight,
    "edit": _edit, "save": _save,
    "theme": _theme, "contents": _contents, "notes": _notes, "add_note": _add_note,
    "level": _level, "font": _font, "help": _help, "quit": _quit,
}


def make_icon(name: str, size: int = _SIZE) -> QIcon:
    color = _icon_color()
    pm = QPixmap(size, size)
    pm.fill(_TRANSPARENT)
    p = QPainter(pm)
    p.setRenderHint(_AA, True)
    pen = QPen(color)
    pen.setWidthF(1.6)
    pen.setJoinStyle(_ROUND_JOIN)
    pen.setCapStyle(_ROUND_CAP)
    p.setPen(pen)
    p.setBrush(_NO_BRUSH)
    glyph = _GLYPHS.get(name)
    if glyph is not None:
        glyph(p)
    else:
        p.drawEllipse(QPointF(11, 11), 2, 2)
    p.end()
    return QIcon(pm)
