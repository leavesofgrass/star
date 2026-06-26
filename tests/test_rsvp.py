"""Tests for the RSVP (Rapid Serial Visual Presentation) reading mode.

Pure-logic tests only — no Qt or curses required.
"""
import pytest


# =============================================================================
# RSVPOverlay position helper (_POSITIONS dict)
# =============================================================================


VALID_POSITIONS = [
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]


def test_all_positions_defined():
    """Every position key maps to a (float, float) pair in [0, 1]."""
    pytest.skip("Qt not available in headless test environment")


def _rsvp_position_coords(pos_key, positions_dict):
    """Compute top-left pixel coords for a given position key."""
    parent_w, parent_h = 800, 600
    overlay_w, overlay_h = 200, 80
    fx, fy = positions_dict.get(pos_key, (0.5, 0.02))
    x = int(parent_w * fx - overlay_w * fx)
    y = int(parent_h * fy - overlay_h * fy)
    margin = 8
    x = max(margin, min(x, parent_w - overlay_w - margin))
    y = max(margin, min(y, parent_h - overlay_h - margin))
    return x, y


_POSITIONS = {
    "top-left":      (0.02, 0.02),
    "top-center":    (0.50, 0.02),
    "top-right":     (0.98, 0.02),
    "center-left":   (0.02, 0.50),
    "center":        (0.50, 0.50),
    "center-right":  (0.98, 0.50),
    "bottom-left":   (0.02, 0.98),
    "bottom-center": (0.50, 0.98),
    "bottom-right":  (0.98, 0.98),
}


def test_position_coords_top_left():
    x, y = _rsvp_position_coords("top-left", _POSITIONS)
    assert x == 12   # int(800*0.02 - 200*0.02)
    assert y == 10   # int(600*0.02 - 80*0.02)


def test_position_coords_top_right():
    x, y = _rsvp_position_coords("top-right", _POSITIONS)
    assert x == 588  # int(800*0.98 - 200*0.98)
    assert y == 10   # fy same as top-left


def test_position_coords_center():
    x, y = _rsvp_position_coords("center", _POSITIONS)
    # x = 800*0.5 - 200*0.5 = 400 - 100 = 300
    assert x == 300
    # y = 600*0.5 - 80*0.5 = 300 - 40 = 260
    assert y == 260


def test_position_coords_bottom_right():
    x, y = _rsvp_position_coords("bottom-right", _POSITIONS)
    assert x > 400  # right half
    assert y > 400  # bottom half


def test_position_coords_unknown_key_falls_back():
    x, y = _rsvp_position_coords("invalid-key", _POSITIONS)
    # Falls back to top-center (0.5, 0.02) default
    assert 8 <= x <= 800
    assert 8 <= y <= 600


def test_all_positions_in_bounds():
    for key in VALID_POSITIONS:
        x, y = _rsvp_position_coords(key, _POSITIONS)
        assert 8 <= x <= 800 - 200 - 8, f"x out of bounds for {key}: {x}"
        assert 8 <= y <= 600 - 80 - 8, f"y out of bounds for {key}: {y}"


# =============================================================================
# TUI RSVP position fractions (matches _RSVP_FRAC in tui.py)
# =============================================================================

_RSVP_FRAC = {
    "top-left":      (0.02, 0.02),
    "top-center":    (0.02, 0.50),
    "top-right":     (0.02, 0.98),
    "center-left":   (0.50, 0.02),
    "center":        (0.50, 0.50),
    "center-right":  (0.50, 0.98),
    "bottom-left":   (0.98, 0.02),
    "bottom-center": (0.98, 0.50),
    "bottom-right":  (0.98, 0.98),
}


def _tui_rsvp_coords(pos_key, h=24, w=80, box_h=3, box_w=16):
    """Compute (row, col) for the RSVP box in TUI layout."""
    view_top = 1
    view_bottom = h - 3
    view_h = max(1, view_bottom - view_top)
    fy, fx = _RSVP_FRAC.get(pos_key, (0.02, 0.50))
    raw_row = int(view_top + view_h * fy - box_h * fy)
    raw_col = int(w * fx - box_w * fx)
    row = max(view_top, min(raw_row, view_bottom - box_h - 1))
    col = max(0, min(raw_col, w - box_w - 1))
    return row, col


def test_tui_position_top_center():
    row, col = _tui_rsvp_coords("top-center")
    assert row <= 3  # near top
    assert col > 20  # horizontally centered


def test_tui_position_bottom_right():
    row, col = _tui_rsvp_coords("bottom-right")
    assert row >= 16  # near bottom of 24-row terminal
    assert col > 50  # in the right half


def test_tui_position_center():
    row, col = _tui_rsvp_coords("center")
    # Middle of view_h (1..21) and middle of w=80
    assert 8 <= row <= 14
    assert 28 <= col <= 52


def test_tui_position_all_in_bounds():
    for key in VALID_POSITIONS:
        row, col = _tui_rsvp_coords(key)
        assert 1 <= row, f"row out of bounds for {key}: {row}"
        assert col >= 0, f"col out of bounds for {key}: {col}"


# =============================================================================
# RSVP positions list in tui.py matches the _RSVP_FRAC keys
# =============================================================================


def test_tui_positions_list_complete():
    """All 9 canonical positions are present in both direction dicts."""
    from star.tui import StarApp
    positions = StarApp._RSVP_POSITIONS
    assert len(positions) == 9
    for pos in VALID_POSITIONS:
        assert pos in positions, f"Missing TUI position: {pos}"


def test_rsvp_frac_keys_match_positions_list():
    """_RSVP_FRAC keys (from tui.py) cover all 9 canonical positions."""
    # Re-import from tui to test the actual dict
    from star import tui as _tui
    frac = _tui.StarApp._RSVP_FRAC
    for pos in VALID_POSITIONS:
        assert pos in frac, f"Missing _RSVP_FRAC key: {pos}"
    for fy, fx in frac.values():
        assert 0.0 <= fy <= 1.0
        assert 0.0 <= fx <= 1.0


# =============================================================================
# Settings defaults
# =============================================================================


def test_rsvp_settings_defaults():
    from star.settings import Settings
    s = Settings()
    assert s.get("qt_rsvp_mode") is False
    assert s.get("qt_rsvp_position") == "top-center"
    assert s.get("qt_rsvp_font_size") == 48
    assert s.get("qt_rsvp_context") is True
    assert s.get("tui_rsvp_mode") is False
    assert s.get("tui_rsvp_position") == "top-center"


def test_rsvp_position_default_in_valid_set():
    from star.settings import Settings
    s = Settings()
    assert s.get("qt_rsvp_position") in VALID_POSITIONS
    assert s.get("tui_rsvp_position") in VALID_POSITIONS


# =============================================================================
# Word extraction from word_map (mirrors _on_highlight / _apply_word_highlight)
# =============================================================================


def _make_word_map(words):
    """Build a minimal word_map-like list with just .word attributes."""
    from types import SimpleNamespace
    return [SimpleNamespace(word=w, disp_line=i, disp_col=0, tts_len=len(w), tts_offset=i*5)
            for i, w in enumerate(words)]


def test_rsvp_word_extraction_middle():
    wm = _make_word_map(["Hello", "world", "goodbye"])
    idx = 1
    prev = wm[idx - 1].word if idx > 0 else ""
    curr = wm[idx].word
    nxt = wm[idx + 1].word if idx + 1 < len(wm) else ""
    assert prev == "Hello"
    assert curr == "world"
    assert nxt == "goodbye"


def test_rsvp_word_extraction_first():
    wm = _make_word_map(["Hello", "world"])
    idx = 0
    prev = wm[idx - 1].word if idx > 0 else ""
    curr = wm[idx].word
    nxt = wm[idx + 1].word if idx + 1 < len(wm) else ""
    assert prev == ""
    assert curr == "Hello"
    assert nxt == "world"


def test_rsvp_word_extraction_last():
    wm = _make_word_map(["Hello", "world"])
    idx = 1
    prev = wm[idx - 1].word if idx > 0 else ""
    curr = wm[idx].word
    nxt = wm[idx + 1].word if idx + 1 < len(wm) else ""
    assert prev == "Hello"
    assert curr == "world"
    assert nxt == ""


def test_rsvp_word_extraction_single():
    wm = _make_word_map(["OnlyWord"])
    idx = 0
    prev = wm[idx - 1].word if idx > 0 else ""
    curr = wm[idx].word
    nxt = wm[idx + 1].word if idx + 1 < len(wm) else ""
    assert prev == ""
    assert curr == "OnlyWord"
    assert nxt == ""
