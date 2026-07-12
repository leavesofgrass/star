"""AutosaveMixin — periodic autosave + crash recovery for in-progress edits.

While the user is editing (edit mode) with unsaved changes, star writes a
recovery snapshot of the live editor buffer to ``<config>/recovery/`` every few
seconds.  If star is quit or crashes before the work is saved, the snapshot
survives; on the next launch star offers to recover it.  This matters most for
brand-new **Untitled** documents, which have no file on disk to fall back to.

Snapshots are cleared the moment the work is safely persisted (Ctrl+S) or the
user deliberately leaves edit mode (finish / discard) — so a recovery prompt
only ever appears for work that was genuinely lost.

Design notes (teardown safety):
 * The autosave QTimer is stopped in ``closeEvent`` alongside the other periodic
   timers, so a closed window never fires it into a half-destroyed object.
 * Every tick is a small, main-thread synchronous file write — no worker thread
   to race Qt teardown.
 * The pure read/write/scan helpers take no Qt objects, so they unit-test
   without a QApplication.

Mixed into StarWindow; operates on the shared editor + document state.
"""
from .._runtime import *  # noqa: F401,F403  (Qt classes: QTimer, QMessageBox, …)

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .._runtime import _CFG_ROOT, APP_VERSION
from ..documents import Document
from ..i18n import tr
from .a11y import announce


def _recovery_dir() -> Path:
    """Directory holding recovery snapshots (created on demand)."""
    return _CFG_ROOT / "recovery"


def _snapshot_key(doc_path: str, fallback_id: str) -> str:
    """Stable filename stem for a document's recovery snapshot.

    A saved document keys off a hash of its absolute path (so re-editing the
    same file reuses one snapshot); an Untitled document keys off a per-window
    id so concurrent windows don't collide."""
    if doc_path:
        h = hashlib.sha1(os.path.abspath(doc_path).encode("utf-8", "replace"))
        return "doc-" + h.hexdigest()[:16]
    return "untitled-" + fallback_id


def _write_snapshot(path: Path, payload: Dict[str, Any]) -> bool:
    """Write *payload* as JSON to *path* (atomic-ish via a temp file). Best-effort."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError:
        return False


def _scan_snapshots(directory: Path) -> List[Dict[str, Any]]:
    """Load every valid recovery snapshot in *directory* that still represents
    unsaved work.

    A snapshot whose original file already contains the recovered text is stale
    (the work was saved) and is skipped.  Returns dicts with an added ``_file``
    key pointing at the snapshot path."""
    out: List[Dict[str, Any]] = []
    if not directory.exists():
        return out
    for f in sorted(directory.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or "markdown" not in data:
            continue
        orig = str(data.get("path") or "")
        if orig:
            try:
                if Path(orig).read_text(encoding="utf-8") == data.get("markdown"):
                    # Already saved — the snapshot is stale; clean it up.
                    f.unlink(missing_ok=True)
                    continue
            except OSError:
                pass  # original missing/unreadable → still offer recovery
        data["_file"] = str(f)
        out.append(data)
    return out


class AutosaveMixin:
    _AUTOSAVE_INTERVAL_MS = 20000  # 20 s between snapshots while dirty

    # ── lifecycle ──────────────────────────────────────────────────────────
    def _autosave_init(self) -> None:
        """Create the autosave timer (idempotent). Call once at construction."""
        if getattr(self, "_autosave_timer", None) is not None:
            return
        self._autosave_id = uuid.uuid4().hex[:12]
        try:
            self._autosave_timer = QTimer(self)
            self._autosave_timer.setInterval(self._AUTOSAVE_INTERVAL_MS)
            self._autosave_timer.timeout.connect(self._autosave_tick)
        except Exception:  # noqa: BLE001 — no Qt in a headless unit test
            self._autosave_timer = None

    def _autosave_start(self) -> None:
        """Begin autosaving (called when entering edit mode)."""
        t = getattr(self, "_autosave_timer", None)
        if t is not None and not getattr(self, "_closing", False):
            try:
                t.start()
            except Exception:  # noqa: BLE001
                pass

    def _autosave_stop(self, *, clear: bool = True) -> None:
        """Stop autosaving; when *clear* also delete this doc's snapshot.

        Called on every clean exit from edit mode (finish / discard / save-and-
        leave) — the work is either on disk or intentionally gone, so the
        snapshot must not linger and trigger a false recovery prompt."""
        t = getattr(self, "_autosave_timer", None)
        if t is not None:
            try:
                t.stop()
            except Exception:  # noqa: BLE001
                pass
        if clear:
            self._autosave_clear()

    def _autosave_snapshot_path(self) -> Path:
        doc_path = getattr(self.doc, "path", "") if getattr(self, "doc", None) else ""
        key = _snapshot_key(doc_path, getattr(self, "_autosave_id", "x"))
        return _recovery_dir() / f"{key}.json"

    def _autosave_clear(self) -> None:
        """Remove this document's recovery snapshot, if any."""
        try:
            self._autosave_snapshot_path().unlink(missing_ok=True)
        except OSError:
            pass

    def _autosave_tick(self) -> None:
        """Write a recovery snapshot when editing with unsaved changes."""
        if getattr(self, "_closing", False):
            return
        if not getattr(self, "_qt_edit_mode", False):
            return
        if not getattr(self, "_qt_edit_dirty", False):
            return
        try:
            text = self.editor.toPlainText()
        except Exception:  # noqa: BLE001
            return
        doc = getattr(self, "doc", None)
        payload = {
            "path": getattr(doc, "path", "") if doc else "",
            "title": getattr(doc, "title", "") if doc else tr("Untitled"),
            "markdown": text,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "app_version": APP_VERSION,
        }
        _write_snapshot(self._autosave_snapshot_path(), payload)

    # ── startup recovery ───────────────────────────────────────────────────
    def _autosave_check_on_startup(self) -> None:
        """Offer to recover any unsaved work left by a previous session.

        Presents one prompt per recoverable snapshot; on accept the text opens
        as a document (in edit mode) so the user can save it properly."""
        if getattr(self, "_closing", False):
            return
        try:
            snaps = _scan_snapshots(_recovery_dir())
        except Exception:  # noqa: BLE001
            return
        for snap in snaps:
            self._autosave_offer_one(snap)

    def _autosave_offer_one(self, snap: Dict[str, Any]) -> None:
        if not self._modal_ok():
            return
        title = snap.get("title") or tr("Untitled")
        when = snap.get("ts") or ""
        try:
            Yes = QMessageBox.StandardButton.Yes
            No = QMessageBox.StandardButton.No
        except AttributeError:  # PyQt5
            Yes = QMessageBox.Yes  # type: ignore[attr-defined]
            No = QMessageBox.No    # type: ignore[attr-defined]
        ret = QMessageBox.question(
            self,
            tr("Recover unsaved work?"),
            tr("star closed with unsaved changes to “{title}” ({when}).\n\n"
               "Recover them now?").format(title=title, when=when),
            Yes | No,
        )
        snap_file = snap.get("_file")
        if ret == Yes:
            self._autosave_recover(snap)
        else:
            # Declined — drop the snapshot so it isn't offered again.
            if snap_file:
                try:
                    Path(snap_file).unlink(missing_ok=True)
                except OSError:
                    pass

    def _autosave_recover(self, snap: Dict[str, Any]) -> None:
        """Open a recovered snapshot as an editable document."""
        # Leaving any current edit cleanly first (prompt if that has unsaved work).
        if not self._qt_confirm_leave_edit_for_replace():
            return
        md = str(snap.get("markdown") or "")
        title = str(snap.get("title") or tr("Recovered document"))
        orig = str(snap.get("path") or "")
        self._pending_doc = Document(
            path=orig, title=title, markdown=md, plain_text="", format="markdown"
        )
        self._on_doc_loaded()
        if not getattr(self, "_qt_edit_mode", False):
            self._qt_enter_edit_mode()
        # Recovered text is unsaved by definition — mark dirty and re-arm autosave.
        self._qt_edit_dirty = True
        self.editor.setFocus()
        # The snapshot has served its purpose; a fresh one is written on the next
        # tick if the user keeps the (still-unsaved) recovered text.
        snap_file = snap.get("_file")
        if snap_file:
            try:
                Path(snap_file).unlink(missing_ok=True)
            except OSError:
                pass
        self.statusBar().showMessage(tr("Recovered unsaved work — remember to save"))
        announce(self.editor, tr("Recovered unsaved work. Remember to save."))
