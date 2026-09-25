#!/usr/bin/env bash
# usage: scripts/macro/install.sh SERIAL [apk ...]   (default: all APKs in builds/)
set -euo pipefail
cd "$(dirname "$0")/../.."
ADB=${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}
SERIAL=$1; shift
for apk in "${@:-builds/*.apk}"; do for f in $apk; do echo "installing $f"; $ADB -s "$SERIAL" install -r "$f"; done; done
