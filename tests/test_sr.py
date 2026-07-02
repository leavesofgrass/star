"""Unit tests for the spaced-repetition scheduler (star/sr.py) and the
annotation-level SR helpers (star/annotations.py).

Everything here is pure logic — no Qt, no I/O, no network — and every test
injects a fixed 'today' so the scheduling maths is fully deterministic.
"""
from __future__ import annotations

import datetime

import pytest

from star import sr
from star import annotations as ann

D0 = datetime.date(2026, 1, 1)


def _plus(day: datetime.date, n: int) -> datetime.date:
    return day + datetime.timedelta(days=n)


# ── grade coercion ────────────────────────────────────────────────────────────
def test_grade_from_names_and_ints():
    assert sr.grade_from("again") == sr.AGAIN
    assert sr.grade_from("HARD") == sr.HARD
    assert sr.grade_from("good") == sr.GOOD
    assert sr.grade_from("easy") == sr.EASY
    assert sr.grade_from(3) == sr.GOOD
    assert sr.grade_from("4") == sr.EASY


@pytest.mark.parametrize("bad", ["", "meh", 0, 5, 99, None])
def test_grade_from_rejects_bad(bad):
    with pytest.raises((ValueError, TypeError)):
        sr.grade_from(bad)


# ── new state ─────────────────────────────────────────────────────────────────
def test_new_state_is_due_today():
    st = sr.new_state(D0)
    assert st["reps"] == 0
    assert st["lapses"] == 0
    assert st["next_review"] == "2026-01-01"
    assert sr.is_new(st)
    assert sr.is_due(st, D0)


def test_is_new_for_none_and_zero():
    assert sr.is_new(None)
    assert sr.is_new({})
    assert sr.is_new({"reps": 0, "stability": 0.0})
    assert not sr.is_new({"reps": 1, "stability": 3.0})


# ── first review seeds S and D from the grade ────────────────────────────────
def test_first_review_good_schedules_forward():
    st = sr.review(None, "good", D0)
    assert st["reps"] == 1
    assert st["lapses"] == 0
    assert st["stability"] > 0
    assert 1.0 <= st["difficulty"] <= 10.0
    # Next review is strictly in the future.
    assert datetime.date.fromisoformat(st["next_review"]) > D0


def test_easy_beats_good_beats_hard_on_first_review():
    """Higher grades → longer first interval (easy > good > hard)."""
    hard = sr.review(None, "hard", D0)["interval"]
    good = sr.review(None, "good", D0)["interval"]
    easy = sr.review(None, "easy", D0)["interval"]
    assert hard < good < easy


def test_first_review_again_counts_lapse_and_returns_next_day():
    st = sr.review(None, "again", D0)
    assert st["lapses"] == 1
    assert st["interval"] == 1
    assert st["next_review"] == "2026-01-02"


# ── intervals grow across successful reviews ─────────────────────────────────
def test_intervals_grow_on_repeated_good():
    st = sr.review(None, "good", D0)
    prev = st["interval"]
    day = D0
    for _ in range(4):
        day = datetime.date.fromisoformat(st["next_review"])
        st = sr.review(st, "good", day)
        assert st["interval"] >= prev  # monotone non-decreasing
        prev = st["interval"]
    # After several good reviews the interval should be well beyond a day.
    assert st["interval"] > 3


def test_lapse_resets_interval_and_increments_lapses():
    st = sr.review(None, "good", D0)
    st = sr.review(st, "good", datetime.date.fromisoformat(st["next_review"]))
    reps_before = st["reps"]
    lapses_before = st["lapses"]
    st = sr.review(st, "again", datetime.date.fromisoformat(st["next_review"]))
    assert st["interval"] == 1
    assert st["lapses"] == lapses_before + 1
    assert st["reps"] == reps_before + 1


def test_review_does_not_mutate_input():
    st = sr.new_state(D0)
    snapshot = dict(st)
    sr.review(st, "good", D0)
    assert st == snapshot  # input untouched


def test_review_is_deterministic():
    a = sr.review(None, "good", D0)
    b = sr.review(None, "good", D0)
    assert a == b


# ── retrievability / retention ───────────────────────────────────────────────
def test_retrievability_decays_with_time():
    st = sr.review(None, "good", D0)
    last = datetime.date.fromisoformat(st["last_review"])
    r_same_day = sr.retention_estimate(st, last)
    r_later = sr.retention_estimate(st, _plus(last, 30))
    assert 0.0 <= r_later <= r_same_day <= 1.0
    # At the last-review moment recall is essentially certain.
    assert r_same_day > 0.95


def test_retention_estimate_new_card_is_zero():
    assert sr.retention_estimate(None) == 0.0
    assert sr.retention_estimate(sr.new_state(D0), D0) == 0.0


# ── due queries ───────────────────────────────────────────────────────────────
def test_is_due_and_days_until_due():
    st = sr.review(None, "good", D0)
    nxt = datetime.date.fromisoformat(st["next_review"])
    assert not sr.is_due(st, D0)            # scheduled ahead → not due yet
    assert sr.is_due(st, nxt)              # on the due date → due
    assert sr.is_due(st, _plus(nxt, 5))   # overdue → due
    assert sr.days_until_due(st, D0) > 0
    assert sr.days_until_due(st, _plus(nxt, 3)) == -3  # overdue by 3


def test_is_due_none_state_is_due():
    assert sr.is_due(None, D0)
    assert sr.is_due({}, D0)


# ── SM-2 fallback ─────────────────────────────────────────────────────────────
def test_sm2_first_two_intervals_are_1_and_6():
    st = sr.review_sm2(None, "good", D0)
    assert st["interval"] == 1
    st = sr.review_sm2(st, "good", datetime.date.fromisoformat(st["next_review"]))
    assert st["interval"] == 6


def test_sm2_again_resets_and_counts_lapse():
    st = sr.review_sm2(None, "good", D0)
    st = sr.review_sm2(st, "good", datetime.date.fromisoformat(st["next_review"]))
    st = sr.review_sm2(st, "again", datetime.date.fromisoformat(st["next_review"]))
    assert st["interval"] == 1
    assert st["lapses"] == 1


def test_sm2_ease_floor():
    st = None
    day = D0
    for _ in range(6):
        st = sr.review_sm2(st, "again", day)
        day = datetime.date.fromisoformat(st["next_review"])
    assert st["ease"] >= 1.3


# =============================================================================
# Annotation-level SR helpers
# =============================================================================
class _FakeSettings:
    """A dict-backed stand-in for star.settings.Settings for pure-logic tests."""

    def __init__(self, annotations=None):
        self._data = {"annotations": annotations or {}}
        self.saved = 0

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def save(self):
        self.saved += 1


def _mk(anchor="highlight", note="the note", **extra):
    d = {"anchor": anchor, "note": note}
    d.update(extra)
    return d


def test_is_reviewable():
    assert ann.is_reviewable(_mk("a", "b"))
    assert ann.is_reviewable(_mk("a", ""))   # highlight only
    assert ann.is_reviewable(_mk("", "b"))   # note only
    assert not ann.is_reviewable(_mk("", ""))
    assert not ann.is_reviewable(_mk("   ", "  "))


def test_iter_review_cards_skips_empty_and_assigns_ids():
    s = _FakeSettings({
        "docA": [_mk("h1", "n1"), _mk("", "")],
        "docB": [_mk("h2", "")],
    })
    cards = list(ann.iter_review_cards(s))
    # The two content cards, not the empty one.
    assert len(cards) == 2
    for _doc, a in cards:
        assert a.get("id")  # id assigned in place


def test_ensure_and_review_annotation_persist():
    a = _mk("h1", "n1", id="fixed1")
    s = _FakeSettings({"docA": [a]})
    st = ann.ensure_sr_state(s, "docA", "fixed1", today=D0)
    assert st is not None and sr.is_new(st)
    assert s.saved >= 1
    new = ann.review_annotation(s, "docA", "fixed1", "good", today=D0)
    assert new["reps"] == 1
    # Written back onto the annotation.
    assert a["sr_state"]["reps"] == 1


def test_review_annotation_unknown_id_returns_none():
    s = _FakeSettings({"docA": [_mk("h1", "n1", id="x")]})
    assert ann.review_annotation(s, "docA", "nope", "good", today=D0) is None
    assert ann.ensure_sr_state(s, "docA", "nope", today=D0) is None


def test_due_cards_orders_most_overdue_first():
    # Two scheduled cards with different due dates + one brand-new card.
    scheduled_soon = sr.review(None, "good", D0)      # due D0+3
    scheduled_late = sr.review(None, "easy", D0)      # due much later
    s = _FakeSettings({
        "docA": [
            _mk("soon", "n", id="soon", sr_state=scheduled_soon),
            _mk("late", "n", id="late", sr_state=scheduled_late),
            _mk("fresh", "n", id="fresh"),  # no sr_state → due now
        ],
    })
    # On a day well past both due dates, most-overdue comes first.
    far = _plus(D0, 400)
    due = ann.due_cards(s, today=far)
    ids = [a["id"] for _doc, a in due]
    assert "fresh" in ids and "soon" in ids and "late" in ids
    # 'soon' (due D0+3) is more overdue than 'late', so it precedes it.
    assert ids.index("soon") < ids.index("late")


def test_due_cards_excludes_not_yet_due():
    scheduled = sr.review(None, "good", D0)  # due in a few days
    s = _FakeSettings({"docA": [_mk("h", "n", id="h", sr_state=scheduled)]})
    assert ann.due_cards(s, today=D0) == []  # nothing due on D0


def test_review_summary_counts_and_retention():
    reviewed = sr.review(None, "good", D0)
    s = _FakeSettings({
        "docA": [
            _mk("h1", "n1", id="a", sr_state=reviewed),
            _mk("h2", "n2", id="b"),          # new, due
            _mk("", "", id="c"),               # not reviewable → excluded
        ],
    })
    summ = ann.review_summary(s, today=D0)
    assert summ["total"] == 2         # only reviewable cards
    assert summ["new"] == 1           # card b
    assert summ["reviewed"] == 1      # card a
    assert summ["due"] >= 1           # the new card is due
    assert 0.0 <= summ["retention"] <= 1.0
