"""Direct unit tests for :mod:`star.citations` — the pure citation
parsers/formatters and ISBN validation.  The network lookups
(``_fetch_metadata_by_isbn`` / ``_fetch_citation_by_doi``) are intentionally
not exercised here.
"""
import json

from star.citations import (
    _citation_label,
    _format_citations,
    _import_citations,
    _parse_bibtex,
    _parse_csl_json,
    _parse_ris,
    _valid_isbn,
)


# ── _citation_label ───────────────────────────────────────────────────────────


def test_citation_label_full():
    label = _citation_label(
        {"id": "Doe2020", "author": "Doe, Jane and Roe, R", "year": "2020", "title": "On X"}
    )
    assert label.startswith("[Doe2020]")
    assert "Doe" in label and "(2020)" in label and "On X" in label


def test_citation_label_untitled():
    assert _citation_label({}) == "(untitled)"


# ── _parse_bibtex ─────────────────────────────────────────────────────────────


def test_parse_bibtex_basic():
    bib = (
        "@article{key1,\n"
        "  title = {A Great Paper},\n"
        "  author = {Doe, Jane},\n"
        "  year = {2021},\n"
        "  booktitle = {Proc of Things},\n"
        "  doi = {10.1/x},\n"
        "}\n"
    )
    items = _parse_bibtex(bib)
    assert len(items) == 1
    c = items[0]
    assert c["id"] == "key1" and c["type"] == "article"
    assert c["title"] == "A Great Paper"
    assert c["author"] == "Doe, Jane"
    assert c["year"] == "2021"
    assert c["journal"] == "Proc of Things"  # booktitle → journal
    assert c["doi"] == "10.1/x"


def test_parse_bibtex_multiple_entries():
    bib = "@book{a, title={One}}\n@article{b, title={Two}}\n"
    items = _parse_bibtex(bib)
    assert [c["id"] for c in items] == ["a", "b"]


# ── _parse_ris ────────────────────────────────────────────────────────────────


def test_parse_ris_basic():
    ris = (
        "TY  - JOUR\n"
        "TI  - A Title\n"
        "AU  - Doe, Jane\n"
        "AU  - Roe, Rick\n"
        "PY  - 2019/01/01\n"
        "DO  - 10.2/y\n"
        "ER  - \n"
    )
    items = _parse_ris(ris)
    assert len(items) == 1
    c = items[0]
    assert c["title"] == "A Title"
    assert c["author"] == "Doe, Jane and Roe, Rick"
    assert c["year"] == "2019"  # truncated to 4 chars
    assert c["doi"] == "10.2/y"
    assert c["id"]  # auto-generated from author+year


# ── _parse_csl_json ───────────────────────────────────────────────────────────


def test_parse_csl_json_basic():
    csl = json.dumps(
        [
            {
                "id": "x1",
                "type": "article-journal",
                "title": "CSL Title",
                "author": [{"family": "Doe", "given": "Jane"}],
                "issued": {"date-parts": [[2018, 5]]},
                "container-title": "J. Things",
                "DOI": "10.3/z",
            }
        ]
    )
    items = _parse_csl_json(csl)
    c = items[0]
    assert c["id"] == "x1"
    assert c["title"] == "CSL Title"
    assert c["author"] == "Doe, Jane"
    assert c["year"] == "2018"
    assert c["journal"] == "J. Things"
    assert c["doi"] == "10.3/z"


def test_parse_csl_json_accepts_single_object():
    items = _parse_csl_json(json.dumps({"id": "solo", "title": "T"}))
    assert len(items) == 1 and items[0]["id"] == "solo"


# ── _import_citations (by extension + content heuristic) ──────────────────────


def test_import_citations_by_extension(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text("@misc{m, title={M}}\n", encoding="utf-8")
    assert _import_citations(str(bib))[0]["id"] == "m"

    ris = tmp_path / "refs.ris"
    ris.write_text("TY  - JOUR\nTI  - R\nER  - \n", encoding="utf-8")
    assert _import_citations(str(ris))[0]["title"] == "R"


def test_import_citations_content_heuristic(tmp_path):
    # Unknown extension → sniff by content (starts with @ → BibTeX).
    p = tmp_path / "refs.txt"
    p.write_text("@article{z, title={Zed}}\n", encoding="utf-8")
    assert _import_citations(str(p))[0]["title"] == "Zed"


# ── _format_citations ─────────────────────────────────────────────────────────


_ITEM = {
    "id": "Doe2020",
    "type": "article",
    "title": "On X",
    "author": "Doe, Jane and Roe, Rick",
    "year": "2020",
    "journal": "J. X",
    "doi": "10.1/x",
}


def test_format_bibtex():
    out = _format_citations([_ITEM], ".bib")
    assert "@article{Doe2020," in out
    assert "title = {On X}" in out
    assert "doi = {10.1/x}" in out


def test_format_ris():
    out = _format_citations([_ITEM], ".ris")
    assert "TY  - ARTICLE" in out
    assert "TI  - On X" in out
    assert "AU  - Doe, Jane" in out and "AU  - Roe, Rick" in out
    assert out.rstrip().endswith("ER  -")


def test_format_csl_json_is_valid_json():
    out = _format_citations([_ITEM], ".json")
    data = json.loads(out)
    assert data[0]["id"] == "Doe2020"
    assert data[0]["author"][0] == {"family": "Doe", "given": "Jane"}
    assert data[0]["issued"] == {"date-parts": [["2020"]]}


def test_format_roundtrip_bibtex():
    out = _format_citations([_ITEM], ".bib")
    back = _parse_bibtex(out)[0]
    assert back["title"] == "On X" and back["author"] == "Doe, Jane and Roe, Rick"


# ── _valid_isbn ───────────────────────────────────────────────────────────────


def test_valid_isbn10():
    assert _valid_isbn("0306406152") is True
    assert _valid_isbn("080442957X") is True  # X check digit


def test_valid_isbn13():
    assert _valid_isbn("9780306406157") is True


def test_valid_isbn_strips_hyphens_and_spaces():
    assert _valid_isbn("978-0-306-40615-7") is True
    assert _valid_isbn(" 0 306 406152 ") is True


def test_invalid_isbn():
    assert _valid_isbn("0306406153") is False  # bad ISBN-10 checksum
    assert _valid_isbn("9780306406158") is False  # bad ISBN-13 checksum
    assert _valid_isbn("not-an-isbn") is False
    assert _valid_isbn("12345") is False
