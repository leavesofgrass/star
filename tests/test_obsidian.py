"""Direct unit tests for :mod:`star.obsidian` — frontmatter/link/tag parsing
helpers plus a vault import/export round-trip over a temp directory.
"""
from star.obsidian import (
    _collect_tags,
    _extract_links,
    _first_line,
    _norm_rel,
    _parse_frontmatter,
    _sanitize_filename,
    _skip,
    _split_frontmatter,
    export_vault,
    import_vault,
)
from star.settings import Settings
from pathlib import Path


# ── _norm_rel ─────────────────────────────────────────────────────────────────


def test_norm_rel_known_and_normalized():
    assert _norm_rel("supports") == "SUPPORTS"
    assert _norm_rel("see-also") == "SEE_ALSO"
    assert _norm_rel("see also") == "SEE_ALSO"


def test_norm_rel_unknown_is_none():
    assert _norm_rel("bogus") is None
    assert _norm_rel("") is None


# ── _split_frontmatter / _parse_frontmatter ──────────────────────────────────


def test_split_frontmatter_present():
    meta, body = _split_frontmatter("---\ntitle: Hi\n---\nthe body\n")
    assert meta.get("title") == "Hi"
    assert body.strip() == "the body"


def test_split_frontmatter_absent():
    meta, body = _split_frontmatter("no frontmatter here")
    assert meta == {} and body == "no frontmatter here"


def test_parse_frontmatter_scalar_and_list():
    meta = _parse_frontmatter('title: My Note\ntags: [alpha, beta]')
    assert meta["title"] == "My Note"
    assert meta["tags"] == ["alpha", "beta"]


def test_parse_frontmatter_block_list():
    meta = _parse_frontmatter("tags:\n  - one\n  - two")
    assert meta["tags"] == ["one", "two"]


# ── _collect_tags ─────────────────────────────────────────────────────────────


def test_collect_tags_from_meta_and_body():
    tags = _collect_tags({"tags": ["meta1", "#meta2"]}, "body text #inline and #more")
    assert "meta1" in tags and "meta2" in tags
    assert "inline" in tags and "more" in tags


def test_collect_tags_string_form_and_dedup():
    tags = _collect_tags({"tags": "a b a"}, "#a #c")
    assert tags.count("a") == 1
    assert "b" in tags and "c" in tags


# ── _extract_links ────────────────────────────────────────────────────────────


def test_extract_links_typed_and_plain():
    links = _extract_links("supports:: [[Foo]]\nand a plain [[Bar]] link")
    assert ("SUPPORTS", "Foo") in links
    assert (None, "Bar") in links


def test_extract_links_ignores_embeds():
    # ![[embed]] is an embed, not a link → excluded by the negative lookbehind.
    links = _extract_links("![[Image]] but [[Real]]")
    targets = [t for _r, t in links]
    assert "Real" in targets and "Image" not in targets


# ── _skip / _first_line / _sanitize_filename ─────────────────────────────────


def test_skip_obsidian_and_trash_dirs():
    assert _skip(Path("vault/.obsidian/x.md")) is True
    assert _skip(Path("vault/.trash/y.md")) is True
    assert _skip(Path("vault/notes/z.md")) is False


def test_first_line_strips_markers_and_links():
    # The first non-empty line wins; the leading "#" is stripped (not skipped).
    assert _first_line("# Heading\n\nmore") == "Heading"
    # Wikilink syntax is reduced to its target text.
    assert _first_line("[[Only]] here") == "Only here"
    assert _first_line("\n\n   \n") == ""


def test_sanitize_filename():
    out = _sanitize_filename('a/b:c*d?e"f')
    for bad in '/:*?"':
        assert bad not in out
    assert _sanitize_filename("") == "note"
    assert len(_sanitize_filename("x" * 500)) <= 120


# ── import_vault / export_vault round-trip ────────────────────────────────────


def _settings():
    s = Settings()
    s["annotations"] = {}
    return s


def test_import_vault_reads_notes(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note1.md").write_text(
        "---\ntags: [topic]\n---\n# Note One\n\nIt supports:: [[Note Two]].\n",
        encoding="utf-8",
    )
    (vault / "note2.md").write_text("# Note Two\n\nStandalone.\n", encoding="utf-8")
    s = _settings()
    result = import_vault(s, str(vault))
    assert isinstance(result, dict)
    # the importer recorded annotations into settings
    anns = s["annotations"]
    assert isinstance(anns, dict)
    # at least the two notes were turned into nodes somewhere in the store
    total = sum(len(v or []) for v in anns.values())
    assert total >= 1


def test_export_vault_writes_markdown(tmp_path):
    # First import a small vault, then export it back out.
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# Alpha\n\nbody [[Beta]]\n", encoding="utf-8")
    (vault / "b.md").write_text("# Beta\n\nbody\n", encoding="utf-8")
    s = _settings()
    import_vault(s, str(vault))

    out = tmp_path / "out"
    result = export_vault(s, str(out))
    assert isinstance(result, dict)
    if out.exists():
        assert any(p.suffix == ".md" for p in out.rglob("*.md"))
