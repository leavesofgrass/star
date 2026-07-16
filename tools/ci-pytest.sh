#!/usr/bin/env bash
# Run pytest with a hard wall-clock backstop, retrying a flaky-teardown
# hang/crash up to three times — but NEVER a real test failure.
#
# The Qt-teardown flake shows up two ways, both retried here:
#
#   * NATIVE CRASH — a worker segfaults/aborts (exit 139/134/132/136).  The
#     `--dist loadgroup` pinning (pyproject addopts) keeps Qt tests on one
#     worker in crash-free order, so this is now rare.
#
#   * HANG — a worker wedges during SHUTDOWN and the pytest-xdist controller
#     waits on it forever.  This is the nasty one: it happens *outside* any
#     test's `faulthandler_timeout` window (which only dumps a traceback, it
#     doesn't kill), and it never yields a native-crash exit code — so without a
#     wall-clock cap the leg simply runs to the job's `timeout-minutes` (30-40
#     min) and is marked "cancelled", and this retry loop never fires.
#
# The fix for the hang is to wrap pytest in `timeout` (coreutils; present on
# Linux and in git-bash on Windows): pytest is KILLED after STAR_PYTEST_TIMEOUT
# seconds (SIGTERM, then SIGKILL via --kill-after), which `timeout` reports as
# 124/137/143 — treated here as a retryable flake.  This catches EVERY hang
# (in-test, fixture-teardown, or xdist-controller), not just the ones a per-test
# timeout could see, which is why an external cap beats pytest-timeout here.
#
# The suite finishes whole in ~30 s locally, so the 480 s default is ~15×
# headroom: a transient hang auto-recovers on the next attempt, and a genuinely
# stuck leg fails in minutes (× up to 3) instead of eating the runner's job
# timeout.  Set STAR_PYTEST_TIMEOUT=0 to disable the cap for local TDD.
#
# Usage: bash tools/ci-pytest.sh python -m pytest [args...]

_dur="${STAR_PYTEST_TIMEOUT:-480}"

# `timeout` may be absent on an unusual host — degrade to a plain run there.
if [ "$_dur" = "0" ] || ! command -v timeout >/dev/null 2>&1; then
  _run() { "$@"; }
else
  _run() { timeout --kill-after=30s "${_dur}s" "$@"; }
fi

# The xdist worker-crash signature.  When a *worker* segfaults, the controller
# survives, marks the dead worker's in-flight test failed, and exits 1 — NOT a
# native-crash code — so the exit-code case below would wrongly treat it as a
# real failure.  Detect it in the output and retry instead.  (A genuine failure
# recurs on every attempt and still fails after 3, so this never masks one.)
_XDIST_CRASH_RE='node down: Not properly terminated|crashed while running|Replacing crashed worker|worker .* crashed'

for attempt in 1 2 3; do
  _log="$(mktemp)"
  _run "$@" 2>&1 | tee "$_log"
  code=${PIPESTATUS[0]}
  if [ "$code" -eq 0 ]; then rm -f "$_log"; exit 0; fi
  _retry=""
  case "$code" in
    124 | 137 | 143)
      echo "::warning::pytest exceeded ${_dur}s and was killed on attempt $attempt — the Qt-teardown xdist wedge; retrying"
      _retry=1
      ;;
    139 | 134 | 132 | 136)
      echo "::warning::pytest native crash (exit $code) on attempt $attempt — retrying (flaky Qt teardown)"
      _retry=1
      ;;
    *)
      if grep -qE "$_XDIST_CRASH_RE" "$_log"; then
        echo "::warning::an xdist worker crashed (surfaced as exit $code) on attempt $attempt — retrying (flaky Qt teardown)"
        _retry=1
      fi
      ;;
  esac
  rm -f "$_log"
  # A real, deterministic test failure — do not mask it with a retry.
  [ -z "$_retry" ] && exit "$code"
done
echo "::error::pytest still hanging/crashing after 3 attempts"
exit 1
