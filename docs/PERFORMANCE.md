# ⚡ Performance & large documents

Notes on `star`'s runtime hot paths, how they were measured, and the
optimizations applied for large documents. Numbers below were captured on the
project's development machine (Windows 11, CPython 3.11, PyQt6) with
`star` at v0.1.19; treat them as relative, not absolute — the *shape* of the
scaling is the point.

- [Startup import cost](#startup-import-cost)
- [Word-map construction](#word-map-construction)
- [Precompiled regexes](#precompiled-regexes)
- [How to reproduce](#how-to-reproduce)

---

## Startup import cost

`import star` pulls in `star._runtime`, which wires the vendored native tools,
detects optional dependencies (cheaply, via `importlib.util.find_spec` — the
heavy packages such as PyMuPDF, Whisper/PyTorch, and Coqui are **not** imported
at startup), and imports the Qt bindings when present.

Measured with `python -X importtime -c "import star"` and a wall-clock harness:

| Metric | Value |
|---|---|
| `import star` (wall clock, warm FS cache) | **~315 ms** |
| Cumulative import time (`-X importtime`, `star` row) | ~335 ms |

Top self-time contributors (from `-X importtime`):

| Module | Self time |
|---|---|
| `star._runtime` | ~64 ms |
| `PyQt6.QtCore` | ~13 ms |
| `_hashlib` | ~9 ms |
| `PyQt6.QtGui` | ~7 ms |
| `pdfminer` (cumulative ~26 ms) | ~7 ms |
| `PyQt6.QtWidgets` | ~6 ms |

The dominant cost is Qt plus the stdlib surface `_runtime` imports; the lazy
optional-dependency detection keeps the multi-second ML/document stacks off the
startup path entirely (importing them is deferred to the first `_load_*` call
that actually needs the feature). There is no per-call regex compilation at
import time beyond a handful of constant module-level patterns.

## Word-map construction

`_build_word_map(plain_text, rendered_lines)` in
[`star/documents/model.py`](../star/documents/model.py) links every word in the
TTS plain-text to its position in the wrapped display (line + column), so the
reading highlight can follow playback. It runs once per document render (on a
background thread), and it is the single largest CPU cost when opening a large
document.

### The problem

The previous implementation, for each of *n* word tokens, scanned the display
line-by-line with `str.find`, **re-lowercasing each candidate line on every
token**. When a token was not found ahead of the rolling cursor (common in
structured documents that re-narrate table column headers in each row), it fell
through to an *extended* scan to end-of-document and then a *backward* scan over
the **entire** document — a full re-scan per unmatched token. That is O(n²) on
exactly the documents where it hurts most.

### The fix

The rewrite keeps the algorithm's output **byte-for-byte identical** but makes
it effectively O(n):

- Each display line is lower-cased **once** and joined into a single `blob`
  (`"\n".join(lowered)`).
- The forward match is a single `blob.find(word_lower, cursor)` — one C-level
  call instead of a per-line Python loop. A word token never contains a newline,
  so a `blob` match always lies within one line; the first match at or after the
  rolling cursor is exactly the first line-scan match. The absolute offset is
  mapped back to `(line, col)` via a precomputed line-start table and `bisect`.
- The "does this word exist anywhere?" backward fallback is a single
  `word_lower in blob` (O(len(word))) rather than a whole-document re-scan.

Output identity was verified against the previous implementation on synthetic
100k-word inputs (well-ordered, lightly structured, and header-heavy) — all
positions match exactly, in addition to `tests/test_documents.py`.

### Measured results

Three synthetic corpora, `orig` = previous implementation, `new` = current:

**Well-ordered** (normal prose, every word found immediately ahead — already
near-linear before, so this is a small constant-factor win from dropping the
per-token `.lower()`):

| words | orig | new | speedup |
|---:|---:|---:|---:|
| 2,000 | 2.7 ms | 2.2 ms | 1.2× |
| 20,000 | 29 ms | 27 ms | 1.1× |
| 100,000 | 155 ms | 137 ms | 1.1× |

**Structured** (≈12% of words re-narrate a header that only appears earlier in
the display — triggers the old backward scan):

| words | orig | new | speedup |
|---:|---:|---:|---:|
| 2,000 | 4.5 ms | 2.6 ms | 1.7× |
| 20,000 | 76 ms | 28 ms | 2.8× |
| 100,000 | 1,167 ms | 216 ms | **5.4×** |

**Structured-heavy** (a table-like document that re-narrates its column header
on every row — the worst case for the old whole-document re-scan):

| words | orig | new | speedup |
|---:|---:|---:|---:|
| 4,800 | 30 ms | 10 ms | 2.9× |
| 19,200 | 290 ms | 43 ms | 6.8× |
| 76,800 | 4,366 ms | 364 ms | **12.0×** |

The key result is the **scaling**, not any single row: the old implementation is
quadratic (each 4× in document size costs ≈16× more time), while the new one is
linear (≈4× time for 4× size). On the structured-heavy corpus the gap is 12× at
77k words and keeps widening — a ~4.4 s stall to open the document collapses to
under 0.4 s, and it would exceed ~20× past ~150k words. This is the difference
between a large accessible textbook opening instantly versus visibly hanging.

## Precompiled regexes

Several constant regexes in the render/markup hot paths were compiled inline on
every call — in `render_markdown`'s per-source-line loop, the Python/R code
lexers, and the per-line markup converters (Org, RST, MediaWiki, AsciiDoc,
Textile, Creole). They are now compiled **once at module import** in
[`star/render.py`](../star/render.py) and
[`star/markup.py`](../star/markup.py), removing the repeated pattern lookup from
the loops. The single-pass `_latex_to_md` applies each of its patterns once per
document, so those are intentionally left inline for readability.

Output was verified byte-for-byte identical against the pre-change functions for
every converter and for `render_markdown` at multiple wrap widths.

## How to reproduce

```sh
# Startup import cost (summarize the top self-time rows):
python -X importtime -c "import star" 2> importtime.txt

# Word-map timeit harness (from a checkout, using the venv interpreter):
python - <<'PY'
import random, timeit
from star.documents.model import _build_word_map

def make_doc(n, width=78, seed=1234):
    rnd = random.Random(seed)
    bank = ("the quick brown fox jumps over a lazy dog and then the cat sat "
            "on mat while data flows through model of words that repeat").split()
    words = [rnd.choice(bank) for _ in range(n)]
    plain = " ".join(words)
    lines, cur, col = [], [], 0
    for w in words:
        add = (1 if cur else 0) + len(w)
        if col + add > width and cur:
            lines.append(" ".join(cur)); cur, col = [w], len(w)
        else:
            cur.append(w); col += add
    if cur:
        lines.append(" ".join(cur))
    return plain, lines

pt, lines = make_doc(100_000)
t = timeit.timeit(lambda: _build_word_map(pt, lines), number=3) / 3
print(f"100k-word word map: {t*1000:.0f} ms")
PY
```
