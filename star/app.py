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


def _check_update() -> int:
    """Handle ``star --check-update``: query PyPI and print the result.

    Foreground, text-only, and lazy: imports :mod:`star.update` (which pulls in
    only urllib, no GUI/TUI/document stacks) and prints a one-line verdict.  The
    check is best-effort and offline-safe — a failed query prints a friendly "no
    update known" rather than a traceback.  Returns a process exit code (0 when
    up to date or the check could not complete, 0 when an update is available;
    the presence of an update is not an error).
    """
    from . import update as _update

    result = _update.check_for_update(current=APP_VERSION, use_cache=False)
    if result.update_available and result.latest:
        print(
            f"A new version of star is available: {result.latest} "
            f"(you have {APP_VERSION})."
        )
        print(f"Release notes and download: {result.url}")
    elif result.latest:
        print(f"star is up to date (version {APP_VERSION}).")
    else:
        print(
            "Could not check for updates (offline or PyPI unreachable). "
            f"You are running star {APP_VERSION}."
        )
    return 0


def _run_plugins(argv: "list[str]") -> int:
    """Handle ``star --plugins [list|info <group> <name>|api]``.

    Foreground, text-only, and lazy: it imports :mod:`star.plugins` (which walks
    entry-points without pulling in the GUI/TUI/document stacks) and prints a
    plain report.  Returns a process exit code.
    """
    from . import plugins as _plugins

    sub = (argv[0] if argv else "list").lower()

    if sub in ("list", "ls"):
        _print_plugin_list(_plugins)
        return 0

    if sub == "api":
        _print_plugin_api(_plugins)
        return 0

    if sub == "info":
        if len(argv) < 3:
            print("usage: star --plugins info <group> <name>", file=sys.stderr)
            print(
                "  group is one of: " + ", ".join(_plugin_group_aliases(_plugins)),
                file=sys.stderr,
            )
            return 2
        group = _resolve_plugin_group(_plugins, argv[1])
        if group is None:
            print(f"Unknown plugin group: {argv[1]!r}", file=sys.stderr)
            print(
                "  group is one of: " + ", ".join(_plugin_group_aliases(_plugins)),
                file=sys.stderr,
            )
            return 2
        info = _plugins.describe_plugin(group, argv[2])
        if info is None:
            print(
                f"No plugin named {argv[2]!r} registered in group {group!r}.",
                file=sys.stderr,
            )
            return 1
        _print_plugin_info(info)
        return 0

    print(f"Unknown --plugins subcommand: {sub!r}", file=sys.stderr)
    print("  expected one of: list, info, api", file=sys.stderr)
    return 2


def _plugin_group_aliases(_plugins) -> "list[str]":
    """Short group aliases accepted by ``--plugins info`` (backends/formats/exporters)."""
    return [g.split(".", 1)[-1] for g in _plugins.PLUGIN_GROUPS]


def _resolve_plugin_group(_plugins, token: str) -> "str | None":
    """Map a user token (full ``star.formats`` or short ``formats``) to a group id."""
    token = token.lower()
    for group in _plugins.PLUGIN_GROUPS:
        if token in (group, group.split(".", 1)[-1]):
            return group
    return None


def _print_plugin_list(_plugins) -> None:
    grouped = _plugins.list_plugins()
    total = sum(len(v) for v in grouped.values())
    print(f"star {APP_VERSION} - registered plugins ({total} total)\n")
    for group, meta in _plugins.PLUGIN_GROUPS.items():
        entries = grouped.get(group, [])
        alias = group.split(".", 1)[-1]
        print(f"{meta['label']} [{group}] ({alias}) - {len(entries)}:")
        if not entries:
            print("  (none registered)")
        for e in entries:
            mark = {True: "+", False: "-"}.get(e.get("available"), "?")
            prio = e.get("priority")
            prio_s = f"  prio={prio}" if prio is not None else ""
            exts = e.get("extensions") or []
            ext_s = "  " + " ".join(exts) if exts else ""
            line = f"  [{mark}] {e['name']:<14} -> {e.get('target', '?')}{prio_s}{ext_s}"
            print(line)
            if e.get("load_error"):
                print(f"        load error: {e['load_error']}")
        print()
    print("Legend: [+] available  [-] unavailable  [?] unknown (checked when used)")
    print("Details: star --plugins info <group> <name>   Contracts: star --plugins api")


def _print_plugin_info(info: "dict") -> None:
    print(f"{info['name']}  ({info['group']})")
    print(f"  target:       {info.get('target', '?')}")
    if info.get("distribution"):
        print(f"  distribution: {info['distribution']}")
    if info.get("load_error"):
        print(f"  load error:   {info['load_error']}")
        return
    print(f"  class:        {info.get('class', '?')}")
    if info.get("priority") is not None:
        print(f"  priority:     {info['priority']}")
    if info.get("extensions"):
        print(f"  extensions:   {' '.join(info['extensions'])}")
    avail = info.get("available")
    avail_s = "yes" if avail is True else "no" if avail is False else "unknown (checked at use)"
    print(f"  available:    {avail_s}")
    if info.get("doc"):
        print(f"  description:  {info['doc']}")


def _print_plugin_api(_plugins) -> None:
    api = _plugins.describe_api()
    ver = api[0]["api_version"] if api else "?"
    print(f"star plugin API contracts - api_version {ver}\n")
    print("Third-party plugins subclass one of these ABCs and register the")
    print("subclass in their package's [project.entry-points.<group>] table.\n")
    for spec in api:
        print(f"{spec['name']}  [entry-point group: {spec['group']}]")
        if spec.get("doc"):
            print(f"  {spec['doc']}")
        for m in spec["methods"]:
            tags = []
            if m["abstract"]:
                tags.append("abstract")
            if m["classmethod"]:
                tags.append("classmethod")
            tag_s = f"  ({', '.join(tags)})" if tags else ""
            print(f"    def {m['signature']}{tag_s}")
            if m["doc"]:
                print(f"        {m['doc']}")
        print()


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
        "--check-update",
        action="store_true",
        help="Check PyPI for a newer release of star and exit (best-effort, "
        "offline-safe — prints the result as plain text)",
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
    ap.add_argument(
        "--plugins",
        nargs="*",
        metavar="ARG",
        default=None,
        help="Inspect the plugin system and exit. Subcommands: "
        "'list' (all registered backends/format-handlers/exporters), "
        "'info <group> <name>' (one plugin's details), "
        "'api' (the plugin ABC contracts). Default: list.",
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

    if args.check_update:
        sys.exit(_check_update())

    if args.install_optional is not None:
        _install_optional(args.install_optional)
        return

    if args.plugins is not None:
        sys.exit(_run_plugins(args.plugins))

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
