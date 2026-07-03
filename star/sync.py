"""Sync conflict detection & merge for ``.star/`` sidecars.

star's library sidecars (``.star/progress.json``) live inside the library
folder and therefore travel through whatever cloud sync the user already runs
(Dropbox / OneDrive / Syncthing / iCloud).  That is convenient but exposes the
classic distributed-editing hazard: read a document on your laptop, read the
same document on your desktop while offline, and when both machines sync their
sidecars back, one machine's copy silently overwrites the other's — a
last-write-wins clobber that can lose reading progress or, worse, annotations.

This module supplies the **pure, GUI-free** reconciliation the caller runs when
it has both the *local* sidecar mapping and an incoming *remote* one.  It is
dependency-free and does no I/O: it takes two dicts and returns the merged dict
plus a list of :class:`Conflict` records describing every field that diverged.

Merge policy for per-document progress entries is selectable:

``newest``           Newer timestamp wins (preserves the historical
                     last-write-wins behaviour exactly — the default).
``highest_progress`` The furthest reading position wins, so glancing at a
                     document on a second device never rewinds your place.
``manual``           Neither side is auto-chosen: the merged doc keeps the
                     local value and every divergence is reported as a
                     :class:`Conflict` for the caller to resolve (no GUI here).

Annotations/highlights are merged **by id** (a union, newest wins per id)
rather than whole-list overwrite, so edits made independently on two devices
both survive instead of one device's list replacing the other's.

Everything is robust to missing / empty / corrupted input: a value that is not
a dict (a partially-synced or hand-corrupted sidecar) is treated as empty and
the other side is taken verbatim.
"""
from ._runtime import *  # noqa: F401,F403

# Recognised conflict-resolution policies for per-document progress entries.
POLICIES = ("newest", "highest_progress", "manual")

# The reserved namespace key the library sidecar uses for cross-device metadata
# (portable reading stats + annotation count).  Mirrored here rather than
# imported so this module stays free of any library.py import cycle; the two
# constants must agree (a test pins them together).
_META_KEY = "_meta"

# Sidecar keys whose *values are lists of annotation/highlight dicts* rather than
# a single progress entry.  These are merged by id (union) instead of by policy.
# A sidecar need not carry any of these — plain progress.json files only hold
# ``{rel: {offset, pct, ts}}`` — but when a future sidecar does embed annotation
# lists, they reconcile edit-safely.
_ANNOTATION_KEYS = ("annotations", "highlights", "user_highlights")


@dataclass
class Conflict:
    """A single field that diverged between the local and remote sidecar.

    ``path`` is the sidecar key (a document's relative path, or a reserved
    namespace such as ``_meta``); ``field`` names the diverging sub-field within
    that entry (e.g. ``"pct"``), or is ``None`` when the whole entry conflicts.
    ``local`` / ``remote`` carry the two competing values, and ``resolution``
    records which side the merge kept (``"local"``, ``"remote"``, ``"merged"``,
    or ``"unresolved"`` under the ``manual`` policy).
    """

    path: str
    field: "Optional[str]"
    local: Any
    remote: Any
    resolution: str = "unresolved"


def _as_dict(value: Any) -> Dict[str, Any]:
    """Coerce *value* to a dict, treating anything else (None / corrupt / list)
    as empty.  This is what makes the merge robust to a half-synced or
    hand-mangled sidecar: a non-dict side simply contributes nothing."""
    return value if isinstance(value, dict) else {}


def _ts_key(entry: Any) -> str:
    """Sortable timestamp string for a progress *entry* ("" when absent).

    Progress entries carry their write time under ``ts`` (raw progress) or
    ``last_ts`` (the portable ``_meta`` stat block); annotations use ``ts``.
    ISO-8601 timestamps sort correctly as plain strings, so no parsing is
    needed.  A missing timestamp sorts *earliest* (loses ties), which is the
    safe choice — an entry that never recorded when it was written should not
    beat one that did.
    """
    if not isinstance(entry, dict):
        return ""
    ts = entry.get("ts")
    if ts is None:
        ts = entry.get("last_ts")
    return str(ts) if ts is not None else ""


def _progress_value(entry: Any) -> float:
    """Numeric reading position for *entry* for the ``highest_progress`` policy.

    Prefers an explicit character/word ``offset`` (finer-grained than a rounded
    percentage), then falls back to ``pct``.  A non-numeric or missing value is
    treated as ``-1`` so any real position beats it.
    """
    if not isinstance(entry, dict):
        return -1.0
    for field in ("offset", "pct"):
        v = entry.get(field)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return -1.0


def _merge_entry(
    key: str,
    local: Any,
    remote: Any,
    policy: str,
    conflicts: "List[Conflict]",
    prefer: str = "remote",
) -> Any:
    """Reconcile one document's *local* and *remote* progress entry per *policy*.

    Records a :class:`Conflict` (with the chosen resolution) whenever the two
    sides both exist and actually differ.  Returns the winning entry.  *prefer*
    breaks exact timestamp ties (see :func:`_newest`).
    """
    # One side missing → take the other verbatim, no conflict.
    if remote is None:
        return local
    if local is None:
        return remote
    if local == remote:
        return local  # identical — nothing to resolve

    if policy == "highest_progress":
        lp, rp = _progress_value(local), _progress_value(remote)
        if rp > lp:
            winner, res = remote, "remote"
        elif lp > rp:
            winner, res = local, "local"
        else:
            # Equal position → fall back to newest so a tie is still broken
            # deterministically rather than arbitrarily favouring one side.
            winner, res = _newest(local, remote, prefer)
        conflicts.append(Conflict(key, None, local, remote, res))
        return winner

    if policy == "manual":
        # Report but do not auto-choose: keep the local value so the caller can
        # present both and let the user decide.
        conflicts.append(Conflict(key, None, local, remote, "unresolved"))
        return local

    # Default / "newest": newer timestamp wins (historical behaviour).
    winner, res = _newest(local, remote, prefer)
    conflicts.append(Conflict(key, None, local, remote, res))
    return winner


def _newest(local: Any, remote: Any, prefer: str = "remote") -> "Tuple[Any, str]":
    """Return ``(winner, "local"|"remote")`` by comparing timestamps.

    On a strict timestamp comparison the newer side wins.  On an exact tie the
    *prefer* side wins: ``"remote"`` (the default) reproduces last-write-wins for
    the reader direction — the remote copy is the one *arriving* in a sync, so
    treating it as "the last write" keeps the incoming value, the same outcome
    the old whole-file overwrite produced.  ``"local"`` is used on the write path
    where the local pending payload is by construction the freshest local edit
    and must not be discarded by a same-timestamp on-disk entry.
    """
    lt, rt = _ts_key(local), _ts_key(remote)
    if rt > lt:
        return remote, "remote"
    if lt > rt:
        return local, "local"
    # Exact tie — break toward the preferred side.
    if prefer == "local":
        return local, "local"
    return remote, "remote"


def _ann_id(ann: Any) -> "Optional[str]":
    """Stable id of an annotation dict, or ``None`` when it has none/is not a dict."""
    if isinstance(ann, dict):
        aid = ann.get("id")
        if aid:
            return str(aid)
    return None


def merge_annotations(
    key: str,
    local: Any,
    remote: Any,
    conflicts: "Optional[List[Conflict]]" = None,
    prefer: str = "remote",
) -> "List[Any]":
    """Union two annotation/highlight lists **by id** (newest wins per id).

    Annotations with matching ``id`` are the *same* annotation edited on two
    devices; the newer ``ts`` wins and a :class:`Conflict` is logged when they
    differ.  Ids present on only one side are kept (both devices' new work
    survives).  Id-less entries (legacy or ad-hoc) are appended verbatim from
    both sides — without an id there is no safe way to dedupe them, and dropping
    them would silently lose data.  Insertion order is preserved: local ids
    first (in their original order), then remote-only ids.
    """
    llist = local if isinstance(local, list) else []
    rlist = remote if isinstance(remote, list) else []

    remote_by_id: Dict[str, Any] = {}
    remote_idless: List[Any] = []
    for ann in rlist:
        aid = _ann_id(ann)
        if aid is None:
            remote_idless.append(ann)
        else:
            remote_by_id[aid] = ann  # last duplicate id on the remote side wins

    merged: List[Any] = []
    seen: set = set()
    for ann in llist:
        aid = _ann_id(ann)
        if aid is None:
            merged.append(ann)  # id-less local entry — keep as-is
            continue
        seen.add(aid)
        r = remote_by_id.get(aid)
        if r is None or r == ann:
            merged.append(ann)  # only local has it, or both identical
        else:
            winner, res = _newest(ann, r, prefer)
            if conflicts is not None:
                conflicts.append(Conflict(key, aid, ann, r, res))
            merged.append(winner)

    # Remote-only ids (not seen on the local side), in remote order.
    for ann in rlist:
        aid = _ann_id(ann)
        if aid is not None and aid not in seen:
            merged.append(ann)
            seen.add(aid)

    # Id-less remote entries last (cannot be deduped against local id-less ones).
    merged.extend(remote_idless)
    return merged


def _merge_meta(
    local: Any, remote: Any, conflicts: "List[Conflict]", prefer: str = "remote"
) -> Dict[str, Any]:
    """Merge the reserved ``_meta`` namespace (per-rel portable stat blocks).

    Each ``_meta`` value is itself a ``{rel: {seconds, pct, last_ts, …}}`` map,
    so we reconcile it rel-by-rel with newest-wins (the metadata is a snapshot,
    not a reading position — highest_progress/manual do not apply to it).
    """
    lmeta, rmeta = _as_dict(local), _as_dict(remote)
    out: Dict[str, Any] = dict(lmeta)
    for rel, r_entry in rmeta.items():
        l_entry = lmeta.get(rel)
        if l_entry is None or l_entry == r_entry:
            out[rel] = r_entry if l_entry is None else l_entry
        else:
            winner, res = _newest(l_entry, r_entry, prefer)
            conflicts.append(Conflict(_META_KEY, rel, l_entry, r_entry, res))
            out[rel] = winner
    return out


def merge_progress(
    local: Any,
    remote: Any,
    policy: str = "newest",
    prefer: str = "remote",
) -> "Tuple[Dict[str, Any], List[Conflict]]":
    """Reconcile a *local* and *remote* sidecar mapping under *policy*.

    Returns ``(merged, conflicts)`` where *merged* is the combined sidecar dict
    and *conflicts* lists every field that diverged (with the resolution the
    merge applied).  When there is no divergence the merged output is behaviour-
    identical to the input and *conflicts* is empty.

    * ``policy`` ∈ :data:`POLICIES`.  An unknown policy falls back to ``newest``.
    * Per-document progress entries reconcile by *policy*.
    * Annotation/highlight *lists* (see :data:`_ANNOTATION_KEYS`) always merge
      by id (union, newest per id) regardless of *policy* — losing an edit is
      never acceptable, whereas a reading position is safely pickable.
    * The reserved ``_meta`` namespace merges rel-by-rel, newest wins.
    * Missing / empty / corrupted (non-dict) input on either side is treated as
      an empty mapping, so the other side is taken verbatim.
    * ``prefer`` breaks exact timestamp ties: ``"remote"`` (default) keeps the
      incoming/remote value (reader/last-write-wins direction); ``"local"`` keeps
      the local value (the write direction, where the local pending payload is
      the freshest edit and must not be lost to an equal-timestamp on-disk copy).
    """
    if policy not in POLICIES:
        policy = "newest"
    lmap, rmap = _as_dict(local), _as_dict(remote)
    conflicts: List[Conflict] = []
    merged: Dict[str, Any] = {}

    # Preserve local insertion order first, then append remote-only keys, so a
    # no-conflict merge round-trips to a stable, diff-friendly ordering.
    keys: List[str] = list(lmap.keys())
    for k in rmap:
        if k not in lmap:
            keys.append(k)

    for key in keys:
        lval = lmap.get(key)
        rval = rmap.get(key)
        if key == _META_KEY:
            merged[key] = _merge_meta(lval, rval, conflicts, prefer)
        elif key in _ANNOTATION_KEYS or _is_annotation_list(lval, rval):
            merged[key] = merge_annotations(key, lval, rval, conflicts, prefer)
        else:
            merged[key] = _merge_entry(key, lval, rval, policy, conflicts, prefer)
    return merged, conflicts


def _is_annotation_list(local: Any, remote: Any) -> bool:
    """True when this key should merge by id (an annotation/highlight list) rather
    than by policy.

    Progress entries are always dicts, so a list value signals an annotation
    collection — *unless the other side is a dict*.  A list-vs-dict pairing is not
    two views of the same annotation collection; it is corruption (one sidecar was
    half-written or hand-mangled).  Routing that to :func:`merge_annotations` would
    coerce the dict to ``[]`` and return the corrupt list, silently dropping a
    valid progress entry.  Returning False here instead sends it to
    :func:`_merge_entry`, whose "non-dict side is empty, keep the other verbatim"
    contract preserves the valid dict.  Genuine annotation keys still route by
    ``key in _ANNOTATION_KEYS`` at the call site; list-vs-list and list-vs-None
    still merge by id here.
    """
    if isinstance(local, dict) or isinstance(remote, dict):
        return False
    return isinstance(local, list) or isinstance(remote, list)
