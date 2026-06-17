#!/usr/bin/env python3
"""Split the monolithic ``star.py`` into the ``star/`` package.

Moves exact source by top-level AST node (so nothing is re-typed) into logical
modules, then computes the cross-module imports automatically from a
name->module map plus free-name analysis.  Shared foundational state (stdlib
imports, vendored-tool wiring, optional-dependency flags, paths) goes into
``star/_runtime.py`` and is re-exported via ``from ._runtime import *``.

Run from the project root:  python tools/split_star.py
"""

from __future__ import annotations

import ast
import builtins
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "star.py"
PKG = ROOT / "star"

# ---------------------------------------------------------------------------
# Top-level symbol -> module.  Bare module-level constants/comments that are
# not in this map are attached to the module of the *following* mapped node.
# ---------------------------------------------------------------------------
SYMBOL_MODULE = {
    # _runtime: foundational (most of the prelude lands here via the gap rule)
    "_vendor_dir": "_runtime",
    "_find_bundled_dectalk": "_runtime",
    "_default_sans_font": "_runtime",
    # settings
    "Settings": "settings",
    # tts engines + manager
    "TTSBackend": "tts",
    "FestivalBackend": "tts",
    "CoquiBackend": "tts",
    "_piper_voice_dirs": "tts",
    "PiperBackend": "tts",
    "_apply_wav_adjustments": "tts",
    "_convert_audio_format": "tts",
    "_wav_duration_seconds": "tts",
    "_fmt_subtitle_time": "tts",
    "_build_subtitle_cues": "tts",
    "_format_subtitles": "tts",
    "_generate_subtitles": "tts",
    "SilentBackend": "tts",
    "Pyttsx3Backend": "tts",
    "ESpeakBackend": "tts",
    "DECtalkDLLBackend": "tts",
    "DECtalkBackend": "tts",
    "AppleSayBackend": "tts",
    "_SCReader": "tts",
    "TTSManager": "tts",
    # tts text preprocessing
    "_strip_markdown_for_tts": "ttstext",
    "_text_to_ssml": "ttstext",
    "_text_to_dectalk": "ttstext",
    "_expand_abbreviations": "ttstext",
    "_apply_pronunciations": "ttstext",
    "_int_to_words": "ttstext",
    "_year_to_words": "ttstext",
    "_ordinal_to_words": "ttstext",
    "_decimal_digits_to_words": "ttstext",
    "_normalize_numbers": "ttstext",
    "_tables_to_narration": "ttstext",
    "_preprocess_tts_text": "ttstext",
    "_normalize_math_inline": "ttstext",
    # markup text converters
    "_orgmode_to_md": "markup",
    "_pandoc_convert": "markup",
    "_rst_to_md": "markup",
    "_mediawiki_to_md": "markup",
    "_asciidoc_to_md": "markup",
    "_textile_to_md": "markup",
    "_creole_to_md": "markup",
    "_latex_to_md": "markup",
    # documents (model + loaders)
    "WordPos": "documents",
    "Document": "documents",
    "_detect_format": "documents",
    "_build_word_map": "documents",
    "_load_plain_text": "documents",
    "_load_markdown": "documents",
    "_HTML2MD": "documents",
    "_load_html": "documents",
    "_load_html_str": "documents",
    "_load_epub": "documents",
    "_load_dtbook": "documents",
    "_load_daisy_zip": "documents",
    "_load_csv_tsv": "documents",
    "_load_xlsx": "documents",
    "_load_docx": "documents",
    "_load_doc": "documents",
    "_load_pdf": "documents",
    "_load_image_ocr": "documents",
    "_load_r_code": "documents",
    "_load_rmarkdown": "documents",
    "_load_notebook": "documents",
    "_load_orgmode": "documents",
    "_load_rst": "documents",
    "_load_mediawiki": "documents",
    "_load_asciidoc": "documents",
    "_load_textile": "documents",
    "_load_creole": "documents",
    "_load_latex": "documents",
    "_load_url": "documents",
    "_load_via_pandoc": "documents",
    "load_document": "documents",
    "_load_pptx": "documents",
    "_load_odt_v2": "documents",
    "_load_odt_via_odfpy": "documents",
    "_odt_table_to_md": "documents",
    "_load_odt_raw_xml": "documents",
    "_process_footnotes": "documents",
    "_epub_extract_chapters": "documents",
    # rendering
    "_parse_inline": "render",
    "_wrap_segs": "render",
    "render_markdown": "render",
    "_lex_python_line": "render",
    "_lex_r_line": "render",
    "lines_to_plain": "render",
    # search / line editor
    "SearchEngine": "search",
    "LineEditor": "search",
    # braille
    "_text_to_braille_grade1": "braille",
    "_format_brf": "braille",
    "_export_braille": "braille",
    # annotations
    "_format_annotations": "annotations",
    "_annotation_matches": "annotations",
    "_parse_tags": "annotations",
    # citations
    "_citation_label": "citations",
    "_parse_bibtex": "citations",
    "_parse_ris": "citations",
    "_parse_csl_json": "citations",
    "_import_citations": "citations",
    "_format_citations": "citations",
    "_fetch_citation_by_doi": "citations",
    # transcription
    "_fmt_timestamp": "transcribe",
    "_transcribe_audio": "transcribe",
    "_record_audio_to_wav": "transcribe",
    # cache
    "_cache_key": "cache",
    "_cache_save": "cache",
    "_cache_load": "cache",
    # reading stats / library / profiles
    "_settings_fingerprint": "stats",
    "_fmt_duration": "stats",
    "ReadingStats": "stats",
    "_record_library": "stats",
    "_library_entries": "stats",
    "_format_reading_stats": "stats",
    "_save_profile": "stats",
    "_apply_profile_values": "stats",
    "_delete_profile": "stats",
    # themes
    "_palette_to_css": "themes",
    "_parse_css_palette": "themes",
    "_load_css_themes": "themes",
    "_seed_default_css_themes": "themes",
    # terminal UI
    "_t": "tui",
    "_setup_colors": "tui",
    "_addstr": "tui",
    "_fillrow": "tui",
    "_shortcuts_text": "tui",
    "StarApp": "tui",
    # qt GUI
    "_run_qt_gui": "gui",
    # entry point
    "main": "app",
    "_run_keytest": "app",
}

# Specific bare module-level constants to force into a module (overrides the
# "attach to following node" gap rule).
NAME_OVERRIDE = {
    "_HELP_TEXT": "tui",
    # Shared by both the TTS chunker and the TUI; keep it in the foundational
    # module so it is re-exported via ``import *`` and creates no tts<->tui
    # import cycle.
    "_SENTENCE_SPLIT_RE": "_runtime",
    # Pin these to tui so relocating the regex above does not drag them out of
    # tui via the "attach to the following mapped node" gap rule.
    "_HEADING_ROLES": "tui",
    "_TABLE_ROLES": "tui",
}

MODULE_ORDER = [
    "_runtime",
    "settings",
    "ttstext",
    "markup",
    "documents",
    "render",
    "search",
    "braille",
    "annotations",
    "citations",
    "transcribe",
    "cache",
    "stats",
    "themes",
    "tts",
    "tui",
    "gui",
    "app",
]

MODULE_DOC = {
    "_runtime": "Foundational shared state: stdlib imports, vendored-tool wiring,\noptional-dependency detection, app metadata and config paths.  Re-exported\nwholesale via ``from ._runtime import *`` by the rest of the package.",
    "settings": "Persistent settings store and the default settings table.",
    "ttstext": "Text preprocessing for TTS: SSML/DECtalk markup, abbreviation and\npronunciation expansion, number/date normalization, table narration.",
    "markup": "Lightweight markup -> Markdown converters (RST, Org, MediaWiki,\nAsciiDoc, Textile, Creole, LaTeX) and the Pandoc bridge.",
    "documents": "Document model and the multi-format loaders (PDF, EPUB, DOCX, PPTX,\nODT, HTML, images/OCR, notebooks, code, URLs, ...).",
    "render": "Markdown -> styled terminal lines rendering and code lexers.",
    "search": "In-document search engine and the curses line editor.",
    "braille": "Built-in Grade 1 BRF translation and Braille export.",
    "annotations": "Annotation formatting, tag parsing, and search matching.",
    "citations": "Citation parsing/formatting (BibTeX, RIS, CSL-JSON) and DOI lookup.",
    "transcribe": "Whisper-based audio transcription and microphone capture.",
    "cache": "On-disk document cache.",
    "stats": "Reading statistics, library/bookshelf, and profile presets.",
    "themes": "CSS theme loading, palette parsing, and default theme seeding.",
    "tts": "Text-to-speech backends and the TTS manager.",
    "tui": "The curses terminal user interface (StarApp).",
    "gui": "The Qt GUI (StarWindow / help window), built lazily in _run_qt_gui.",
    "app": "Command-line entry point and argument handling.",
}

BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}


def node_span(node):
    start = node.lineno
    for dec in getattr(node, "decorator_list", []) or []:
        start = min(start, dec.lineno)
    return start, node.end_lineno


def collect_bound(node, names):
    """Names bound at module level by *node* (recurse into module-level
    compound statements but NOT into function/class bodies)."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.add(node.name)
        return
    if isinstance(node, ast.Assign):
        for t in node.targets:
            for sub in ast.walk(t):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
        return
    if isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            names.add(node.target.id)
        return
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name.split(".")[0]
            names.add(bound)
        return
    if isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
        for field in ("body", "orelse", "finalbody"):
            for child in getattr(node, field, []) or []:
                collect_bound(child, names)
        for handler in getattr(node, "handlers", []) or []:
            for child in handler.body:
                collect_bound(child, names)
        return


def loaded_names(node):
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
            out.add(sub.id)
    return out


def is_main_guard(node):
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
    )


def main():
    source = SRC.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)

    body = [n for n in tree.body if not is_main_guard(n)]

    # Assign a module to every top-level node.
    entries = []  # (start, end, node, module)
    for node in body:
        start, end = node_span(node)
        mod = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            mod = SYMBOL_MODULE.get(node.name)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            mod = NAME_OVERRIDE.get(node.targets[0].id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            mod = NAME_OVERRIDE.get(node.target.id)
        entries.append([start, end, node, mod])

    # Resolve None modules: attach to the following mapped node (else preceding).
    n = len(entries)
    for i in range(n):
        if entries[i][3] is None:
            mod = None
            for j in range(i + 1, n):
                if entries[j][3] is not None:
                    mod = entries[j][3]
                    break
            if mod is None:
                for j in range(i - 1, -1, -1):
                    if entries[j][3] is not None:
                        mod = entries[j][3]
                        break
            entries[i][3] = mod or "_runtime"

    # Map every source line (1-based) to a module.  Node spans win; gap lines
    # attach to the next node's module (trailing gap -> last node's module).
    line_mod = [None] * (len(lines) + 2)
    for start, end, _node, mod in entries:
        for ln in range(start, end + 1):
            line_mod[ln] = mod
    # gap fill forward
    last = entries[-1][3] if entries else "_runtime"
    nxt = last
    for ln in range(len(lines), 0, -1):
        if line_mod[ln] is None:
            line_mod[ln] = nxt
        else:
            nxt = line_mod[ln]

    # Build per-module source (preserve original order) and node lists.
    mod_lines = {m: [] for m in MODULE_ORDER}
    for idx, raw in enumerate(lines, start=1):
        m = line_mod[idx] or "_runtime"
        mod_lines.setdefault(m, []).append(raw)
    mod_nodes = {m: [] for m in MODULE_ORDER}
    for _s, _e, node, mod in entries:
        mod_nodes.setdefault(mod, []).append(node)

    # provides / loaded per module
    provides = {}
    loaded = {}
    for m, nodes in mod_nodes.items():
        pset = set()
        lset = set()
        for nd in nodes:
            collect_bound(nd, pset)
            lset |= loaded_names(nd)
        provides[m] = pset
        loaded[m] = lset

    name_owner = {}
    for m, names in provides.items():
        for nm in names:
            name_owner.setdefault(nm, m)

    runtime_names = provides["_runtime"]

    # Compute cross-module imports + edges.
    edges = []
    imports = {}
    for m in MODULE_ORDER:
        if m == "_runtime":
            continue
        need = {}
        for nm in sorted(loaded[m]):
            if nm in provides[m] or nm in runtime_names or nm in BUILTINS:
                continue
            owner = name_owner.get(nm)
            if owner and owner != m and owner != "_runtime":
                need.setdefault(owner, []).append(nm)
        imports[m] = need
        for owner in need:
            edges.append((m, owner))

    # Write the package.
    PKG.mkdir(exist_ok=True)
    for m in MODULE_ORDER:
        text = "".join(mod_lines.get(m, []))
        header_parts = []
        doc = MODULE_DOC.get(m, "")
        if m == "_runtime":
            # Keep the original shebang/module docstring at the very top; just
            # append a dynamic __all__ so `import *` re-exports everything bound.
            out = text.rstrip("\n") + (
                "\n\n# Re-export every module-level name (so `from ._runtime "
                "import *`\n# rehydrates the shared namespace the rest of the "
                "package was written\n# against).  Optional names are only "
                "present when their import succeeded.  The metadata dunders "
                "are\n# re-exported explicitly because `import *` skips "
                "underscored names\n# unless they are named in __all__.\n"
                '__all__ = [n for n in dict(globals()) if not n.startswith("__")]\n'
                '__all__ += ["__version__", "__author__", "__copyright__", "__license__"]\n'
            )
        else:
            header_parts.append(f'"""{doc}"""')
            header_parts.append("from ._runtime import *  # noqa: F401,F403")
            for owner in sorted(imports[m]):
                names = ", ".join(sorted(imports[m][owner]))
                header_parts.append(f"from .{owner} import {names}")
            out = "\n".join(header_parts) + "\n\n\n" + text.lstrip("\n")
        (PKG / f"{m}.py").write_text(out, encoding="utf-8")

    # __init__.py and __main__.py
    (PKG / "__init__.py").write_text(
        '"""star — Speaking Terminal Access Reader (package).\n\n'
        "Refactored from the original single-file ``star.py`` into logical\n"
        "submodules.  Public entry point: ``star.app.main`` (also ``python -m star``\n"
        'and the ``star`` console script).\n"""\n'
        "from ._runtime import __author__, __copyright__, __license__, __version__\n"
        "from .app import main\n\n"
        '__all__ = ["main", "__version__", "__author__", "__copyright__", "__license__"]\n',
        encoding="utf-8",
    )
    (PKG / "__main__.py").write_text(
        '"""``python -m star`` entry point."""\n'
        "from .app import main\n\n"
        'if __name__ == "__main__":\n'
        "    main()\n",
        encoding="utf-8",
    )
    # PyInstaller / dev entry script.
    (ROOT / "run_star.py").write_text(
        "#!/usr/bin/env python3\n"
        '"""Entry script for PyInstaller and `python run_star.py`."""\n'
        "from star.app import main\n\n"
        'if __name__ == "__main__":\n'
        "    main()\n",
        encoding="utf-8",
    )

    # Report.
    print("Wrote package to", PKG)
    for m in MODULE_ORDER:
        ln = len(mod_lines.get(m, []))
        imp = imports.get(m, {})
        impstr = ", ".join(f"{k}:{len(v)}" for k, v in sorted(imp.items()))
        print(f"  {m:12s} {ln:6d} lines   imports[{impstr}]")
    # Cycle check (simple DFS).
    graph = {}
    for a, b in edges:
        graph.setdefault(a, set()).add(b)
    cycles = []
    WHITE, GREY, BLACK = 0, 1, 2
    color = {m: WHITE for m in MODULE_ORDER}
    stack = []

    def dfs(u):
        color[u] = GREY
        stack.append(u)
        for v in graph.get(u, ()):  # noqa
            if color[v] == GREY:
                i = stack.index(v)
                cycles.append(stack[i:] + [v])
            elif color[v] == WHITE:
                dfs(v)
        stack.pop()
        color[u] = BLACK

    for m in MODULE_ORDER:
        if color[m] == WHITE:
            dfs(m)
    if cycles:
        print("\nWARNING: import cycles detected:")
        for c in cycles:
            print("   ", " -> ".join(c))
    else:
        print("\nNo import cycles detected.")


if __name__ == "__main__":
    main()
