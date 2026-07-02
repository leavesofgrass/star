"""Spaced-repetition scheduler — pure logic, no I/O, deterministic.

star's notes and highlights can be reviewed like flashcards.  This module holds
the *scheduling* brain: given a card's current memory state and the grade the
reader just assigned it, it returns the next state (when the card is next due,
how long the interval is, and the internal memory parameters).

Algorithm: **FSRS** (Free Spaced Repetition Scheduler) — the modern, open
memory model that replaced SM-2 in Anki 23.10.  Each item carries a
*stability* (S, days until recall probability falls to the target) and a
*difficulty* (D, 1–10).  On each review the elapsed time and the grade update
S and D, and the next interval is the number of days for retrievability to
decay from 1.0 back to the requested retention (default 0.9).  A well-documented
SM-2 fallback (:func:`review_sm2`) is provided for reference and testing.

Design notes
------------
* **Pure & deterministic.**  Every function is a plain transform of its inputs.
  "Today" is injected (``now``/``today`` parameters) so tests are reproducible
  and the scheduler never reads the wall clock behind the caller's back.
* **JSON-friendly state.**  An ``sr_state`` is a plain ``dict`` of primitives
  (see :func:`new_state`) so it round-trips through ``settings.json`` and the
  ``.star/`` sidecars with no custom serializer.
* **Self-contained.**  Depends only on the standard library; imported freely by
  ``annotations.py`` and the GUI without pulling in Qt or any optional package.

The four grades match Anki's four buttons::

    AGAIN = 1   # forgot / wrong
    HARD  = 2   # recalled with serious difficulty
    GOOD  = 3   # recalled correctly
    EASY  = 4   # recalled effortlessly
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import Any, Dict, Optional

# ── Grades ───────────────────────────────────────────────────────────────────
AGAIN = 1
HARD = 2
GOOD = 3
EASY = 4
GRADES = (AGAIN, HARD, GOOD, EASY)

#: Map the review dashboard's string grades to the integer scale.
GRADE_NAMES: Dict[str, int] = {
    "again": AGAIN,
    "hard": HARD,
    "good": GOOD,
    "easy": EASY,
}


def grade_from(value: Any) -> int:
    """Coerce *value* (int 1–4 or name ``again``/``hard``/``good``/``easy``) to a grade.

    Raises ``ValueError`` on anything outside the four-grade scale so a typo in
    a caller surfaces immediately instead of silently scheduling wrong.
    """
    if isinstance(value, str):
        key = value.strip().lower()
        if key in GRADE_NAMES:
            return GRADE_NAMES[key]
        # Allow a numeric string too ("3").
        try:
            value = int(key)
        except ValueError:
            raise ValueError(f"unknown grade {value!r}") from None
    ival = int(value)
    if ival not in GRADES:
        raise ValueError(f"grade must be 1–4, got {ival!r}")
    return ival


# ── FSRS parameters ──────────────────────────────────────────────────────────
# The 19 default weights published with FSRS-4.5 / FSRS-5 (Anki's built-in
# preset).  They are constants of the memory model, not tunables star exposes;
# a power user could override them but the defaults are strong out of the box.
DEFAULT_WEIGHTS = (
    0.4072, 1.1829, 3.1262, 15.4722, 7.2102, 0.5316, 1.0651, 0.0234,
    1.616, 0.1544, 1.0824, 1.9813, 0.0953, 0.2975, 2.2042, 0.2407,
    2.9466, 0.5034, 0.6567,
)

#: Target retention: the probability of recall at which a card is scheduled.
#: 0.9 means "show the card again once I'd have a 90% chance of remembering."
DEFAULT_RETENTION = 0.9

#: Decay constant of the FSRS forgetting curve, and the derived factor used to
#: invert it.  R(t) = (1 + FACTOR * t / S) ** DECAY.
_DECAY = -0.5
_FACTOR = 0.9 ** (1.0 / _DECAY) - 1.0  # = 19/81 for DECAY = -0.5

#: Interval clamp: never schedule further out than ~100 years, never negative.
_MAX_INTERVAL = 36500


# ── Date helpers (deterministic; "today" is always injected) ─────────────────
def _as_date(value: Any) -> _dt.date:
    """Coerce *value* (``date``/``datetime``/ISO string) to a ``date``."""
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    return _dt.date.fromisoformat(str(value)[:10])


def _iso(d: _dt.date) -> str:
    """Serialize a date as an ISO ``YYYY-MM-DD`` string."""
    return d.isoformat()


def new_state(today: Optional[_dt.date] = None) -> Dict[str, Any]:
    """Return a fresh, never-reviewed ``sr_state`` dict.

    ``today`` (a ``date``) sets ``next_review`` so a brand-new card is due
    immediately; it defaults to :func:`datetime.date.today` for convenience but
    tests always pass it explicitly for determinism.
    """
    day = today or _dt.date.today()
    return {
        "stability": 0.0,      # FSRS S; 0 until the first review
        "difficulty": 0.0,     # FSRS D (1–10); 0 until the first review
        "interval": 0,         # last scheduled interval in days
        "reps": 0,             # total reviews
        "lapses": 0,           # times graded AGAIN after learning
        "last_review": None,   # ISO date of the previous review, or None
        "next_review": _iso(day),  # ISO date the card is next due
    }


def is_new(state: Optional[Dict[str, Any]]) -> bool:
    """True when *state* is missing or has never been reviewed."""
    return not state or int(state.get("reps", 0)) <= 0 or float(state.get("stability", 0.0)) <= 0.0


# ── FSRS core maths ──────────────────────────────────────────────────────────
def _clamp_d(d: float) -> float:
    return min(max(d, 1.0), 10.0)


def _init_difficulty(grade: int, w) -> float:
    # D0(G) = w4 - e^(w5 * (G - 1)) + 1
    return _clamp_d(w[4] - math.exp(w[5] * (grade - 1)) + 1.0)


def _init_stability(grade: int, w) -> float:
    # S0(G) = w[G-1], floored to a small positive number.
    return max(w[grade - 1], 0.1)


def retrievability(elapsed_days: float, stability: float) -> float:
    """Probability of recall after *elapsed_days* given *stability* (FSRS curve)."""
    if stability <= 0:
        return 0.0
    return (1.0 + _FACTOR * max(elapsed_days, 0) / stability) ** _DECAY


def _next_interval(stability: float, retention: float) -> int:
    """Days until retrievability decays from 1.0 to *retention*."""
    if stability <= 0:
        return 0
    ivl = (stability / _FACTOR) * (retention ** (1.0 / _DECAY) - 1.0)
    return int(min(max(round(ivl), 1), _MAX_INTERVAL))


def _next_difficulty(d: float, grade: int, w) -> float:
    # ΔD = -w6 * (G - 3); linear-damped then mean-reverted toward D0(EASY=4).
    delta = -w[6] * (grade - 3)
    d_prime = d + delta * ((10.0 - d) / 9.0)  # linear damping
    target = _init_difficulty(EASY, w)
    d_new = w[7] * target + (1.0 - w[7]) * d_prime  # mean reversion
    return _clamp_d(d_new)


def _stability_after_recall(d: float, s: float, r: float, grade: int, w) -> float:
    # SInc for a successful review (grades HARD/GOOD/EASY).
    hard_penalty = w[15] if grade == HARD else 1.0
    easy_bonus = w[16] if grade == EASY else 1.0
    inc = (
        math.exp(w[8])
        * (11.0 - d)
        * (s ** -w[9])
        * (math.exp(w[10] * (1.0 - r)) - 1.0)
        * hard_penalty
        * easy_bonus
        + 1.0
    )
    return s * inc


def _stability_after_lapse(d: float, s: float, r: float, w) -> float:
    # Post-lapse stability (grade AGAIN).
    new_s = (
        w[11]
        * (d ** -w[12])
        * ((s + 1.0) ** w[13] - 1.0)
        * math.exp(w[14] * (1.0 - r))
    )
    # Never let a lapse *raise* stability above its pre-lapse value.
    return max(min(new_s, s), 0.1)


def review(
    state: Optional[Dict[str, Any]],
    grade: Any,
    today: Optional[_dt.date] = None,
    *,
    retention: float = DEFAULT_RETENTION,
    weights=DEFAULT_WEIGHTS,
) -> Dict[str, Any]:
    """Return the new ``sr_state`` after grading a card *today*.

    *state* is the card's current state (or ``None``/new for a first review).
    *grade* is ``again``/``hard``/``good``/``easy`` or the integers 1–4.
    *today* (injected for determinism) is the review date.  *retention* is the
    desired recall probability the next interval is scheduled at.

    The returned dict is a **new** object; the input is not mutated.
    """
    g = grade_from(grade)
    w = weights
    day = today or _dt.date.today()
    st = dict(state) if state else new_state(day)

    reps = int(st.get("reps", 0))
    lapses = int(st.get("lapses", 0))

    if is_new(st):
        # First-ever review: seed S and D from the grade.
        difficulty = _init_difficulty(g, w)
        stability = _init_stability(g, w)
        if g == AGAIN:
            lapses += 1
    else:
        s = float(st.get("stability", 0.0))
        d = float(st.get("difficulty", 0.0)) or _init_difficulty(GOOD, w)
        last = st.get("last_review")
        elapsed = (day - _as_date(last)).days if last else 0
        r = retrievability(elapsed, s)
        difficulty = _next_difficulty(d, g, w)
        if g == AGAIN:
            stability = _stability_after_lapse(d, s, r, w)
            lapses += 1
        else:
            stability = _stability_after_recall(d, s, r, g, w)

    interval = _next_interval(stability, retention)
    # A lapse always comes back the next day, regardless of the tiny post-lapse
    # stability, so the reader actually re-sees a forgotten card soon.
    if g == AGAIN:
        interval = 1
    next_day = day + _dt.timedelta(days=interval)

    return {
        "stability": round(stability, 4),
        "difficulty": round(difficulty, 4),
        "interval": interval,
        "reps": reps + 1,
        "lapses": lapses,
        "last_review": _iso(day),
        "next_review": _iso(next_day),
    }


def is_due(state: Optional[Dict[str, Any]], today: Optional[_dt.date] = None) -> bool:
    """True when a card with *state* is due for review on or before *today*.

    A card with no state (never scheduled) is considered due — it needs its
    first review.
    """
    if not state:
        return True
    day = today or _dt.date.today()
    nxt = state.get("next_review")
    if not nxt:
        return True
    try:
        return _as_date(nxt) <= day
    except (ValueError, TypeError):
        return True


def days_until_due(state: Optional[Dict[str, Any]], today: Optional[_dt.date] = None) -> int:
    """Signed days until the card is due (0 = today, negative = overdue)."""
    if not state or not state.get("next_review"):
        return 0
    day = today or _dt.date.today()
    try:
        return (_as_date(state["next_review"]) - day).days
    except (ValueError, TypeError):
        return 0


def retention_estimate(state: Optional[Dict[str, Any]], today: Optional[_dt.date] = None) -> float:
    """Current estimated probability of recall (0.0–1.0) for *state* today.

    Uses the FSRS forgetting curve from the last review to *today*.  A new /
    unreviewed card returns 0.0 (nothing memorised yet).
    """
    if is_new(state):
        return 0.0
    assert state is not None
    s = float(state.get("stability", 0.0))
    last = state.get("last_review")
    if not last:
        return 0.0
    day = today or _dt.date.today()
    try:
        elapsed = (day - _as_date(last)).days
    except (ValueError, TypeError):
        return 0.0
    return round(retrievability(elapsed, s), 4)


# ── SM-2 fallback (reference / documented alternative) ───────────────────────
def review_sm2(
    state: Optional[Dict[str, Any]],
    grade: Any,
    today: Optional[_dt.date] = None,
) -> Dict[str, Any]:
    """SuperMemo-2 scheduler — the classic, simpler alternative to FSRS.

    Kept as a documented fallback: some users prefer SM-2's transparency, and it
    is a good oracle for tests.  It tracks an *ease factor* (EF, ≥1.3) and a
    running interval.  Grades 3/4 advance the interval by ×EF; grades 1/2 reset
    it (a lapse).  EF rises on easy recalls and falls on hard ones.

    State fields mirror :func:`new_state` plus ``ease`` (the EF), so a card can
    be scheduled by either engine without losing data.
    """
    g = grade_from(grade)
    day = today or _dt.date.today()
    st = dict(state) if state else new_state(day)
    ease = float(st.get("ease", 2.5)) or 2.5
    reps = int(st.get("reps", 0))
    lapses = int(st.get("lapses", 0))
    interval = int(st.get("interval", 0))

    # SM-2 quality is 0–5; map the four-grade scale to {2,3,4,5}.
    q = {AGAIN: 2, HARD: 3, GOOD: 4, EASY: 5}[g]

    if g in (AGAIN, HARD) and g == AGAIN:
        # Failed recall: reset the interval, count a lapse, keep reps growing.
        interval = 1
        lapses += 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = int(max(1, round(interval * ease)))
    # EF update (the standard SM-2 formula), floored at 1.3.
    ease = max(1.3, ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))

    next_day = day + _dt.timedelta(days=interval)
    out = {
        "stability": float(interval),  # SM-2 has no S; expose interval as a proxy
        "difficulty": round(6.0 - (ease - 1.3) / (2.5 - 1.3) * 5.0, 4),
        "interval": interval,
        "reps": reps + 1,
        "lapses": lapses,
        "ease": round(ease, 4),
        "last_review": _iso(day),
        "next_review": _iso(next_day),
    }
    return out
