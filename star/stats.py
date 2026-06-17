"""Reading statistics, library/bookshelf, and profile presets."""
from ._runtime import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# Helper — settings fingerprint
# ---------------------------------------------------------------------------


def _settings_fingerprint(settings: "Settings") -> str:
    """Hash the settings values that affect document parsing output."""
    key = (
        f"{settings['tts_skip_code']}"
        f"|{settings.get('table_reading_mode', 'structured')}"
        f"|{settings.get('footnote_mode', 'inline')}"
    )
    import hashlib

    return hashlib.md5(key.encode()).hexdigest()[:8]


# =============================================================================
# Reading statistics & library
# =============================================================================


def _fmt_duration(seconds: float) -> str:
    """Render a duration in seconds as a compact human string."""
    seconds = int(max(0, round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class ReadingStats:
    """Per-document reading-time and progress tracker.

    Designed to be driven by a periodic ``tick(speaking, path, word_idx,
    total_words)`` poll from either UI — the curses main loop or a Qt
    ``QTimer`` — so it needs no hooks into every play/stop path.  Time is
    accrued only while speech is actually playing; stats live in memory and
    are flushed to ``settings['reading_stats']`` every few seconds and on
    each pause/stop, keeping disk writes infrequent.
    """

    FLUSH_INTERVAL = 5.0

    def __init__(self, settings: "Settings") -> None:
        self.settings = settings
        self._path: str = ""
        self._last_tick: Optional[float] = None
        self._last_flush: float = 0.0
        self._prev_active: bool = False
        # In-memory accumulators for the document currently being read.
        self._sec: float = 0.0
        self._words_read: int = 0
        self._words_total: int = 0
        self._pct: int = 0
        self._sessions: int = 0

    def _load_doc(self, path: str) -> None:
        rec = dict(self.settings.get("reading_stats", {}).get(path, {}))
        self._sec = float(rec.get("seconds", 0.0))
        self._words_read = int(rec.get("words_read", 0))
        self._words_total = int(rec.get("words_total", 0))
        self._pct = int(rec.get("pct", 0))
        self._sessions = int(rec.get("sessions", 0))

    def tick(
        self,
        speaking: bool,
        path: str,
        word_idx: int = -1,
        total_words: int = 0,
    ) -> None:
        now = time.monotonic()
        active = bool(speaking and path)
        if active:
            if not self._prev_active or self._path != path:
                # A new reading session began (or the document changed).
                if self._path and self._prev_active:
                    self.flush()
                self._path = path
                self._load_doc(path)
                self._sessions += 1
                self._last_tick = now
                self._last_flush = now
            else:
                self._sec += max(0.0, now - (self._last_tick or now))
                self._last_tick = now
            if total_words > 0 and word_idx >= 0:
                self._words_total = total_words
                self._words_read = max(self._words_read, min(word_idx + 1, total_words))
                self._pct = int(100 * self._words_read / total_words)
            if now - self._last_flush >= self.FLUSH_INTERVAL:
                self.flush()
                self._last_flush = now
        else:
            if self._prev_active:
                if self._last_tick is not None:
                    self._sec += max(0.0, now - self._last_tick)
                self.flush()
                self._last_tick = None
        self._prev_active = active

    def flush(self) -> None:
        """Persist the current document's accumulated stats to settings."""
        if not self._path:
            return
        stats = dict(self.settings.get("reading_stats", {}))
        stats[self._path] = {
            "seconds": round(self._sec, 1),
            "words_read": self._words_read,
            "words_total": self._words_total,
            "pct": self._pct,
            "sessions": self._sessions,
            "last_ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if len(stats) > 500:
            evict = sorted(stats, key=lambda k: stats[k].get("last_ts", ""))[:100]
            for k in evict:
                del stats[k]
        self.settings.set("reading_stats", stats)


def _record_library(settings: "Settings", doc: "Document") -> None:
    """Record/refresh a document's entry in the library."""
    path = getattr(doc, "path", "") or ""
    if not path or getattr(doc, "format", "") == "error":
        return
    lib = dict(settings.get("library", {}))
    rec = dict(lib.get(path, {}))
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    rec.setdefault("added", now)
    rec["title"] = (doc.title or Path(path).name)[:200]
    rec["format"] = getattr(doc, "format", "") or ""
    rec["last_opened"] = now
    lib[path] = rec
    if len(lib) > 500:
        evict = sorted(lib, key=lambda k: lib[k].get("last_opened", ""))[:100]
        for k in evict:
            del lib[k]
    settings.set("library", lib)


def _library_entries(settings: "Settings") -> List[Dict[str, Any]]:
    """Return library documents merged with progress and time-read data,
    newest-opened first."""
    lib = settings.get("library", {}) or {}
    positions = settings.get("reading_positions", {}) or {}
    stats = settings.get("reading_stats", {}) or {}
    entries: List[Dict[str, Any]] = []
    for path, rec in lib.items():
        pct = positions.get(path, {}).get("pct")
        if pct is None:
            pct = stats.get(path, {}).get("pct", 0)
        entries.append(
            {
                "path": path,
                "title": rec.get("title") or Path(path).name,
                "format": rec.get("format", ""),
                "last_opened": rec.get("last_opened", ""),
                "added": rec.get("added", ""),
                "pct": int(pct or 0),
                "seconds": float(stats.get(path, {}).get("seconds", 0.0)),
            }
        )
    entries.sort(key=lambda e: e.get("last_opened", ""), reverse=True)
    return entries


def _format_reading_stats(
    settings: "Settings", current_path: str = "", current_title: str = ""
) -> str:
    """Build a Markdown reading-statistics dashboard."""
    stats = settings.get("reading_stats", {}) or {}
    lib = settings.get("library", {}) or {}
    lines: List[str] = ["# Reading Statistics", ""]
    if not stats:
        lines.append(
            "No reading time recorded yet. Start playing a document "
            "and your progress will be tracked here."
        )
        return "\n".join(lines)

    total_seconds = sum(float(r.get("seconds", 0.0)) for r in stats.values())
    total_words = sum(int(r.get("words_read", 0)) for r in stats.values())
    lines += [
        "## Totals",
        "",
        f"- **Time read:** {_fmt_duration(total_seconds)}",
        f"- **Words read:** {total_words:,}",
        f"- **Documents tracked:** {len(stats)}",
        "",
    ]

    cur = stats.get(current_path) if current_path else None
    if cur:
        title = current_title or lib.get(current_path, {}).get(
            "title", Path(current_path).name
        )
        lines += [
            "## Current Document",
            "",
            f"- **{title}**",
            f"- Progress: {int(cur.get('pct', 0))}%  "
            f"({int(cur.get('words_read', 0)):,} / "
            f"{int(cur.get('words_total', 0)):,} words)",
            f"- Time read: {_fmt_duration(cur.get('seconds', 0.0))}",
            f"- Sessions: {int(cur.get('sessions', 0))}",
            "",
        ]

    # Top documents by time read.
    ranked = sorted(
        stats.items(), key=lambda kv: kv[1].get("seconds", 0.0), reverse=True
    )[:10]
    lines += [
        "## Most-read Documents",
        "",
        "| Document | Progress | Time |",
        "|---|---|---|",
    ]
    for path, r in ranked:
        title = lib.get(path, {}).get("title", Path(path).name)
        title = (title[:48] + "…") if len(title) > 49 else title
        lines.append(
            f"| {title} | {int(r.get('pct', 0))}% | "
            f"{_fmt_duration(r.get('seconds', 0.0))} |"
        )
    lines.append("")
    return "\n".join(lines)


# =============================================================================
# Voice & profile presets (named bundles of settings)
# =============================================================================

# Settings keys captured and restored by a named profile.  Font/spacing keys
# are Qt-only and simply ignored by the TUI; speech keys apply to both.
PROFILE_KEYS: List[str] = [
    "tts_backend",
    "tts_voice",
    "tts_rate",
    "tts_volume",
    "use_ssml",
    "theme",
    "qt_font_family",
    "qt_font_size",
    "font_size",
    "qt_line_height",
    "qt_letter_spacing",
    "qt_word_spacing",
    "qt_dyslexia_font",
    "qt_bionic_reading",
    "qt_current_line_highlight",
    "highlight_style",
    "highlight_color",
    "highlight_speed",
    "highlight_lead_words",
    "highlight_granularity",
]


def _save_profile(settings: "Settings", name: str) -> bool:
    """Capture the current values of PROFILE_KEYS into a named profile."""
    name = (name or "").strip()
    if not name:
        return False
    profiles = dict(settings.get("profiles", {}))
    profiles[name] = {
        k: settings.get(k) for k in PROFILE_KEYS if settings.get(k) is not None
    }
    settings.set("profiles", profiles)
    return True


def _apply_profile_values(settings: "Settings", name: str) -> Optional[Dict[str, Any]]:
    """Write a named profile's stored values back into settings.

    Returns the applied value dict, or None if the profile does not exist.
    Only writes recognized PROFILE_KEYS; the caller is responsible for any
    runtime side-effects (re-theming, re-selecting the backend, etc.).
    """
    prof = (settings.get("profiles", {}) or {}).get(name)
    if not prof:
        return None
    for k, v in prof.items():
        if k in PROFILE_KEYS:
            settings._data[k] = v
    settings.save()
    return dict(prof)


def _delete_profile(settings: "Settings", name: str) -> bool:
    profiles = dict(settings.get("profiles", {}))
    if name in profiles:
        del profiles[name]
        settings.set("profiles", profiles)
        return True
    return False
