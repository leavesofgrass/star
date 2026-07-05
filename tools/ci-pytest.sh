#!/usr/bin/env bash
# Run pytest, retrying ONLY on a native crash (segfault / abort) — never on a
# real test failure.
#
# The exit-139 Qt-teardown segfault is now PREVENTED structurally: pytest runs
# under xdist with `--dist loadgroup` (see pyproject addopts), which pins every
# Qt test to one worker so they run in their crash-free serial order while the
# non-GUI bulk parallelizes.  This retry loop stays as a thin backstop: exit
# codes 139 (SIGSEGV), 134 (SIGABRT), 132/136 (SIGILL/SIGFPE) are a native crash
# and are retried up to three times; any other non-zero exit is a genuine test
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
