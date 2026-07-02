"""Tests for the Study & retention GUI + card generation + Anki sync.

Covers:
* the offscreen review dialog building, revealing, and grading (updating
  ``sr_state`` immediately);
* auto-cloze card generation from highlighted sentences (pure logic, no Qt);
* the AnkiConnect two-way sync against a fully mocked HTTP transport — no
  network is ever touched.

The Qt portions are skipped when PyQt is unavailable; the cloze and anki_sync
portions run everywhere (stdlib only).
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("STAR_NO_AUTOINSTALL", "1")

_HAS_QT = bool(importlib.util.find_spec("PyQt6") or importlib.util.find_spec("PyQt5"))

D0 = datetime.date(2026, 1, 1)


# =============================================================================
# Auto-cloze generation (pure logic — runs without Qt)
# =============================================================================
from star import flashcards  # noqa: E402


def test_cloze_blanks_named_entities_and_numbers():
    cards = flashcards.make_cloze_cards(
        "Marie Curie won the Nobel Prize in 1903.", anki_syntax=True
    )
    assert cards, "expected at least one cloze card"
    card = cards[0]
    # Key terms blanked in the plain front.
    assert "____" in card["front"]
    # The original sentence is the answer.
    assert "Marie Curie" in card["back"]
    # Anki cloze syntax present with numbered deletions.
    assert "{{c1::" in card["cloze"]
    # A named entity and the year were picked as terms.
    joined = " ".join(card["terms"])
    assert "Marie Curie" in joined or "Curie" in joined
    assert "1903" in card["terms"]


def test_cloze_skips_sentence_with_no_key_terms():
    # All-lowercase common words → nothing worth blanking.
    cards = flashcards.make_cloze_cards("this is a small and very common thing.")
    assert cards == []


def test_cloze_multiple_sentences_each_yield_a_card():
    text = "The Amazon flows through Brazil. Mount Everest is in Nepal."
    cards = flashcards.make_cloze_cards(text, anki_syntax=True)
    assert len(cards) == 2


def test_cloze_carries_note_into_back():
    cards = flashcards.make_cloze_cards(
        "Paris is the capital of France.", note="Remember this for the exam.",
        anki_syntax=True,
    )
    assert cards
    assert "Remember this for the exam." in cards[0]["back"]


def test_cloze_plain_marker_when_not_anki():
    cards = flashcards.make_cloze_cards("Einstein published relativity in 1905.")
    assert cards
    assert "____" in cards[0]["cloze"]
    assert "{{c" not in cards[0]["cloze"]


# =============================================================================
# AnkiConnect two-way sync (mocked HTTP transport — no network)
# =============================================================================
from star import anki_sync  # noqa: E402


class _FakeResp:
    def __init__(self, obj):
        self._data = json.dumps(obj).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(responses):
    """Return an opener callable yielding queued responses; records requests."""
    queue = list(responses)
    calls = {"requests": []}

    def opener(req, timeout=None):
        calls["requests"].append(req)
        if not queue:
            raise AssertionError("no more mocked responses")
        return _FakeResp(queue.pop(0))

    opener.calls = calls
    return opener


def test_is_available_true_and_false():
    ok = _opener([{"result": 6, "error": None}])
    assert anki_sync.is_available(opener=ok) is True

    def boom(req, timeout=None):
        import urllib.error
        raise urllib.error.URLError("refused")

    assert anki_sync.is_available(opener=boom) is False


def test_invoke_raises_on_error_payload():
    op = _opener([{"result": None, "error": "collection is not open"}])
    with pytest.raises(anki_sync.AnkiConnectError):
        anki_sync.invoke("addNotes", opener=op)


def test_push_cards_adds_and_skips_empty():
    op = _opener([
        {"result": True, "error": None},        # createDeck
        {"result": [1001], "error": None},       # addNotes → one id
    ])
    anns = [
        {"id": "a1", "anchor": "front", "note": "back"},
        {"id": "a2", "anchor": "", "note": ""},  # empty → skipped
    ]
    summary = anki_sync.push_cards(anns, deck="star", opener=op)
    assert summary["ok"] is True
    assert summary["added"] == 1
    assert summary["skipped"] == 1
    assert summary["note_ids"] == [1001]


def test_push_cards_offline_is_safe():
    def boom(req, timeout=None):
        import urllib.error
        raise urllib.error.URLError("no anki")

    summary = anki_sync.push_cards(
        [{"id": "a", "anchor": "x", "note": "y"}], opener=boom
    )
    assert summary["ok"] is False
    assert summary["added"] == 0


def test_pull_review_state_maps_by_star_id():
    op = _opener([
        {"result": [55], "error": None},  # findCards
        {"result": [{
            "cardId": 55,
            "interval": 12,
            "due": 20000,
            "reps": 3,
            "lapses": 1,
            "factor": 2500,
            "tags": ["star", "star::abc123"],
        }], "error": None},               # cardsInfo
    ])
    state = anki_sync.pull_review_state(deck="star", opener=op)
    assert "abc123" in state
    assert state["abc123"]["interval"] == 12
    assert state["abc123"]["reps"] == 3
    assert state["abc123"]["ease"] == 2.5


def test_sync_annotations_writes_pulled_state():
    class _Settings:
        def __init__(self, data):
            self._data = data
            self.saved = 0

        def __getitem__(self, k):
            return self._data[k]

        def get(self, k, d=None):
            return self._data.get(k, d)

        def save(self):
            self.saved += 1

    s = _Settings({"annotations": {"docA": [
        {"id": "abc123", "anchor": "front", "note": "back"},
    ]}})
    op = _opener([
        {"result": 6, "error": None},            # is_available → version
        {"result": True, "error": None},          # createDeck
        {"result": [77], "error": None},          # addNotes
        {"result": [77], "error": None},          # findCards
        {"result": [{
            "cardId": 77, "interval": 8, "due": 1, "reps": 2,
            "lapses": 0, "factor": 2100, "tags": ["star::abc123"],
        }], "error": None},                        # cardsInfo
    ])
    result = anki_sync.sync_annotations(s, deck="star", opener=op)
    assert result["ok"] is True
    assert result["pulled"] == 1
    # The Anki mirror landed on the annotation.
    assert s._data["annotations"]["docA"][0]["anki"]["interval"] == 8


# =============================================================================
# Review dashboard dialog (offscreen Qt)
# =============================================================================
pytestmark_qt = pytest.mark.skipif(not _HAS_QT, reason="PyQt not installed")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtGui import QFontDatabase
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    for ttf in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(ttf):
            QFontDatabase.addApplicationFont(ttf)
    return app


@pytest.fixture
def window(qapp):
    from star.gui.main_window import StarWindow
    from star.settings import Settings

    win = StarWindow(Settings())

    # Neutralise TTS so nothing tries to speak during the test.
    class _Stub:
        speaking = False

        def speak(self, *a, **k):
            pass

        def stop(self):
            pass

        def set_rate(self, *a):
            pass

        def set_word_map(self, *a):
            pass

    win.tts_manager = _Stub()
    yield win
    win.close()


def _seed_cards(win):
    """Give the window two reviewable annotations under a fake doc path."""
    win.settings._data["annotations"] = {
        "docA": [
            {"id": "c1", "anchor": "The mitochondrion", "note": "powerhouse of the cell"},
            {"id": "c2", "anchor": "Photosynthesis", "note": "converts light to sugar"},
        ]
    }


@pytestmark_qt
def test_review_dialog_builds_and_reveals(window):
    from star.gui.mixin_review import _ReviewDialog
    from star.annotations import due_cards

    _seed_cards(window)
    cards = due_cards(window.settings, today=D0)
    assert len(cards) == 2

    dlg = _ReviewDialog(window, cards)
    dlg._set_today(D0)
    dlg._show_card()
    # Front shown, back hidden, grade buttons disabled pre-reveal.
    # (isVisibleTo reports visibility relative to the dialog without requiring
    # the top-level window to actually be shown under the offscreen QPA.)
    assert dlg._front.text()
    assert not dlg._back.isVisibleTo(dlg)
    assert all(not b.isEnabled() for b in dlg._grade_btns.values())

    dlg._reveal()
    assert dlg._back.isVisibleTo(dlg)
    assert all(b.isEnabled() for b in dlg._grade_btns.values())
    dlg.close()


@pytestmark_qt
def test_review_dialog_grade_updates_sr_state(window):
    from star.gui.mixin_review import _ReviewDialog
    from star.annotations import due_cards, get_annotation_by_id

    _seed_cards(window)
    cards = due_cards(window.settings, today=D0)
    dlg = _ReviewDialog(window, cards)
    dlg._set_today(D0)
    dlg._show_card()

    # Grade before reveal only reveals (recall-before-answer discipline).
    dlg._grade("good")
    assert dlg._revealed
    ann_before = get_annotation_by_id(window.settings, "docA", "c1")
    assert "sr_state" not in ann_before or ann_before.get("sr_state") is None

    # Now grade for real.
    dlg._grade("good")
    ann_after = get_annotation_by_id(window.settings, "docA", "c1")
    assert ann_after["sr_state"]["reps"] == 1
    assert ann_after["sr_state"]["next_review"] > "2026-01-01"
    # The queue advanced to the second card.
    assert dlg._pos == 1
    dlg.close()


@pytestmark_qt
def test_review_menu_and_shortcut_present(window):
    """The Study menu carries Review Due Cards with its Ctrl+Shift+F5 binding."""
    labels = {label for (label, _act, _sc) in window._shortcut_actions}
    assert "Review Due Cards…" in labels
    sc = {label: sc for (label, _a, sc) in window._shortcut_actions}
    assert sc["Review Due Cards…"] == "Ctrl+Shift+F5"


@pytestmark_qt
def test_review_due_no_cards_is_graceful(window, monkeypatch):
    """With no annotations, opening the dashboard shows an info box, no crash."""
    window.settings._data["annotations"] = {}
    shown = {"count": 0}
    import star.gui.mixin_review as mr

    monkeypatch.setattr(
        mr.QMessageBox, "information",
        lambda *a, **k: shown.__setitem__("count", shown["count"] + 1),
    )
    window._qt_review_due()
    assert shown["count"] == 1


@pytestmark_qt
def test_anki_sync_menu_action_offline(window, monkeypatch):
    """Anki sync gracefully reports when Anki is unreachable."""
    import star.anki_sync as anki_sync
    import star.gui.mixin_review as mr

    monkeypatch.setattr(anki_sync, "is_available", lambda *a, **k: False)
    shown = {"count": 0}
    monkeypatch.setattr(
        mr.QMessageBox, "information",
        lambda *a, **k: shown.__setitem__("count", shown["count"] + 1),
    )
    window._qt_anki_sync()
    assert shown["count"] == 1
