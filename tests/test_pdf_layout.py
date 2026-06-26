"""Unit tests for PDF reading-order reconstruction (star.documents).

These exercise the pure geometry helpers with synthetic boxes — no real PDF or
pdfminer required.  pdfminer coordinates: origin bottom-left, y grows upward,
so y1 is a box's TOP edge and a higher y1 means higher on the page.
"""
from star.documents import (
    _PdfBox,
    _pdf_detect_columns,
    _pdf_is_running,
    _pdf_norm_margin,
    _pdf_order_boxes,
    _pdf_running_heads_feet,
)

W, H = 600.0, 800.0  # a US-letter-ish page in points

# Column x-extents with a clear gutter at ~280–320 (≈7% of width > 4% threshold).
LX0, LX1 = 50.0, 280.0   # left column
RX0, RX1 = 320.0, 550.0  # right column


def _b(text, x0, y0, x1, y1):
    return _PdfBox(text, x0, y0, x1, y1)


def _texts(boxes):
    return [b.text for b in boxes]


def test_single_column_reads_top_to_bottom():
    boxes = [
        _b("third", 50, 400, 550, 430),
        _b("first", 50, 700, 550, 730),
        _b("second", 50, 550, 550, 580),
    ]
    assert _texts(_pdf_order_boxes(boxes, W)) == ["first", "second", "third"]


def test_two_columns_read_left_then_right():
    boxes = [
        _b("R1", RX0, 680, RX1, 710),
        _b("L2", LX0, 560, LX1, 590),
        _b("R2", RX0, 560, RX1, 590),
        _b("L1", LX0, 680, LX1, 710),
    ]
    # left column top→bottom, THEN right column top→bottom
    assert _texts(_pdf_order_boxes(boxes, W)) == ["L1", "L2", "R1", "R2"]


def test_full_width_title_precedes_columns():
    boxes = [
        _b("R1", RX0, 600, RX1, 630),
        _b("L1", LX0, 600, LX1, 630),
        _b("TITLE", 50, 740, 550, 770),  # spans both columns → divider
    ]
    assert _texts(_pdf_order_boxes(boxes, W)) == ["TITLE", "L1", "R1"]


def test_midpage_full_width_divider_bands_columns():
    boxes = [
        _b("TITLE", 50, 740, 550, 770),     # full-width, top
        _b("L1", LX0, 680, LX1, 710),       # band 1 left
        _b("R1", RX0, 680, RX1, 710),       # band 1 right
        _b("FIG", 50, 480, 550, 540),       # full-width figure, mid
        _b("L2", LX0, 420, LX1, 450),       # band 2 left
        _b("R2", RX0, 420, RX1, 450),       # band 2 right
    ]
    assert _texts(_pdf_order_boxes(boxes, W)) == [
        "TITLE", "L1", "R1", "FIG", "L2", "R2"
    ]


def test_detect_columns_single_vs_two():
    one = [_b("x", 50, 600, 550, 630), _b("y", 50, 500, 550, 530)]
    assert len(_pdf_detect_columns(one, W)) == 1

    two = [_b("L", LX0, 600, LX1, 630), _b("R", RX0, 600, RX1, 630)]
    assert len(_pdf_detect_columns(two, W)) == 2


def test_norm_margin_collapses_digits_and_space():
    assert _pdf_norm_margin("Page 3") == _pdf_norm_margin("Page 4") == "page #"
    assert _pdf_norm_margin("  Journal   of  X ") == "journal of x"


def test_running_header_detected_and_stripped():
    pages = []
    for n in range(1, 5):  # 4 pages
        pages.append([
            _b("Journal of Examples", 50, 778, 300, 792),  # top margin, recurring
            _b(str(n), 290, 6, 310, 20),                   # bottom margin page no.
            _b("body text here", LX0, 400, LX1, 430),      # body
        ])
    repeating = _pdf_running_heads_feet(pages, H)
    assert "journal of examples" in repeating

    head = pages[0][0]
    pageno = pages[2][1]
    body = pages[0][2]
    assert _pdf_is_running(head, H, repeating) is True
    assert _pdf_is_running(pageno, H, repeating) is True   # matches page-number regex
    assert _pdf_is_running(body, H, repeating) is False    # not in a margin


def test_page_number_stripped_without_recurrence():
    # A bare page number in the margin is stripped even with an empty repeat set.
    pageno = _b("iv", 290, 6, 310, 20)
    assert _pdf_is_running(pageno, H, set()) is True


def test_empty_and_single_box_are_safe():
    assert _pdf_order_boxes([], W) == []
    one = [_b("only", 50, 600, 550, 630)]
    assert _texts(_pdf_order_boxes(one, W)) == ["only"]
