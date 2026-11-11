#!/usr/bin/env bash
# Every check to run before a deploy, in one command (offline and free: no LLM call, no e-mail).
#   scripts/check.sh            lint + tests + frontend build
#   scripts/check.sh --docker   … + build the Docker image
#   scripts/check.sh --live     … + read-only checks of the deployed app (scripts/smoke_live.py)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

step "Python lint (ruff)"
"$PY" -m ruff check backend evals scripts modal_deploy.py --select F,E9,B904,I001

step "Tests (pytest: offline, no API key, no network)"
"$PY" -m pytest backend/tests -q

step "Frontend lint (oxlint)"
(cd frontend && npx oxlint src --quiet)   # errors only; `npm run lint` also lists React style warnings

step "Frontend type check + production build (next build)"
(cd frontend && NEXT_TELEMETRY_DISABLED=1 npm run --silent build >/dev/null && echo "build OK")

if [[ " $* " == *" --docker "* ]]; then
  step "Docker image"
  docker build -q -t orvane-rh:check . >/dev/null && echo "image OK"
fi

if [[ " $* " == *" --live "* ]]; then
  step "Live app (read-only)"
  "$PY" scripts/smoke_live.py
fi

printf '\n\033[32mAll checks passed.\033[0m\n'
