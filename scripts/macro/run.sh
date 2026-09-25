#!/usr/bin/env bash
# One command per app/mode: scripts/macro/run.sh APP MODE [RUNS] [SERIAL]
#   APP/MODE: rn default | ns default | nativephp pdo|laravel|ui
# Each run: force-stop, clear logcat, cold launch, wait for UI, tap the run button,
# wait for the SQLITE_BENCHMARK_DONE marker, collect + validate JSON into results/pixel9/.
# Before every timed run it waits until no other benchmark/build is active on this machine.
set -euo pipefail
cd "$(dirname "$0")/../.."
export ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
APP=$1; MODE=${2:-default}; RUNS=${3:-3}
SERIAL=${4:-${SERIAL:-$($ADB devices | awk 'NR>1 && $2=="device"{print $1; exit}')}}
OUTDIR=${OUTDIR:-results/pixel9}
LOCK=/tmp/framework-sqlite-benchmark.timing.lock
OTHER_PKG=com.nativephp.sqlitebench
case "$APP" in
  wait) PKG=none ;;
  rn) PKG=com.sqlitebenchmark.reactnative; ACT=.MainActivity; LABEL='run benchmark'; TIMEOUT=600 ;;
  ns) PKG=com.sqlitebenchmark.nativescript; ACT=com.tns.NativeScriptActivity; LABEL='run benchmark'; TIMEOUT=600 ;;
  nativephp) PKG=com.sqlitebenchmark.nativephp; ACT=com.nativephp.mobile.ui.MainActivity; TIMEOUT=300
    case "$MODE" in
      pdo) LABEL='Run PHP loop' ;; laravel) LABEL='PHP loop Laravel DB' ;;
      ui) LABEL='Run per-query UI benchmark'; TIMEOUT=2400 ;;
      *) echo "unknown nativephp mode $MODE"; exit 2 ;;
    esac ;;
  *) echo "unknown app $APP"; exit 2 ;;
esac

busy_reason() {
  if [ -e "$LOCK" ] && [ "$(cat "$LOCK" 2>/dev/null)" != "$$" ] && kill -0 "$(cat "$LOCK")" 2>/dev/null; then echo "lock $LOCK held"; return; fi
  if pgrep -f 'artisan native:run' >/dev/null; then echo "native:run running"; return; fi
  if pgrep -f 'GradleWrapperMain|gradle-launcher|nativescript.*build' >/dev/null; then echo "gradle/ns build running"; return; fi
  # the other worker's app may sit idle in the foreground; only treat it as busy while it burns CPU
  local cpu; cpu=$($ADB -s "$SERIAL" shell top -b -n 2 -d 2 -q -o %CPU,ARGS 2>/dev/null | awk -v p="$OTHER_PKG" '$2==p{v=int($1)} END{print v}')
  if [ -n "$cpu" ] && [ "$cpu" -gt 5 ]; then echo "other benchmark app $OTHER_PKG using ${cpu}% CPU"; return; fi
  local load; load=$(sysctl -n vm.loadavg | awk '{print $2}')
  if awk "BEGIN{exit !($load > ${MAX_LOAD:-6})}"; then echo "1-min load $load > ${MAX_LOAD:-6}"; return; fi
}
wait_free() {  # require QUIET_CHECKS consecutive idle checks 30 s apart (default 4 = ~2 min of quiet)
  local r quiet=0
  while [ "$quiet" -lt "${QUIET_CHECKS:-4}" ]; do
    r=$(busy_reason)
    if [ -n "$r" ]; then quiet=0; echo "$(date +%T) busy: $r"; else quiet=$((quiet+1)); fi
    if [ "$quiet" -lt "${QUIET_CHECKS:-4}" ]; then sleep 30; fi
  done
}

if [ "$APP" = wait ]; then wait_free; exit 0; fi
mkdir -p "$OUTDIR"
echo "device $SERIAL: $($ADB -s "$SERIAL" shell getprop ro.product.model) Android $($ADB -s "$SERIAL" shell getprop ro.build.version.release) API $($ADB -s "$SERIAL" shell getprop ro.build.version.sdk) emulator=$($ADB -s "$SERIAL" shell getprop ro.kernel.qemu)"
RUN_START=${RUN_START:-1}
for run in $(seq "$RUN_START" $((RUN_START + RUNS - 1))); do
  wait_free
  echo $$ > "$LOCK"; trap 'rm -f "$LOCK"' EXIT
  OUT="$OUTDIR/$APP-$MODE-run$run.json"
  BATT=$($ADB -s "$SERIAL" shell dumpsys battery | awk -F': ' '/^ *level:/{l=$2} / temperature:/{t=$2/10} END{print "battery=" l "% temp=" t "C"}')
  THERM=$($ADB -s "$SERIAL" shell dumpsys thermalservice | awk -F': ' '/Thermal Status/{print "thermal_status=" $2; exit}')
  echo "$(date '+%F %T') $SERIAL $APP $MODE run$run $BATT $THERM" | tee -a "$OUTDIR/device-log.txt"
  $ADB -s "$SERIAL" shell am force-stop "$PKG"; sleep 3
  $ADB -s "$SERIAL" logcat -c
  $ADB -s "$SERIAL" shell am start -W -n "$PKG/$ACT" >/dev/null
  sleep 5
  python3 scripts/macro/tap.py "$SERIAL" "$LABEL" 90
  sleep 3   # let the UI settle before we start polling
  python3 scripts/macro/collect_logcat.py "$SERIAL" "$OUT" --wait "$TIMEOUT"
  $ADB -s "$SERIAL" shell am force-stop "$PKG"
  rm -f "$LOCK"; trap - EXIT
  python3 - "$OUT" <<'PY'
import json,sys; d=json.load(open(sys.argv[1])); m=d['metadata']
print(sys.argv[1], d.get('driver'), 'sqlite', m['sqlite_version'], m['journal_mode'], 'sync', m['synchronous'], 'integrity', m['integrity_check'], 'sum-of-medians %.1f ms' % sum(r['median_ms'] for r in d['results']))
PY
  sleep 10
done
