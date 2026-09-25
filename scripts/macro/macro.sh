#!/usr/bin/env bash
# Jetpack Macrobenchmark run of the whole matrix on one device:
#   scripts/macro/macro.sh SERIAL [ITERATIONS] [TEST ...]
# TESTs (methods of com.sqlitebenchmark.macro.SqliteSuiteBenchmark): nativescript reactnative nativephpPdo
#   nativephpLaravel   (default: all, in that order)
# Builds+installs the macrobenchmark APK (and builds/*.apk unless SKIP_INSTALL=1), waits until the
# device is free (another benchmark may share it), lets the device cool between apps, then pulls
# Macrobenchmark JSON + per-iteration in-app reports into results/pixel9/macro/<RUN_TAG>/<test>/.
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT=$PWD
export ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
export JAVA_HOME=${JAVA_HOME:-$HOME/Library/Java/JavaVirtualMachines/jbr-21.0.11/Contents/Home}
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}
SERIAL=$1; ITER=${2:-5}; shift $(( $# >= 2 ? 2 : $# ))
TESTS=${*:-nativescript reactnative nativephpPdo nativephpLaravel}
RUN_TAG=${RUN_TAG:-$(date +%Y%m%d-%H%M)}
OUT=results/pixel9/macro/$RUN_TAG
COOL_C=${COOL_C:-36}            # battery temperature (C) to cool down to before each app
COOL_MAX=${COOL_MAX:-600}       # max seconds to wait for cooldown
MEDIA=/sdcard/Android/media/com.sqlitebenchmark.macro
LOCK=/tmp/framework-sqlite-benchmark.timing.lock
mkdir -p "$OUT"
(cd macrobenchmark && bash ./gradlew -q :bench:assembleDebug)
[ -n "${SKIP_INSTALL:-}" ] || { MAX_LOAD=1000 QUIET_CHECKS=${QUIET_CHECKS:-2} scripts/macro/run.sh wait x 1 "$SERIAL"; scripts/macro/install.sh "$SERIAL"; }
$ADB -s "$SERIAL" install -r -t macrobenchmark/bench/build/outputs/apk/debug/bench-debug.apk >/dev/null
$ADB -s "$SERIAL" shell svc power stayon true || true
{
  for p in ro.product.model ro.product.device ro.build.version.release ro.build.version.sdk ro.build.fingerprint ro.kernel.qemu; do echo "$p=$($ADB -s "$SERIAL" shell getprop $p)"; done
  for pkg in com.sqlitebenchmark.nativescript com.sqlitebenchmark.reactnative com.sqlitebenchmark.nativephp; do
    echo "$pkg $($ADB -s "$SERIAL" shell dumpsys package $pkg | grep -m1 -E 'versionName') flags: $($ADB -s "$SERIAL" shell dumpsys package $pkg | grep -m1 -oE 'pkgFlags=\[[^]]*\]')"
  done
} > "$OUT/device.txt"
cat "$OUT/device.txt"
batt() { $ADB -s "$SERIAL" shell dumpsys battery | awk -F': ' '/^ *level:/{l=$2} / temperature:/{t=$2/10} END{print l, t}'; }
therm() { $ADB -s "$SERIAL" shell dumpsys thermalservice | awk -F': ' '/Thermal Status/{print $2; exit}'; }
for t in $TESTS; do
  MAX_LOAD=1000 QUIET_CHECKS=${QUIET_CHECKS:-2} scripts/macro/run.sh wait x 1 "$SERIAL"
  echo $$ > "$LOCK"; trap 'rm -f "$LOCK"' EXIT
  waited=0
  while read -r lvl temp < <(batt); awk "BEGIN{exit !($temp > $COOL_C)}" || [ "$(therm)" != 0 ]; do
    [ $waited -ge $COOL_MAX ] && { echo "cooldown timeout (temp $temp C)"; break; }
    echo "$(date +%T) cooling: battery $temp C, thermal status $(therm)"; sleep 30; waited=$((waited+30))
  done
  read -r lvl temp < <(batt)
  echo "$(date '+%F %T') $t start: battery ${lvl}% ${temp}C thermal_status=$(therm)" | tee -a "$OUT/device-log.txt"
  $ADB -s "$SERIAL" shell rm -rf "$MEDIA" || true
  for attempt in 1 2 3; do   # rc 255 = adb server was restarted under us (shared machine); retry the whole test
    set +e
    $ADB -s "$SERIAL" shell am instrument -w -r \
        -e class "com.sqlitebenchmark.macro.SqliteSuiteBenchmark#$t" -e iterations "$ITER" -e compilation "${COMPILATION:-full}" \
        -e androidx.benchmark.suppressErrors "${SUPPRESS:-DEBUGGABLE}" \
        com.sqlitebenchmark.macro/androidx.test.runner.AndroidJUnitRunner > "$OUT/$t-instrument.txt" 2>&1
    rc=$?
    set -e
    grep -q 'OK (1 test)' "$OUT/$t-instrument.txt" && break
    echo "$(date +%T) $t attempt $attempt failed (rc=$rc); retrying in 30s" | tee -a "$OUT/device-log.txt"
    $ADB -s "$SERIAL" shell am force-stop com.sqlitebenchmark.macro || true
    sleep 30; $ADB -s "$SERIAL" shell rm -rf "$MEDIA" || true
  done
  read -r lvl temp < <(batt)
  echo "$(date '+%F %T') $t end rc=$rc: battery ${lvl}% ${temp}C thermal_status=$(therm)" | tee -a "$OUT/device-log.txt"
  mkdir -p "$OUT/$t"
  $ADB -s "$SERIAL" pull "$MEDIA/." "$OUT/$t/" >/dev/null 2>&1 || true
  find "$OUT/$t" -name '*.perfetto-trace' -size +1k | tail -n +3 | xargs rm -f   # keep 2 traces per test for inspection (size)
  grep -E 'OK \(|FAILURES|Error|Exception' "$OUT/$t-instrument.txt" | head -5 || true
  rm -f "$LOCK"; trap - EXIT
  sleep "${GAP:-20}"
done
python3 scripts/macro/macro_report.py "$OUT" || true
