"""PublishDialog — prefill, a11y names, options round-trip, menu wiring.

Follows the GUI test conventions: module-scoped offscreen QApplication,
dialogs constructed directly (never exec'd — modal loops don't belong in
tests), and the accessible-name loop assertion the Preferences dialog pins.
"""
import importlib.util

import pytest

_HAS_QT = bool(
    importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5")
)

pytestmark = [
    pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed"),
    pytest.mark.qt,
]

from star.documents.model import Document  # noqa: E402
from star.publish import PublishOptions  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _doc(**kw) -> Document:
    d = Document()
    for k, v in kw.items():
        setattr(d, k, v)
    return d


def _dialog(qapp, doc=None, saved=None):
    from star.gui.publish_dialog import PublishDialog

    return PublishDialog(None, doc or _doc(), saved)


def test_prefills_from_document_metadata(qapp):
    doc = _doc(title="My Paper", metadata={"creator": "A. Student", "lang": "en"})
    dlg = _dialog(qapp, doc)
    assert dlg._title.text() == "My Paper"
    assert dlg._author.text() == "A. Student"
    assert dlg._language.text() == "en"
    dlg.deleteLater()


def test_saved_values_outrank_document(qapp):
    doc = _doc(title="Doc Title")
    dlg = _dialog(
        qapp, doc,
        {"title": "Saved Title", "fmt": "html", "toc": False, "toc_depth": 2},
    )
    assert dlg._title.text() == "Saved Title"
    assert dlg._fmt.currentData() == "html"
    assert dlg._toc.isChecked() is False
    assert dlg._toc_depth.value() == 2
    dlg.deleteLater()


def test_every_field_announces_its_setting(qapp):
    """The Preferences a11y contract: no unnamed field controls."""
    from PyQt6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit

    dlg = _dialog(qapp)
    unnamed = [
        w.__class__.__name__
        for w in dlg.findChildren((QComboBox, QAbstractSpinBox, QLineEdit))
        if not w.accessibleName()
        # A QSpinBox's internal line edit is announced through its parent.
        and not isinstance(w.parent(), QAbstractSpinBox)
    ]
    assert unnamed == []
    dlg.deleteLater()


def test_options_round_trip(qapp):
    dlg = _dialog(qapp)
    dlg._title.setText("T")
    dlg._author.setText("A")
    dlg._language.setText("es")
    dlg._date.setText("2026-08-16")
    dlg._cover.setText("c.png")
    dlg._toc.setChecked(True)
    dlg._toc_depth.setValue(4)
    o = dlg.options()
    assert o == PublishOptions(
        fmt="epub", template="", title="T", author="A", language="es",
        date="2026-08-16", cover_image="c.png", toc=True, toc_depth=4,
    )
    # values_dict feeds a fresh dialog identically (per-doc persistence).
    dlg2 = _dialog(qapp, saved=dlg.values_dict())
    assert dlg2.options() == o
    dlg.deleteLater()
    dlg2.deleteLater()


def test_cover_is_epub_only(qapp):
    dlg = _dialog(qapp)
    assert dlg._cover_row.isEnabled()
    dlg._select_data(dlg._fmt, "html")
    dlg._sync_format_rows()
    assert not dlg._cover_row.isEnabled()
    # And the produced options drop the cover for non-EPUB formats.
    dlg._cover.setText("c.png")
    assert dlg.options().cover_image == ""
    # values_dict still REMEMBERS the path for the next EPUB publish.
    assert dlg.values_dict()["cover_image"] == "c.png"
    dlg.deleteLater()


def test_format_switch_repopulates_templates(qapp, monkeypatch, tmp_path):
    """EPUB↔DOCX switching swaps the template list (CSS vs reference docs)
    while keeping a same-named selection — large-print exists in both worlds."""
    import star.gui.publish_dialog as pd
    import star.publish as publish

    css = tmp_path / "large-print.css"
    css.write_text("body{}", encoding="utf-8")
    ref = tmp_path / "large-print.docx"
    ref.write_bytes(b"stub")
    monkeypatch.setattr(
        pd, "available_templates", lambda: {"large-print": css, "web-only": css}
    )
    monkeypatch.setattr(
        publish, "available_reference_docs", lambda: {"large-print": ref}
    )

    dlg = _dialog(qapp)
    dlg._select_data(dlg._template, "large-print")
    dlg._select_data(dlg._fmt, "docx")
    dlg._on_format_changed()
    names = [dlg._template.itemData(i) for i in range(dlg._template.count())]
    assert names == ["", "large-print"]  # reference docs, not CSS
    assert dlg._template.currentData() == "large-print"  # selection survived
    assert not dlg._cover_row.isEnabled()  # cover stays EPUB-only

    dlg._select_data(dlg._fmt, "epub")
    dlg._on_format_changed()
    names = [dlg._template.itemData(i) for i in range(dlg._template.count())]
    assert "web-only" in names  # CSS list is back
    assert dlg._template.currentData() == "large-print"
    dlg.deleteLater()


def test_publish_menu_action_bound_to_f9(qapp):
    from PyQt6.QtGui import QKeySequence
    from PyQt6.QtWidgets import QApplication  # noqa: F401

    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())
    try:
        acts = [
            a for a in win.findChildren(type(win.menuBar().actions()[0]))
            if a.text().replace("&", "").startswith("Publish")
        ]
        assert acts, "File menu lacks a Publish… action"
        assert any(
            a.shortcut() == QKeySequence("F9") for a in acts
        ), "Publish… is not bound to F9"
    finally:
        win.close()
