#!/bin/bash
# SessionStart hook — prepare the repo for Claude Code on the web and guard the
# deterministic statutory-amount calculators against silent regression.
set -euo pipefail

# Web sessions only; local runs keep their own setup.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# 1) Install Python dependencies so app.py (and thus the tests) import cleanly in a
#    freshly-cloned web container. Idempotent; the container layer is cached after the
#    first session. Non-fatal if the index is unreachable or deps are pre-installed.
python3 -m pip install -q -r requirements.txt || \
  echo "note: pip install skipped/failed — dependencies may already be present"

# 2) Run the calculator unit tests (no network or credentials needed). These pin rupee
#    figures the app states AS LAW (gratuity / retrenchment / lay-off / overtime), so any
#    regression should be visible at session start rather than shipped silently.
echo "Running calculator unit tests…"
if python3 tests/test_calculators.py 2>/dev/null && python3 tests/test_calculators_new.py 2>/dev/null \
   && python3 tests/test_comparison.py 2>/dev/null && python3 tests/test_usage.py 2>/dev/null; then
  echo "✅ calculator unit tests passed"
else
  echo "‼️ calculator unit tests FAILED — the statutory amount calculators have regressed"
fi
