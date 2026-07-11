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

for attempt in 1 2 3; do
  _run "$@"
  code=$?
  [ "$code" -eq 0 ] && exit 0
  case "$code" in
    124 | 137 | 143)
      echo "::warning::pytest exceeded ${_dur}s and was killed on attempt $attempt — the Qt-teardown xdist wedge; retrying"
      ;;
    139 | 134 | 132 | 136)
      echo "::warning::pytest native crash (exit $code) on attempt $attempt — retrying (flaky Qt teardown)"
      ;;
    *)
      # A real, deterministic test failure — do not mask it with a retry.
      exit "$code"
      ;;
  esac
done
echo "::error::pytest still hanging/crashing after 3 attempts"
exit 1
