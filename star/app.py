"""Command-line entry point and argument handling.

Imports are branched by mode: only ``_runtime`` (cheap) and ``Settings`` load at
import time.  The heavy stacks — the Qt GUI (``.gui``), the curses TUI
(``.tui``), the document loaders (``.documents``), and the TTS manager
(``.tts``) — are imported lazily inside the branch of :func:`main` that needs
them, so ``--version`` / ``--deps`` / ``--list-themes`` stay nearly instant and a
GUI launch never pays for the TUI stack (or vice versa).
"""
from ._runtime import *  # noqa: F401,F403
from .settings import Settings


# =============================================================================
# Command-line interface and entry point
# =============================================================================


def _install_optional(spec: str) -> None:
    """Install optional features from a preset or comma-separated feature keys.

    Runs in the foreground with plain progress output (the GUI chooser is the
    interactive path). Best-effort per package — see :mod:`star.autodeps`.
    """
    from . import autodeps

    spec = (spec or "all").strip().lower()
    if spec in autodeps.PRESETS:
        keys = autodeps.preset(spec)
    else:
        keys = [k.strip() for k in spec.split(",") if k.strip()]
    unknown = [k for k in keys if k not in autodeps.FEATURES]
    if not keys or unknown:
        if unknown:
            print(f"Unknown feature(s): {', '.join(unknown)}\n")
        print("Presets:  thin  all")
        print("Features:")
        for key, (label, _detail, mb) in autodeps.FEATURE_INFO.items():
            size = f"~{mb} MB" if mb < 1000 else f"~{mb / 1000:.1f} GB"
            state = "installed" if autodeps.feature_installed(key) else size
            print(f"  {key:<12} {label}  ({state})")
        return

    autodeps.set_enabled(True)
    pkgs = [pair for k in keys for pair in autodeps.FEATURES.get(k, [])]
    todo = autodeps.missing(pkgs)
    if not todo:
        print("All selected optional features are already installed.")
        return
    print(f"Installing {len(todo)} package(s): {', '.join(p for p, _m in todo)}")
    # Foreground + force so the CLI actually waits and ignores once-per-machine markers.
    autodeps.ensure(pkgs, background=False, force=True)
    still = autodeps.missing(pkgs)
    if still:
        print(f"Done — {len(still)} package(s) could not be installed: "
              f"{', '.join(p for p, _m in still)} (offline, no pip, or build failure).")
    else:
        print("Done — all selected optional features installed.")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog=APP_NAME,
        description=f"{APP_TITLE} — keyboard-driven reading with built-in TTS.",
        epilog=(
            "Keyboard shortcuts:  Space=play/pause  Ctrl+O=open  "
            "F2=commands  F1=help  Ctrl+Q=quit"
        ),
    )
    ap.add_argument(
        "file",
        nargs="?",
        default="",
        help="Document to open (file path or URL), or a folder to open as a library",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    ap.add_argument(
        "--gui",
        action="store_true",
        help="Launch the Qt GUI (requires PyQt6 or PyQt5; now the default when Qt is available)",
    )
    ap.add_argument(
        "--tui",
        action="store_true",
        help="Force terminal UI mode even when Qt is available",
    )
    ap.add_argument(
        "--theme",
        default="",
        help="Initial color theme name (e.g. dark, light, contrast, phosphor; "
        "see --list-themes)",
    )
    ap.add_argument(
        "--rate",
        type=int,
        default=0,
        help="TTS rate in words per minute (default: 265)",
    )
    ap.add_argument(
        "--backend",
        default="",
        help="TTS backend: auto|pyttsx3|espeak|festival|coqui|dectalk|none",
    )
    ap.add_argument(
        "--plain",
        action="store_true",
        help="Extract text to stdout and exit (no TUI — ideal for piping to other tools)",
    )
    ap.add_argument(
        "--list-themes", action="store_true", help="Print available themes and exit"
    )
    ap.add_argument(
        "--list-voices", action="store_true", help="Print available TTS voices and exit"
    )
    ap.add_argument(
        "--keytest", action="store_true", help="Run the key-code inspector (diagnostic)"
    )
    ap.add_argument(
        "--deps",
        action="store_true",
        help="Print the status of every optional dependency and exit",
    )
    ap.add_argument(
        "--install-optional",
        metavar="PRESET",
        nargs="?",
        const="all",
        default=None,
        help="Install optional features and exit. PRESET is a preset (thin|all) or a "
        "comma-separated list of feature keys (e.g. ocr,dictionary); default 'all'. "
        "Run with no value or an unknown value to see the available features.",
    )
    # ── Hot-folder watching (headless batch conversion) ──────────────────
    ap.add_argument(
        "--watch",
        metavar="DIR",
        default="",
        help="Watch DIR and convert each file dropped into it (headless mode); "
        "requires --output",
    )
    ap.add_argument(
        "--output",
        metavar="DIR",
        default="",
        help="Output directory for --watch conversions",
    )
    ap.add_argument(
        "--format",
        default="",
        help="Output format for --watch (default: markdown)",
    )
    args = ap.parse_args()

    settings = Settings()

    if args.deps:
        from .diagnostics import format_dependency_report

        sys.stdout.write(format_dependency_report())
        return

    if args.install_optional is not None:
        _install_optional(args.install_optional)
        return

    if args.list_themes:
        from .tui import THEME_NAMES

        for name in THEME_NAMES:
            print(name)
        return

    if args.theme:
        from .tui import THEMES

        if args.theme in THEMES:
            settings["theme"] = args.theme
    if args.rate > 0:
        settings["tts_rate"] = args.rate
    if args.backend:
        settings["tts_backend"] = args.backend

    if args.list_voices:
        from .tts import TTSManager

        mgr = TTSManager(settings)
        voices = mgr.list_voices()
        if voices:
            for v in voices:
                print(f"{v.get('id', '?')}\t{v.get('name', '?')}\t{v.get('lang', '?')}")
        else:
            print("No voices available or TTS not installed.")
        return

    if args.plain and args.file:
        from .documents import load_document

        doc = load_document(args.file, settings)
        sys.stdout.write(doc.plain_text)
        sys.stdout.write("\n")
        return

    if args.keytest:
        _run_keytest()
        return

    if args.watch:
        _run_watch(args, settings)
        return

    # GUI is the default mode when Qt is available; use --tui to force terminal.
    # --gui keeps working as an explicit opt-in (and errors if Qt missing).
    # The .gui / .tui stacks are imported lazily so only the chosen one loads.
    if args.gui:
        from .gui import _run_qt_gui

        _run_qt_gui(settings, args.file)  # errors internally if _QT is None
        return

    if not args.tui and _QT:
        from .gui import _run_qt_gui

        _run_qt_gui(settings, args.file)
        return

    if not _CURSES:
        # The curses --tui interface is unavailable — most commonly Windows
        # without the windows-curses package.  Fall back to the Qt GUI when it
        # is available; otherwise explain how to get a working interface.
        if _QT:
            print(
                "Terminal UI unavailable (curses not installed); launching the "
                "Qt GUI instead.\n"
                "Install windows-curses to enable --tui on Windows.",
                file=sys.stderr,
            )
            from .gui import _run_qt_gui

            _run_qt_gui(settings, args.file)
            return
        print(
            "No usable interface available.\n"
            "  - The terminal UI (--tui) needs curses; on Windows: "
            "pip install windows-curses\n"
            "  - The Qt GUI needs PyQt6 or PyQt5: pip install PyQt6",
            file=sys.stderr,
        )
        sys.exit(1)

    os.environ.setdefault("ESCDELAY", "25")

    from .tui import StarApp

    def _tui(stdscr: "curses.window") -> None:
        app = StarApp(stdscr, settings, initial_path=args.file)
        app.run()

    try:
        curses.wrapper(_tui)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Surface any crash outside curses for debugging
        print(f"star crashed: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


def _run_watch(args: "argparse.Namespace", settings: Settings) -> None:
    """Run the headless hot-folder watcher (``star --watch``).

    Validates the output directory and format (reusing the batch feature's
    format validation), then blocks until interrupted.
    """
    from .convert import resolve_format, supported_formats
    from .watch import HotFolderWatcher

    if not args.output:
        print("--watch requires --output <dir>", file=sys.stderr)
        sys.exit(2)
    in_dir = Path(args.watch)
    if not in_dir.is_dir():
        print(f"--watch: not a directory: {in_dir}", file=sys.stderr)
        sys.exit(2)
    fmt = args.format or str(settings.get("watch_format", "markdown"))
    try:
        fmt = resolve_format(fmt)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        print("Supported formats: " + ", ".join(supported_formats()), file=sys.stderr)
        sys.exit(2)
    watcher = HotFolderWatcher(args.watch, args.output, fmt, settings)
    watcher.run_forever()


def _run_keytest() -> None:
    """Interactive key-code inspector — shows raw curses key values."""

    def _inner(scr: "curses.window") -> None:
        scr.keypad(True)
        scr.timeout(500)
        try:
            scr.addstr(
                0, 0, "star key tester — press any key to see its code.  q = quit."
            )
            scr.addstr(1, 0, "Try: Alt+x, Esc, F1-F12, Ctrl+letter, arrow keys …")
        except curses.error:
            pass
        row = 3
        while True:
            ch = scr.getch()
            if ch == -1:
                continue
            if ch == ord("q"):
                break
            extra = ""
            if ch == 27:
                scr.timeout(150)
                ch2 = scr.getch()
                scr.timeout(500)
                if ch2 != -1:
                    extra = f"  +  ch2={ch2} (0x{ch2:04x})"
            label = repr(chr(ch)) if 32 <= ch <= 126 else "?"
            line = f"ch={ch:6d}  0x{ch:04x}  {label}{extra}"
            try:
                scr.addstr(row, 0, line)
                scr.clrtoeol()
            except curses.error:
                pass
            row += 1
            if row > curses.LINES - 2:
                row = 3
                scr.clear()
            scr.refresh()

    curses.wrapper(_inner)


if __name__ == "__main__":
    main()
