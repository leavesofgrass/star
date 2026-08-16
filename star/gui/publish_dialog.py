"""PublishDialog — one keyboard-first place for every publishing choice.

The GUI half of the publishing arc (design 2026-08-08): format, stylesheet
template, metadata, cover image, and table-of-contents options in a single
dialog, translated into a :class:`star.publish.PublishOptions` that the
pandoc-backed exporters consume.  The quick File ▸ Export items stay exactly
as they were — this dialog is the full pipeline, they are the bare converter.

Accessibility mirrors the Preferences dialog: every field takes its
accessible name from its form-row label, so a screen reader announces which
setting has focus (the loop in :meth:`_ensure_accessible_names`, pinned by
``tests/test_publish_dialog.py`` exactly like ``test_prefs_a11y``).
"""
from .._runtime import *  # noqa: F401,F403
from ..i18n import tr
from ..publish import PublishOptions, available_templates, resolve_metadata

#: The publish targets.  EPUB and DOCX are the deliverable formats; HTML here
#: means ONE portable file (--embed-resources), unlike the bare quick export.
_FORMATS: "List[Tuple[str, str]]" = [
    ("EPUB", "epub"),
    ("DOCX", "docx"),
    ("HTML", "html"),
]

#: Combo entry meaning "no stylesheet — Pandoc's default look".
_NO_TEMPLATE = ""


class PublishDialog(QDialog):
    """Collect a :class:`PublishOptions` for the open document.

    *saved* is the per-document value dict from a previous session (or ``{}``);
    the dialog prefills from it first, then from the document's own metadata,
    so re-publishing a document remembers every choice.
    """

    def __init__(self, parent, document, saved: "Optional[Dict[str, Any]]" = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Publish"))
        self._document = document
        saved = dict(saved or {})

        form = QFormLayout()

        self._fmt = QComboBox()
        for label, value in _FORMATS:
            self._fmt.addItem(label, value)
        form.addRow(tr("Format:"), self._fmt)

        # Populated per-format by _populate_templates(): CSS stylesheets for
        # EPUB/HTML, --reference-doc .docx files for DOCX.
        self._template = QComboBox()
        form.addRow(tr("Stylesheet template:"), self._template)

        # Metadata rows prefill from the document via the same resolution the
        # export itself uses — what the user sees is what pandoc will get.
        meta = resolve_metadata(document, PublishOptions())
        self._title = QLineEdit(saved.get("title") or meta["title"])
        form.addRow(tr("Title:"), self._title)
        self._author = QLineEdit(saved.get("author") or meta["author"])
        form.addRow(tr("Author:"), self._author)
        self._language = QLineEdit(saved.get("language") or meta["language"])
        self._language.setPlaceholderText(tr("e.g. en, es, fr"))
        form.addRow(tr("Language:"), self._language)
        self._date = QLineEdit(saved.get("date") or meta["date"])
        self._date.setPlaceholderText(tr("e.g. 2026-08-16"))
        form.addRow(tr("Date:"), self._date)

        cover_row = QWidget()
        cover_box = QHBoxLayout(cover_row)
        cover_box.setContentsMargins(0, 0, 0, 0)
        self._cover = QLineEdit(saved.get("cover_image", ""))
        self._cover.setAccessibleName(tr("Cover image file"))
        cover_box.addWidget(self._cover)
        browse = QPushButton(tr("Browse…"))
        browse.clicked.connect(self._pick_cover)
        cover_box.addWidget(browse)
        form.addRow(tr("Cover image (EPUB):"), cover_row)
        self._cover_row = cover_row

        self._toc = QCheckBox(tr("Include a table of contents"))
        self._toc.setChecked(bool(saved.get("toc", True)))
        form.addRow("", self._toc)
        self._toc_depth = QSpinBox()
        self._toc_depth.setRange(1, 6)
        self._toc_depth.setValue(int(saved.get("toc_depth", 3)))
        form.addRow(tr("Contents depth:"), self._toc_depth)

        # Restore the remembered format, fill the template list for it, then
        # restore the remembered template and keep both format-dependent rows
        # (template list + EPUB-only cover) in sync with later changes.
        self._select_data(self._fmt, saved.get("fmt", "epub"))
        self._populate_templates()
        self._select_data(self._template, saved.get("template", _NO_TEMPLATE))
        self._fmt.currentIndexChanged.connect(self._on_format_changed)
        self._sync_format_rows()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Publish"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)
        self._ensure_accessible_names()

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _on_format_changed(self, *_a) -> None:
        self._populate_templates()
        self._sync_format_rows()

    def _populate_templates(self) -> None:
        """Fill the template combo for the current format, keeping the
        selection when the same name exists in the new list (large-print
        exists as both a stylesheet and a reference doc, so switching
        EPUB ↔ DOCX preserves the intent)."""
        from ..publish import available_reference_docs

        fmt = str(self._fmt.currentData())
        current = str(self._template.currentData() or _NO_TEMPLATE)
        names = sorted(
            available_reference_docs() if fmt == "docx" else available_templates()
        )
        self._template.blockSignals(True)
        self._template.clear()
        self._template.addItem(tr("No template (Pandoc default)"), _NO_TEMPLATE)
        for name in names:
            self._template.addItem(name, name)
        self._select_data(self._template, current)
        self._template.blockSignals(False)

    def _sync_format_rows(self, *_a) -> None:
        """The cover image applies to EPUB only — disable it elsewhere."""
        self._cover_row.setEnabled(self._fmt.currentData() == "epub")

    def _pick_cover(self) -> None:
        path, _flt = QFileDialog.getOpenFileName(
            self,
            tr("Choose Cover Image"),
            self._cover.text() or "",
            tr("Images (*.png *.jpg *.jpeg *.gif *.svg);;All Files (*)"),
        )
        if path:
            self._cover.setText(path)

    def _ensure_accessible_names(self) -> None:
        """Name every field from its form-row label (Preferences convention)."""
        try:  # PyQt6 / PyQt5 spin-box base + form-layout role enums
            from PyQt6.QtWidgets import QAbstractSpinBox, QFormLayout
            _LABEL = QFormLayout.ItemRole.LabelRole
            _FIELD = QFormLayout.ItemRole.FieldRole
        except ImportError:  # PyQt5
            from PyQt5.QtWidgets import QAbstractSpinBox, QFormLayout  # type: ignore
            _LABEL = QFormLayout.LabelRole  # type: ignore[attr-defined]
            _FIELD = QFormLayout.FieldRole  # type: ignore[attr-defined]

        def _clean(text: str) -> str:
            return text.replace("&", "").rstrip(":： ").strip()

        for form in self.findChildren(QFormLayout):
            for row in range(form.rowCount()):
                field_item = form.itemAt(row, _FIELD)
                if field_item is None:
                    continue
                field = field_item.widget()
                if not isinstance(
                    field, (QComboBox, QAbstractSpinBox, QLineEdit)
                ):
                    continue
                if field.accessibleName():
                    continue
                label_item = form.itemAt(row, _LABEL)
                label = label_item.widget() if label_item is not None else None
                text = _clean(label.text()) if label is not None else ""
                if text:
                    field.setAccessibleName(text)

    # ── results ─────────────────────────────────────────────────────────────

    def options(self) -> PublishOptions:
        """The dialog's current state as the pipeline's options object."""
        return PublishOptions(
            fmt=str(self._fmt.currentData()),
            template=str(self._template.currentData() or ""),
            title=self._title.text().strip(),
            author=self._author.text().strip(),
            language=self._language.text().strip(),
            date=self._date.text().strip(),
            cover_image=(
                self._cover.text().strip()
                if self._fmt.currentData() == "epub"
                else ""
            ),
            toc=self._toc.isChecked(),
            toc_depth=self._toc_depth.value(),
        )

    def values_dict(self) -> "Dict[str, Any]":
        """The state as a plain dict for per-document settings persistence."""
        o = self.options()
        return {
            "fmt": o.fmt,
            "template": o.template,
            "title": o.title,
            "author": o.author,
            "language": o.language,
            "date": o.date,
            "cover_image": self._cover.text().strip(),
            "toc": o.toc,
            "toc_depth": o.toc_depth,
        }
