#!/usr/bin/env bash
# Run pytest, retrying ONLY on a native crash (segfault / abort) — never on a
# real test failure.
#
# Building ~90 QWidgets in one process intermittently segfaults PyQt6 on Linux
# during window teardown/construction (a known Qt flake, not a product or test
# bug — it never reproduces on Windows/macOS and the app works fine).  Exit codes
# 139 (SIGSEGV), 134 (SIGABRT), 132/136 (SIGILL/SIGFPE) are that native crash and
# are retried up to three times.  Any other non-zero exit is a genuine test
# failure and fails the job immediately.
#
# Usage: bash tools/ci-pytest.sh python -m pytest [args...]
for attempt in 1 2 3; do
  "$@"
  code=$?
  [ "$code" -eq 0 ] && exit 0
  case "$code" in
    139 | 134 | 132 | 136)
      echo "::warning::pytest native crash (exit $code) on attempt $attempt — retrying (flaky Qt teardown)"
      ;;
    *)
      exit "$code"
      ;;
  esac
done
echo "::error::pytest still crashing after 3 attempts"
exit 1
