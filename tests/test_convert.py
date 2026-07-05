"""Tests for the batch-conversion core (``star.convert``).

Covers the export-format registry/validation, single-file conversion with
collision-safe naming, and — most importantly — batch failure isolation: a
single broken file must not abort the batch, and its real error must be
recorded and persisted to the summary log.
"""

from pathlib import Path

import pytest

from star import convert
from star.settings import Settings


@pytest.fixture
def settings():
    s = Settings()
    # Deterministic, side-effect-free conversions: never touch the user cache.
    s._data["document_cache"] = False
    return s


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_supported_formats_and_resolve():
    assert set(convert.supported_formats()) == {"markdown", "text", "braille"}
    assert convert.resolve_format("md") == "markdown"
    assert convert.resolve_format(".TXT") == "text"
    assert convert.resolve_format("brf") == "braille"
    with pytest.raises(ValueError):
        convert.resolve_format("mp3")


def test_convert_file_text(tmp_path, settings):
    src = _write(tmp_path / "a.txt", "Hello world.\nSecond line.")
    out = tmp_path / "out"
    res = convert.convert_file(src, out, "text", settings)
    assert res.ok
    dest = Path(res.output)
    assert dest.exists() and dest.suffix == ".txt"
    assert "Hello world." in dest.read_text(encoding="utf-8")


def test_convert_file_braille(tmp_path, settings):
    src = _write(tmp_path / "b.txt", "Braille test.")
    out = tmp_path / "out"
    res = convert.convert_file(src, out, "braille", settings)
    assert res.ok and Path(res.output).suffix == ".brf"


def test_collision_disambiguates_never_overwrites(tmp_path, settings):
    src = _write(tmp_path / "a.txt", "content here")
    out = tmp_path / "out"
    r1 = convert.convert_file(src, out, "markdown", settings)
    r2 = convert.convert_file(src, out, "markdown", settings)
    assert r1.ok and r2.ok
    assert r1.output != r2.output  # the second run did not overwrite the first
    assert Path(r1.output).exists() and Path(r2.output).exists()


def test_batch_failure_isolation(tmp_path, settings, monkeypatch):
    """Two good files + one broken file: the batch finishes all three."""
    _write(tmp_path / "good1.txt", "First document.")
    _write(tmp_path / "good2.txt", "Second document.")
    _write(tmp_path / "broken.txt", "irrelevant content")
    out = tmp_path / "out"

    real_load = convert.load_document

    def fake_load(path, s):
        # Simulate a corrupt / password-protected / unsupported file.
        if Path(path).name == "broken.txt":
            raise RuntimeError("simulated corrupt file")
        return real_load(path, s)

    monkeypatch.setattr(convert, "load_document", fake_load)

    summary = convert.run_batch([tmp_path], out, "markdown", settings)

    assert summary.total == 3
    assert len(summary.succeeded) == 2  # the broken file did not abort the run
    assert len(summary.failed) == 1
    failure = summary.failed[0]
    assert Path(failure.source).name == "broken.txt"
    assert "simulated corrupt file" in failure.error  # the real reason, not "failed"

    # Outputs for the good files exist; none for the broken one.
    assert (out / "good1.md").exists() and (out / "good2.md").exists()

    # The summary is persisted alongside the outputs and is retrievable.
    assert summary.log_path and Path(summary.log_path).exists()
    log_text = Path(summary.log_path).read_text(encoding="utf-8")
    assert "broken.txt" in log_text
    assert "good1.txt" in log_text
    assert "FAIL" in log_text and "OK" in log_text


def test_batch_stop_event_cancels(tmp_path, settings):
    import threading

    for i in range(5):
        _write(tmp_path / f"f{i}.txt", f"doc {i}")
    out = tmp_path / "out"
    stop = threading.Event()
    stop.set()  # already stopped → nothing should be processed
    summary = convert.run_batch([tmp_path], out, "text", settings, stop=stop)
    assert summary.total == 0


def test_braille_letter_sign_after_number():
    """Grade 1: an a-j letter after digits needs the letter sign (dots 5-6) —
    without it '3a' embosses as '31' (silent content corruption)."""
    from star.braille import _BRAILLE_ASCII, _BRL_LETTER_SIGN, _text_to_braille_grade1

    sign = _BRAILLE_ASCII[_BRL_LETTER_SIGN]
    out = _text_to_braille_grade1("3a")
    assert sign in out, "letter sign missing after a number"
    # k-z (outside the digit cells) and letters after a space don't need it.
    assert sign not in _text_to_braille_grade1("3 a")
    # And accented Latin letters fold to their base instead of vanishing.
    cafe = _text_to_braille_grade1("café")
    plain = _text_to_braille_grade1("cafe")
    assert cafe == plain, "accented letter dropped from braille output"
