"""Tests for sidecar sync conflict detection & merge (star/sync.py).

Pure-logic only: no GUI, no network, no disk I/O.  Covers every policy
(newest / highest_progress / manual), annotation-by-id union, tie-breaking,
robustness to missing/empty/corrupted sidecars, and the guarantee that the
"newest" policy reproduces the prior last-write-wins outcome.
"""
from __future__ import annotations

from star import library
from star.sync import (
    POLICIES,
    Conflict,
    merge_annotations,
    merge_progress,
)


# =============================================================================
# Basic shape / no-conflict identity
# =============================================================================


def test_empty_inputs_yield_empty_merge():
    merged, conflicts = merge_progress({}, {})
    assert merged == {}
    assert conflicts == []


def test_disjoint_keys_are_unioned_without_conflict():
    local = {"a.md": {"pct": 10, "ts": "2026-01-01"}}
    remote = {"b.md": {"pct": 20, "ts": "2026-01-02"}}
    merged, conflicts = merge_progress(local, remote, "newest")
    assert merged["a.md"]["pct"] == 10
    assert merged["b.md"]["pct"] == 20
    assert conflicts == []


def test_identical_entry_is_not_a_conflict():
    entry = {"offset": 5, "pct": 42, "ts": "2026-06-27T10:00:00"}
    local = {"doc.md": dict(entry)}
    remote = {"doc.md": dict(entry)}
    merged, conflicts = merge_progress(local, remote, "newest")
    assert merged["doc.md"] == entry
    assert conflicts == []


def test_one_side_missing_takes_the_other_no_conflict():
    local = {"doc.md": {"pct": 1, "ts": "t1"}}
    merged, conflicts = merge_progress(local, {}, "newest")
    assert merged["doc.md"]["pct"] == 1
    assert conflicts == []
    merged, conflicts = merge_progress({}, local, "newest")
    assert merged["doc.md"]["pct"] == 1
    assert conflicts == []


# =============================================================================
# Policy: newest (default) — reproduces last-write-wins
# =============================================================================


def test_newest_remote_newer_wins():
    local = {"doc.md": {"pct": 10, "ts": "2026-01-01T00:00:00"}}
    remote = {"doc.md": {"pct": 90, "ts": "2026-06-01T00:00:00"}}
    merged, conflicts = merge_progress(local, remote, "newest")
    assert merged["doc.md"]["pct"] == 90
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c.path == "doc.md" and c.field is None and c.resolution == "remote"
    assert c.local["pct"] == 10 and c.remote["pct"] == 90


def test_newest_local_newer_wins():
    local = {"doc.md": {"pct": 88, "ts": "2026-06-01T00:00:00"}}
    remote = {"doc.md": {"pct": 5, "ts": "2026-01-01T00:00:00"}}
    merged, conflicts = merge_progress(local, remote, "newest")
    assert merged["doc.md"]["pct"] == 88
    assert conflicts[0].resolution == "local"


def test_newest_tie_prefers_remote_reproducing_last_write_wins():
    # Historical whole-file overwrite: the arriving (remote) copy replaces local.
    # On an exact timestamp tie, "newest" keeps remote — the same net effect.
    local = {"doc.md": {"pct": 10, "ts": "2026-06-27T10:00:00"}}
    remote = {"doc.md": {"pct": 20, "ts": "2026-06-27T10:00:00"}}
    merged, conflicts = merge_progress(local, remote, "newest")
    assert merged["doc.md"]["pct"] == 20  # remote wins tie
    assert conflicts[0].resolution == "remote"


def test_newest_reproduces_prior_whole_file_overwrite():
    """The exact scenario the old last-write-wins produced: an incoming remote
    sidecar (all newer) fully replaces the local values."""
    local = {
        "a.md": {"pct": 1, "ts": "2026-01-01"},
        "b.md": {"pct": 2, "ts": "2026-01-01"},
    }
    remote = {
        "a.md": {"pct": 11, "ts": "2026-02-01"},
        "b.md": {"pct": 22, "ts": "2026-02-01"},
    }
    merged, _ = merge_progress(local, remote, "newest")
    # Every value now matches remote — identical to overwriting the whole file.
    assert merged["a.md"]["pct"] == 11
    assert merged["b.md"]["pct"] == 22


def test_prefer_local_breaks_tie_toward_local():
    local = {"doc.md": {"pct": 10, "ts": "2026-06-27T10:00:00"}}
    remote = {"doc.md": {"pct": 20, "ts": "2026-06-27T10:00:00"}}
    merged, conflicts = merge_progress(local, remote, "newest", prefer="local")
    assert merged["doc.md"]["pct"] == 10  # tie broken toward local
    assert conflicts[0].resolution == "local"


def test_missing_timestamp_loses_to_timestamped():
    local = {"doc.md": {"pct": 10}}  # no ts → sorts earliest
    remote = {"doc.md": {"pct": 20, "ts": "2026-01-01"}}
    merged, _ = merge_progress(local, remote, "newest")
    assert merged["doc.md"]["pct"] == 20


# =============================================================================
# Policy: highest_progress
# =============================================================================


def test_highest_progress_keeps_max_offset():
    # Remote is *older* but further along — highest_progress keeps it so a quick
    # glance on another device never rewinds the reading position.
    local = {"doc.md": {"offset": 500, "pct": 20, "ts": "2026-06-01"}}
    remote = {"doc.md": {"offset": 5000, "pct": 80, "ts": "2026-01-01"}}
    merged, conflicts = merge_progress(local, remote, "highest_progress")
    assert merged["doc.md"]["offset"] == 5000
    assert conflicts[0].resolution == "remote"


def test_highest_progress_local_further_wins():
    local = {"doc.md": {"offset": 9000, "pct": 95, "ts": "2026-01-01"}}
    remote = {"doc.md": {"offset": 100, "pct": 3, "ts": "2026-06-01"}}
    merged, conflicts = merge_progress(local, remote, "highest_progress")
    assert merged["doc.md"]["offset"] == 9000
    assert conflicts[0].resolution == "local"


def test_highest_progress_falls_back_to_pct_when_no_offset():
    local = {"doc.md": {"pct": 30, "ts": "2026-06-01"}}
    remote = {"doc.md": {"pct": 70, "ts": "2026-01-01"}}
    merged, _ = merge_progress(local, remote, "highest_progress")
    assert merged["doc.md"]["pct"] == 70


def test_highest_progress_equal_position_breaks_by_newest():
    # Same offset → tie broken by newest timestamp (deterministic).
    local = {"doc.md": {"offset": 500, "pct": 50, "ts": "2026-06-01"}}
    remote = {"doc.md": {"offset": 500, "pct": 50, "ts": "2026-01-01"}}
    # pct differs? no — offsets equal, whole entries differ only by ts.
    local["doc.md"]["note"] = "L"
    remote["doc.md"]["note"] = "R"
    merged, conflicts = merge_progress(local, remote, "highest_progress")
    assert merged["doc.md"]["note"] == "L"  # newer ts (local) wins the tie
    assert conflicts[0].resolution == "local"


# =============================================================================
# Policy: manual
# =============================================================================


def test_manual_keeps_local_and_reports_conflict():
    local = {"doc.md": {"pct": 10, "ts": "2026-01-01"}}
    remote = {"doc.md": {"pct": 90, "ts": "2026-06-01"}}
    merged, conflicts = merge_progress(local, remote, "manual")
    assert merged["doc.md"]["pct"] == 10  # local kept, not auto-resolved
    assert len(conflicts) == 1
    assert conflicts[0].resolution == "unresolved"
    assert conflicts[0].local["pct"] == 10 and conflicts[0].remote["pct"] == 90


def test_manual_no_conflict_when_identical():
    entry = {"pct": 5, "ts": "t"}
    merged, conflicts = merge_progress({"d.md": dict(entry)}, {"d.md": dict(entry)}, "manual")
    assert conflicts == []
    assert merged["d.md"] == entry


# =============================================================================
# Unknown policy falls back to newest
# =============================================================================


def test_unknown_policy_falls_back_to_newest():
    local = {"doc.md": {"pct": 10, "ts": "2026-01-01"}}
    remote = {"doc.md": {"pct": 20, "ts": "2026-06-01"}}
    merged, _ = merge_progress(local, remote, "bogus-policy")
    assert merged["doc.md"]["pct"] == 20  # behaves like newest


def test_all_named_policies_are_recognised():
    for p in POLICIES:
        merged, _ = merge_progress({"d.md": {"pct": 1, "ts": "t"}}, {}, p)
        assert merged["d.md"]["pct"] == 1


# =============================================================================
# Annotation / highlight merge by id (union, newest per id)
# =============================================================================


def test_annotations_disjoint_ids_both_kept():
    local = {"annotations": [{"id": "a1", "note": "hello", "ts": "2026-01-01"}]}
    remote = {"annotations": [{"id": "b2", "note": "world", "ts": "2026-01-02"}]}
    merged, conflicts = merge_progress(local, remote, "newest")
    ids = {a["id"] for a in merged["annotations"]}
    assert ids == {"a1", "b2"}  # both survive
    assert conflicts == []  # disjoint ids never conflict


def test_annotations_same_id_newest_content_wins():
    local = {"annotations": [{"id": "x", "note": "old note", "ts": "2026-01-01"}]}
    remote = {"annotations": [{"id": "x", "note": "edited note", "ts": "2026-06-01"}]}
    merged, conflicts = merge_progress(local, remote, "newest")
    (ann,) = merged["annotations"]
    assert ann["note"] == "edited note"  # newer remote edit wins
    assert len(conflicts) == 1
    assert conflicts[0].field == "x" and conflicts[0].resolution == "remote"


def test_annotations_same_id_local_newer_wins():
    local = {"annotations": [{"id": "x", "note": "local edit", "ts": "2026-06-01"}]}
    remote = {"annotations": [{"id": "x", "note": "stale", "ts": "2026-01-01"}]}
    merged, conflicts = merge_progress(local, remote, "newest")
    (ann,) = merged["annotations"]
    assert ann["note"] == "local edit"
    assert conflicts[0].resolution == "local"


def test_annotations_edits_on_two_devices_both_survive():
    # Device A adds a1 and edits shared; device B adds b1 and edits shared older.
    local = {
        "annotations": [
            {"id": "shared", "note": "A's newer text", "ts": "2026-06-02"},
            {"id": "a1", "note": "A only", "ts": "2026-06-02"},
        ]
    }
    remote = {
        "annotations": [
            {"id": "shared", "note": "B's older text", "ts": "2026-06-01"},
            {"id": "b1", "note": "B only", "ts": "2026-06-01"},
        ]
    }
    merged, _ = merge_progress(local, remote, "newest")
    by_id = {a["id"]: a for a in merged["annotations"]}
    assert set(by_id) == {"shared", "a1", "b1"}  # nothing lost
    assert by_id["shared"]["note"] == "A's newer text"  # newest edit kept
    assert by_id["a1"]["note"] == "A only"
    assert by_id["b1"]["note"] == "B only"


def test_annotations_identical_same_id_no_conflict():
    ann = {"id": "x", "note": "same", "ts": "t"}
    local = {"annotations": [dict(ann)]}
    remote = {"annotations": [dict(ann)]}
    merged, conflicts = merge_progress(local, remote, "newest")
    assert len(merged["annotations"]) == 1
    assert conflicts == []


def test_annotations_idless_entries_kept_from_both_sides():
    local = {"annotations": [{"note": "no id local", "ts": "t"}]}
    remote = {"annotations": [{"note": "no id remote", "ts": "t"}]}
    merged, _ = merge_progress(local, remote, "newest")
    notes = sorted(a["note"] for a in merged["annotations"])
    assert notes == ["no id local", "no id remote"]  # neither dropped


def test_annotations_merge_ignores_progress_policy():
    # Even under highest_progress, annotation lists still merge by id.
    local = {"annotations": [{"id": "x", "note": "L", "ts": "2026-06-01"}]}
    remote = {"annotations": [{"id": "y", "note": "R", "ts": "2026-01-01"}]}
    merged, _ = merge_progress(local, remote, "highest_progress")
    assert {a["id"] for a in merged["annotations"]} == {"x", "y"}


def test_merge_annotations_helper_preserves_order_local_first():
    local = [{"id": "1", "ts": "t"}, {"id": "2", "ts": "t"}]
    remote = [{"id": "3", "ts": "t"}, {"id": "2", "ts": "t"}]
    out = merge_annotations("k", local, remote)
    assert [a["id"] for a in out] == ["1", "2", "3"]  # local order, then remote-only


def test_highlights_key_also_merges_by_id():
    local = {"highlights": [{"id": "h1", "color": "cyan", "ts": "2026-01-01"}]}
    remote = {"highlights": [{"id": "h1", "color": "yellow", "ts": "2026-06-01"}]}
    merged, conflicts = merge_progress(local, remote, "newest")
    (h,) = merged["highlights"]
    assert h["color"] == "yellow"  # newest edit
    assert conflicts[0].field == "h1"


def test_list_valued_key_under_any_name_merges_by_id():
    # A list value signals an annotation collection even under an odd key name.
    local = {"my_notes": [{"id": "n1", "ts": "t"}]}
    remote = {"my_notes": [{"id": "n2", "ts": "t"}]}
    merged, _ = merge_progress(local, remote, "newest")
    assert {a["id"] for a in merged["my_notes"]} == {"n1", "n2"}


# =============================================================================
# _meta namespace merge
# =============================================================================


def test_meta_namespace_merges_rel_by_rel_newest():
    local = {"_meta": {"a.md": {"seconds": 10, "last_ts": "2026-01-01"}}}
    remote = {"_meta": {"a.md": {"seconds": 99, "last_ts": "2026-06-01"},
                        "b.md": {"seconds": 5, "last_ts": "2026-01-01"}}}
    merged, conflicts = merge_progress(local, remote, "newest")
    assert merged["_meta"]["a.md"]["seconds"] == 99  # newer remote wins
    assert merged["_meta"]["b.md"]["seconds"] == 5    # remote-only kept
    assert any(c.path == "_meta" and c.field == "a.md" for c in conflicts)


def test_meta_uses_last_ts_for_recency():
    local = {"_meta": {"a.md": {"seconds": 100, "last_ts": "2026-06-01"}}}
    remote = {"_meta": {"a.md": {"seconds": 1, "last_ts": "2026-01-01"}}}
    merged, _ = merge_progress(local, remote, "newest")
    assert merged["_meta"]["a.md"]["seconds"] == 100  # local newer


# =============================================================================
# Robustness: missing / empty / corrupted sidecars
# =============================================================================


def test_none_inputs_treated_as_empty():
    merged, conflicts = merge_progress(None, None, "newest")
    assert merged == {} and conflicts == []
    merged, _ = merge_progress(None, {"d.md": {"pct": 1, "ts": "t"}}, "newest")
    assert merged["d.md"]["pct"] == 1


def test_non_dict_top_level_input_is_ignored():
    # A corrupted sidecar that parsed to a list / string / int contributes nothing.
    for junk in ([1, 2, 3], "corrupt", 42, 3.14):
        merged, conflicts = merge_progress({"d.md": {"pct": 5, "ts": "t"}}, junk, "newest")
        assert merged["d.md"]["pct"] == 5
        assert conflicts == []
        merged, _ = merge_progress(junk, {"d.md": {"pct": 9, "ts": "t"}}, "newest")
        assert merged["d.md"]["pct"] == 9


def test_corrupt_entry_value_does_not_crash():
    # An entry whose value is not a dict (half-synced) still merges safely.
    local = {"d.md": "not-a-dict"}
    remote = {"d.md": {"pct": 7, "ts": "2026-06-01"}}
    merged, conflicts = merge_progress(local, remote, "newest")
    # Remote has a real ts, local's non-dict sorts earliest → remote wins.
    assert merged["d.md"]["pct"] == 7
    assert conflicts[0].resolution == "remote"


def test_corrupt_annotation_value_does_not_crash():
    local = {"annotations": "corrupt"}
    remote = {"annotations": [{"id": "x", "ts": "t"}]}
    merged, _ = merge_progress(local, remote, "newest")
    assert [a["id"] for a in merged["annotations"]] == ["x"]


def test_corrupt_meta_value_does_not_crash():
    local = {"_meta": "corrupt"}
    remote = {"_meta": {"a.md": {"seconds": 3, "last_ts": "t"}}}
    merged, _ = merge_progress(local, remote, "newest")
    assert merged["_meta"]["a.md"]["seconds"] == 3


def test_valid_progress_dict_survives_a_corrupt_list_on_the_other_side():
    """BUG 3: a valid progress *dict* opposed by a corrupt *list* must keep the
    dict, not route to merge_annotations (which would coerce the dict to [] and
    return the garbage list, silently dropping reading progress)."""
    valid = {"offset": 4321, "pct": 55, "ts": "2026-06-30T09:00:00"}
    # local side has the real reading progress; remote side is a corrupt list.
    merged, _ = merge_progress({"a": dict(valid)}, {"a": ["garbage"]}, "newest",
                               prefer="local")
    assert merged["a"] == valid, "valid progress dict must not be discarded"
    # Symmetric: corrupt list on the local side, valid dict on the remote side.
    merged, _ = merge_progress({"a": ["garbage"]}, {"a": dict(valid)}, "newest")
    assert merged["a"] == valid


def test_dict_vs_list_never_routes_to_annotation_merge():
    """The list-vs-dict mismatch is corruption, not an annotation collection:
    _is_annotation_list returns False so the dict survives via _merge_entry."""
    from star.sync import _is_annotation_list

    assert _is_annotation_list({"offset": 1}, ["x"]) is False
    assert _is_annotation_list(["x"], {"offset": 1}) is False
    # Genuine annotation shapes (list-vs-list, list-vs-None) still merge by id.
    assert _is_annotation_list([{"id": "a"}], [{"id": "b"}]) is True
    assert _is_annotation_list([{"id": "a"}], None) is True
    assert _is_annotation_list(None, [{"id": "a"}]) is True


def test_boolean_offset_not_mistaken_for_number():
    # bool is a subclass of int; ensure a stray True/False isn't treated as a
    # reading position under highest_progress.
    local = {"d.md": {"offset": True, "pct": 5, "ts": "2026-01-01"}}
    remote = {"d.md": {"offset": 100, "pct": 50, "ts": "2026-06-01"}}
    merged, _ = merge_progress(local, remote, "highest_progress")
    assert merged["d.md"]["offset"] == 100  # real offset beats bool


# =============================================================================
# Conflict dataclass shape
# =============================================================================


def test_conflict_dataclass_fields():
    c = Conflict("doc.md", "pct", {"pct": 1}, {"pct": 2}, "remote")
    assert c.path == "doc.md"
    assert c.field == "pct"
    assert c.local == {"pct": 1}
    assert c.remote == {"pct": 2}
    assert c.resolution == "remote"


def test_conflict_default_resolution_is_unresolved():
    c = Conflict("doc.md", None, 1, 2)
    assert c.resolution == "unresolved"


# =============================================================================
# library.py integration: no-conflict behaviour is identical to before
# =============================================================================


def test_meta_key_constant_matches_library():
    # The two _META_KEY constants must agree or the sidecar merge would treat the
    # reserved metadata namespace as a document entry.
    from star import sync
    assert sync._META_KEY == library._META_KEY


def test_reconcile_before_write_no_remote_returns_local(tmp_path):
    folder = tmp_path / "lib"
    (folder / ".star").mkdir(parents=True)
    local = {"a.md": {"pct": 5, "ts": "t"}}
    # No on-disk sidecar yet → local written unchanged.
    out = library._reconcile_before_write(folder, local, "newest")
    assert out == local


def test_reconcile_before_write_local_edit_survives_equal_ts(tmp_path):
    # A concurrent sync wrote the same document with an equal timestamp; the
    # local pending edit (prefer=local on the write path) must not be clobbered.
    import json
    folder = tmp_path / "lib"
    star_dir = folder / ".star"
    star_dir.mkdir(parents=True)
    (star_dir / "progress.json").write_text(
        json.dumps({"a.md": {"pct": 10, "ts": "2026-06-27T10:00:00"}}),
        encoding="utf-8",
    )
    local = {"a.md": {"pct": 40, "ts": "2026-06-27T10:00:00"}}
    out = library._reconcile_before_write(folder, local, "newest")
    assert out["a.md"]["pct"] == 40  # local kept on the write path


def test_reconcile_before_write_newer_remote_survives(tmp_path):
    # A sync wrote a genuinely newer entry for a *different* doc; it must be
    # preserved (not clobbered) when we flush our local payload.
    import json
    folder = tmp_path / "lib"
    star_dir = folder / ".star"
    star_dir.mkdir(parents=True)
    (star_dir / "progress.json").write_text(
        json.dumps({"other.md": {"pct": 77, "ts": "2026-06-30"}}),
        encoding="utf-8",
    )
    local = {"a.md": {"pct": 40, "ts": "2026-06-27"}}
    out = library._reconcile_before_write(folder, local, "newest")
    assert out["a.md"]["pct"] == 40
    assert out["other.md"]["pct"] == 77  # remote-only entry survived


def test_conflict_policy_default(tmp_path, monkeypatch):
    from star import settings as settings_mod
    from star.settings import Settings
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    s = Settings()
    # Key absent from DEFAULTS → helper still returns the safe default.
    assert library._conflict_policy(s) == "newest"
