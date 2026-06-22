"""Hot-folder watching: convert files dropped into a directory, unattended.

This builds on the batch-conversion core — every detected file goes through the
SAME :func:`convert.convert_file` (``load_document`` -> export) pipeline, in the
configurable format the batch feature exposes.  Design points the feature
requires:

* **Real filesystem events** via ``watchdog`` when it is installed; a simple
  directory-polling fallback otherwise (so ``--watch`` still works, just less
  efficiently, without the optional dependency).  watchdog is a new optional
  dependency — install with ``pip install "star-reader[watch]"``.
* **Debounce / partial-write safety.** A file copied into the folder is not an
  atomic event, so each candidate is processed only after its size has stayed
  unchanged for a short window (and it can be opened for reading), avoiding
  reads of half-written files.
* **Source disposition.** On success the source is moved to
  ``<input>/processed/``; on failure it is moved to ``<input>/failed/`` — never
  left in the watched directory (which would be reprocessed on every restart,
  since startup rescans existing files) and never confused with a success.
  Name collisions in either subfolder are disambiguated, never overwritten.
* **Logging.** Every attempt (success or failure) is logged with a timestamp to
  ``<output>/star-watch.log`` (and the console), because nobody is watching.
* **Graceful shutdown.** SIGINT/SIGTERM stop the watcher cleanly; a file that is
  mid-conversion when the signal arrives is allowed to finish first.
"""

from ._runtime import *  # noqa: F401,F403
from .convert import _unique_path, convert_file, resolve_format
from .settings import Settings

try:  # watchdog is optional (the [watch] extra); fall back to polling without it
    from watchdog.events import FileSystemEventHandler as _FSHandler
    from watchdog.observers import Observer as _Observer

    _WATCHDOG = True
except ImportError:  # pragma: no cover - exercised only without the extra
    _FSHandler = object  # type: ignore[assignment,misc]
    _Observer = None  # type: ignore[assignment]
    _WATCHDOG = False


def _make_logger(output_dir: Path) -> "logging.Logger":
    """A logger writing timestamped lines to ``<output>/star-watch.log`` + stderr."""
    import logging

    logger = logging.getLogger(f"star.watch.{id(output_dir)}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s  %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(output_dir / "star-watch.log", encoding="utf-8")
            fh.setFormatter(formatter)
            logger.addHandler(fh)
        except OSError:
            pass
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger


class HotFolderWatcher:
    """Watch *input_dir* and convert each stable file into *output_dir*."""

    def __init__(
        self,
        input_dir: "str | Path",
        output_dir: "str | Path",
        fmt: str,
        settings: Settings,
        *,
        stable_seconds: "Optional[float]" = None,
        poll_interval: "Optional[float]" = None,
        move_processed: "Optional[bool]" = None,
        processed_subdir: str = "processed",
        failed_subdir: str = "failed",
        logger: "Optional[logging.Logger]" = None,
    ):
        self.input_dir = Path(input_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.fmt = resolve_format(fmt)  # validate up front, reusing Feature 1
        self.settings = settings
        # Tuning falls back to settings, then to sensible defaults.
        self.stable_seconds = float(
            stable_seconds
            if stable_seconds is not None
            else settings.get("watch_stable_seconds", 2.0)
        )
        self.poll_interval = float(
            poll_interval
            if poll_interval is not None
            else settings.get("watch_poll_interval", 0.5)
        )
        self.move_processed = bool(
            move_processed
            if move_processed is not None
            else settings.get("watch_move_processed", True)
        )
        self.processed_dir = self.input_dir / processed_subdir
        self.failed_dir = self.input_dir / failed_subdir
        self.log = logger or _make_logger(self.output_dir)

        self._stop = threading.Event()
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._pending: "set[str]" = set()  # enqueued/in-flight (dedupe)
        self._lock = threading.Lock()
        self._worker: "Optional[threading.Thread]" = None
        self._poller: "Optional[threading.Thread]" = None
        self._observer = None

    # -- event intake -----------------------------------------------------
    def _is_own_subdir(self, p: Path) -> bool:
        return self.processed_dir in p.parents or self.failed_dir in p.parents

    def _enqueue(self, path: "str | Path") -> None:
        p = Path(path)
        try:
            if p.is_dir() or self._is_own_subdir(p):
                return
        except OSError:
            return
        key = str(p)
        with self._lock:
            if key in self._pending:
                return
            self._pending.add(key)
        self._queue.put(key)

    # -- debounce ---------------------------------------------------------
    def _wait_until_stable(self, p: Path) -> bool:
        """Return True once *p*'s size has held steady and it opens for reading.

        Guards against processing a file that is still being copied/written.
        Returns False if it vanishes, never stabilises, or a stop is requested.
        """
        last_size = -1
        held = 0.0
        deadline = time.monotonic() + 600.0  # safety cap for pathological copies
        while not self._stop.is_set():
            try:
                size = p.stat().st_size
            except OSError:
                return False  # removed/renamed before it settled
            if size == last_size and size > 0:
                held += self.poll_interval
                if held >= self.stable_seconds:
                    try:
                        with open(p, "rb"):
                            pass
                    except OSError:
                        held = 0.0  # still locked by the writer; keep waiting
                    else:
                        return True
            else:
                held = 0.0
                last_size = size
            if time.monotonic() > deadline:
                self.log.warning("giving up waiting for %s to stabilise", p.name)
                return False
            self._stop.wait(self.poll_interval)
        return False

    # -- per-file processing ---------------------------------------------
    def _disambiguated_move(self, src: Path, dest_dir: Path) -> str:
        """Move *src* into *dest_dir*, disambiguating an existing same-name file."""
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            if dest.exists():
                stamp = time.strftime("%Y%m%d-%H%M%S")
                dest = _unique_path(dest_dir / f"{src.stem}.{stamp}{src.suffix}")
            shutil.move(str(src), str(dest))
            return str(dest)
        except OSError as exc:
            self.log.error("could not move %s: %s", src.name, exc)
            return ""

    def _process(self, key: str) -> None:
        p = Path(key)
        if not self._wait_until_stable(p):
            return
        self.log.info("converting %s", p.name)
        result = convert_file(p, self.output_dir, self.fmt, self.settings)
        if result.ok:
            self.log.info("ok      %s -> %s", p.name, result.output)
            if self.move_processed:
                moved = self._disambiguated_move(p, self.processed_dir)
                if moved:
                    self.log.info("moved   %s -> %s", p.name, moved)
        else:
            # Move failures aside so they are not reprocessed on every restart,
            # and are never mistaken for a handled file.
            self.log.error("failed  %s :: %s", p.name, result.error)
            moved = self._disambiguated_move(p, self.failed_dir)
            if moved:
                self.log.info("moved   %s -> %s (failed)", p.name, moved)

    def _run_worker(self) -> None:
        while not self._stop.is_set():
            try:
                key = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._process(key)
            except Exception as exc:  # noqa: BLE001 - one bad file can't kill the loop
                self.log.error("unexpected error on %s: %s", Path(key).name, exc)
            finally:
                with self._lock:
                    self._pending.discard(key)
                self._queue.task_done()

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                for child in self.input_dir.iterdir():
                    if child.is_file():
                        self._enqueue(child)
            except OSError:
                pass
            self._stop.wait(max(1.0, self.poll_interval * 2))

    def _scan_existing(self) -> None:
        """Enqueue files already present (dropped while the watcher was down)."""
        try:
            for child in sorted(self.input_dir.iterdir()):
                if child.is_file():
                    self._enqueue(child)
        except OSError as exc:
            self.log.error("could not scan %s: %s", self.input_dir, exc)

    # -- lifecycle --------------------------------------------------------
    def start(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._worker = threading.Thread(target=self._run_worker, daemon=True)
        self._worker.start()
        self._scan_existing()
        if _WATCHDOG:

            class _Handler(_FSHandler):  # type: ignore[misc,valid-type]
                def __init__(self, watcher: "HotFolderWatcher"):
                    super().__init__()
                    self._w = watcher

                def on_created(self, event):  # noqa: ANN001
                    if not event.is_directory:
                        self._w._enqueue(event.src_path)

                def on_moved(self, event):  # noqa: ANN001
                    if not event.is_directory:
                        self._w._enqueue(event.dest_path)

            self._observer = _Observer()
            self._observer.schedule(
                _Handler(self), str(self.input_dir), recursive=False
            )
            self._observer.start()
            self.log.info(
                "watching %s (watchdog) -> %s  [format=%s]",
                self.input_dir,
                self.output_dir,
                self.fmt,
            )
        else:
            self._poller = threading.Thread(target=self._poll_loop, daemon=True)
            self._poller.start()
            self.log.warning(
                "watchdog not installed; using directory polling. "
                'Install with: pip install "star-reader[watch]"'
            )
            self.log.info(
                "watching %s (polling) -> %s  [format=%s]",
                self.input_dir,
                self.output_dir,
                self.fmt,
            )

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
        # Let the worker finish the file it is mid-conversion on before exiting.
        if self._worker is not None:
            self._worker.join(timeout=60)

    def run_forever(self) -> None:
        """Start watching and block until SIGINT/SIGTERM (headless entry point)."""
        import signal

        self.start()

        def _on_signal(signum, frame):  # noqa: ANN001
            self.log.info("stop signal received; finishing current file…")
            self._stop.set()

        for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
            if sig is not None:
                try:
                    signal.signal(sig, _on_signal)
                except (ValueError, OSError):
                    pass  # not running in the main thread; rely on KeyboardInterrupt
        try:
            while not self._stop.is_set():
                time.sleep(0.3)
        except KeyboardInterrupt:
            self._stop.set()
        self.stop()
        self.log.info("watcher stopped.")
