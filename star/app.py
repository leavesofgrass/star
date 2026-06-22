"""Command-line entry point and argument handling."""
from ._runtime import *  # noqa: F401,F403
from .documents import load_document
from .gui import _run_qt_gui
from .settings import Settings
from .tts import TTSManager
from .tui import THEME_NAMES, THEMES, StarApp


# =============================================================================
# Command-line interface and entry point
# =============================================================================


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
        "file", nargs="?", default="", help="Document to open (file path or URL)"
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
        "--theme", default="", help=f"Color theme: {', '.join(THEME_NAMES)}"
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

    if args.list_themes:
        for name in THEME_NAMES:
            print(name)
        return

    if args.theme and args.theme in THEMES:
        settings["theme"] = args.theme
    if args.rate > 0:
        settings["tts_rate"] = args.rate
    if args.backend:
        settings["tts_backend"] = args.backend

    if args.list_voices:
        mgr = TTSManager(settings)
        voices = mgr.list_voices()
        if voices:
            for v in voices:
                print(f"{v.get('id', '?')}\t{v.get('name', '?')}\t{v.get('lang', '?')}")
        else:
            print("No voices available or TTS not installed.")
        return

    if args.plain and args.file:
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
    if args.gui:
        _run_qt_gui(settings, args.file)  # errors internally if _QT is None
        return

    if not args.tui and _QT:
        _run_qt_gui(settings, args.file)
        return

    os.environ.setdefault("ESCDELAY", "25")

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
