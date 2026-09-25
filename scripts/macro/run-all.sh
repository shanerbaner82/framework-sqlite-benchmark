#!/usr/bin/env bash
# Full suite, round-robin so slow drift on the device hits every app equally:
#   scripts/macro/run-all.sh SERIAL [RUNS]
# Installs builds/*.apk (after waiting for the device to be free), then for run 1..RUNS
# runs every app/mode once. Raw JSON lands in results/pixel9/APP-MODE-runN.json.
set -euo pipefail
cd "$(dirname "$0")/../.."
SERIAL=$1; RUNS=${2:-3}
MODES=${MODES:-"rn:default ns:default nativephp:pdo nativephp:laravel"}
scripts/macro/run.sh wait x 1 "$SERIAL"
[ -n "${SKIP_INSTALL:-}" ] || scripts/macro/install.sh "$SERIAL"
for run in $(seq 1 "$RUNS"); do
  for m in $MODES; do
    [ -f "results/pixel9/${m%%:*}-${m##*:}-run$run.json" ] && [ -z "${FORCE:-}" ] && { echo "skip existing ${m} run$run"; continue; }
    RUN_START=$run scripts/macro/run.sh "${m%%:*}" "${m##*:}" 1 "$SERIAL" || echo "FAILED $m run$run"
  done
done
python3 scripts/macro/report.py
