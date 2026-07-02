"""AnkiConnect two-way sync — push star cards to Anki, pull review state back.

Optional, best-effort, and fully offline-safe.  It talks to a **locally running**
Anki desktop that has the community `AnkiConnect <https://ankiweb.net/shared/info/
2055492159>`_ add-on installed, which exposes a small JSON-RPC API on
``http://localhost:8765``.

No hard dependency: this module uses only :mod:`urllib` from the standard
library, so importing star never requires Anki or ``requests`` to be present.
Every call is wrapped so that when Anki is closed, the add-on is absent, or the
port is firewalled, the functions degrade quietly (return ``None`` / ``False``
/ empty) instead of raising — the reader's own note store is the source of
truth, and Anki is a convenience mirror.

Two directions:

* **Push** (``push_cards``): create/replace Anki notes for star annotations in a
  named deck, so highlights + notes become reviewable in Anki.
* **Pull** (``pull_review_state``): read back each note's scheduling info
  (interval, due, reps, lapses, ease) so star's in-app dashboard can reflect
  reviews the user did *inside* Anki.

The transport (:func:`invoke`) is deliberately tiny and easy to mock in tests —
point ``opener``/the URL at a fake and no network is touched.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

#: Default AnkiConnect endpoint (the add-on binds localhost only).
DEFAULT_URL = "http://127.0.0.1:8765"
#: AnkiConnect API version this client speaks.
API_VERSION = 6
#: Short socket timeout — a missing Anki should fail fast, not hang the GUI.
DEFAULT_TIMEOUT = 3.0


class AnkiConnectError(RuntimeError):
    """Raised by :func:`invoke` when AnkiConnect returns an ``error`` payload.

    Callers that want best-effort behaviour use the higher-level helpers
    (:func:`push_cards`, :func:`pull_review_state`, :func:`is_available`) which
    swallow this; :func:`invoke` raises it so a direct caller can see the cause.
    """


def invoke(
    action: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    url: str = DEFAULT_URL,
    timeout: float = DEFAULT_TIMEOUT,
    opener: Any = None,
) -> Any:
    """Call one AnkiConnect *action* and return its ``result``.

    *params* is the action's parameter dict.  *opener* lets tests inject a fake
    transport: any callable taking ``(request, timeout)`` and returning an
    object with ``.read()`` (i.e. the shape of :func:`urllib.request.urlopen`).
    Defaults to ``urllib.request.urlopen``.

    Raises :class:`AnkiConnectError` when the endpoint reports an error, and
    lets network errors (``URLError``) propagate so callers can distinguish
    "Anki is not running" from "Anki rejected the request".
    """
    payload = json.dumps(
        {"action": action, "version": API_VERSION, "params": params or {}}
    ).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    _open = opener or urllib.request.urlopen
    with _open(req, timeout=timeout) as resp:
        raw = resp.read()
    data = json.loads(raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw)
    # AnkiConnect always returns an object with exactly {"result", "error"}.
    if not isinstance(data, dict) or "error" not in data or "result" not in data:
        raise AnkiConnectError("malformed AnkiConnect response")
    if data["error"] is not None:
        raise AnkiConnectError(str(data["error"]))
    return data["result"]


def is_available(url: str = DEFAULT_URL, timeout: float = DEFAULT_TIMEOUT, opener: Any = None) -> bool:
    """True when a reachable AnkiConnect endpoint answers ``version``.

    Never raises — a closed Anki, missing add-on, or blocked port all return
    False, so callers can gate the feature with one cheap probe.
    """
    try:
        v = invoke("version", url=url, timeout=timeout, opener=opener)
        return isinstance(v, int) and v >= 1
    except (AnkiConnectError, urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return False


def ensure_deck(name: str, *, url: str = DEFAULT_URL, opener: Any = None) -> bool:
    """Create the deck *name* in Anki if it does not already exist.

    Returns True on success, False if the call failed (Anki closed, etc.).
    """
    try:
        invoke("createDeck", params={"deck": name}, url=url, opener=opener)
        return True
    except (AnkiConnectError, urllib.error.URLError, OSError, ValueError):
        return False


def _note_from_annotation(ann: Dict[str, Any], deck: str, model: str) -> Dict[str, Any]:
    """Build the AnkiConnect ``note`` object for one star annotation."""
    front = str(ann.get("anchor", "") or "").strip()
    back = str(ann.get("note", "") or "").strip()
    # A stable star id, stored in a tag, lets a re-push update the same note
    # instead of duplicating it, and lets a pull match Anki notes back to
    # annotations.
    sid = str(ann.get("id", "") or "")
    tags = ["star"] + ([f"star::{sid}"] if sid else [])
    return {
        "deckName": deck,
        "modelName": model,
        "fields": {"Front": front, "Back": back},
        "tags": tags,
        # Let Anki dedupe on the first field within the deck.
        "options": {"allowDuplicate": False, "duplicateScope": "deck"},
    }


def push_cards(
    annotations: List[Dict[str, Any]],
    deck: str = "star",
    *,
    model: str = "Basic",
    url: str = DEFAULT_URL,
    opener: Any = None,
) -> Dict[str, Any]:
    """Push reviewable *annotations* to Anki as notes in *deck*.

    Best-effort and offline-safe: returns a summary dict
    ``{"added": int, "skipped": int, "note_ids": [...], "ok": bool}``.  When
    Anki is unreachable, ``ok`` is False and ``added`` is 0 — nothing raises.
    Annotations with neither a highlight nor a note are skipped.
    """
    summary: Dict[str, Any] = {"added": 0, "skipped": 0, "note_ids": [], "ok": False}
    notes = []
    for ann in annotations or []:
        if not (str(ann.get("anchor", "") or "").strip()
                or str(ann.get("note", "") or "").strip()):
            summary["skipped"] += 1
            continue
        notes.append(_note_from_annotation(ann, deck, model))
    if not notes:
        return summary
    if not ensure_deck(deck, url=url, opener=opener):
        return summary
    try:
        # addNotes returns a list of new note ids (null for a rejected dup).
        result = invoke("addNotes", params={"notes": notes}, url=url, opener=opener)
    except (AnkiConnectError, urllib.error.URLError, OSError, ValueError):
        return summary
    ids = [nid for nid in (result or []) if nid is not None]
    summary["note_ids"] = ids
    summary["added"] = len(ids)
    summary["skipped"] += len(notes) - len(ids)
    summary["ok"] = True
    return summary


def pull_review_state(
    deck: str = "star",
    *,
    url: str = DEFAULT_URL,
    opener: Any = None,
) -> Dict[str, Dict[str, Any]]:
    """Pull scheduling state from Anki for notes tagged with a star id.

    Returns ``{star_id: {"interval", "due", "reps", "lapses", "ease"}}`` for
    every card in *deck* whose note carries a ``star::<id>`` tag, so star can
    reflect reviews done inside Anki.  Best-effort: an unreachable Anki yields
    an empty dict, never an exception.
    """
    out: Dict[str, Dict[str, Any]] = {}
    try:
        card_ids = invoke(
            "findCards", params={"query": f'deck:"{deck}" tag:star'},
            url=url, opener=opener,
        )
        if not card_ids:
            return out
        infos = invoke("cardsInfo", params={"cards": card_ids}, url=url, opener=opener)
    except (AnkiConnectError, urllib.error.URLError, OSError, ValueError):
        return out
    for info in infos or []:
        sid = _star_id_from_fields_or_tags(info)
        if not sid:
            continue
        out[sid] = {
            "interval": int(info.get("interval", 0) or 0),
            "due": info.get("due"),
            "reps": int(info.get("reps", 0) or 0),
            "lapses": int(info.get("lapses", 0) or 0),
            # AnkiConnect reports ease factor in permille (2500 = 2.5).
            "ease": (info.get("factor", 0) or 0) / 1000.0,
        }
    return out


def _star_id_from_fields_or_tags(info: Dict[str, Any]) -> str:
    """Extract the ``star::<id>`` id from a cardsInfo record's tags, or ""."""
    for tag in info.get("tags", []) or []:
        if isinstance(tag, str) and tag.startswith("star::"):
            return tag.split("::", 1)[1]
    return ""


def sync_annotations(
    settings: Any,
    deck: str = "star",
    *,
    url: str = DEFAULT_URL,
    opener: Any = None,
) -> Dict[str, Any]:
    """Two-way sync: push all reviewable annotations, then pull Anki's schedule.

    Pushed review state is written back onto each annotation's ``anki`` field
    (a small mirror of Anki's interval/reps/lapses/ease) so the in-app
    dashboard can show it.  Returns ``{"pushed": summary, "pulled": n, "ok": bool}``.
    Offline-safe throughout.
    """
    from .annotations import _save_settings, iter_review_cards

    if not is_available(url=url, opener=opener):
        return {"pushed": {"added": 0, "ok": False}, "pulled": 0, "ok": False}

    anns = [ann for _doc, ann in iter_review_cards(settings)]
    pushed = push_cards(anns, deck, url=url, opener=opener)
    pulled_state = pull_review_state(deck, url=url, opener=opener)

    applied = 0
    for doc, anns_list in (settings["annotations"] or {}).items():
        for ann in anns_list or []:
            sid = str(ann.get("id", "") or "")
            if sid and sid in pulled_state:
                ann["anki"] = pulled_state[sid]
                applied += 1
    if applied:
        _save_settings(settings)
    return {"pushed": pushed, "pulled": applied, "ok": pushed.get("ok", False)}
