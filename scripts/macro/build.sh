#!/usr/bin/env bash
# Build all apps (macOS/bash port of the README's Windows steps). usage: scripts/macro/build.sh [rn|ns|nativephp ...]
# Outputs signed release/profileable APKs into builds/. Install with scripts/macro/install.sh.
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT=$PWD
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}
export JAVA_HOME=${JAVA_HOME:-$HOME/Library/Java/JavaVirtualMachines/jbr-21.0.11/Contents/Home}
export PATH="${NODE_BIN:-$HOME/.nvm/versions/node/v22.21.1/bin}:$ANDROID_HOME/platform-tools:$PATH"
KS="$ROOT/react-native/android/app/debug.keystore"   # RN template's debug keystore (android/androiddebugkey/android), used to sign both JS release APKs
mkdir -p builds
# sync the shared JS runner (scripts/sync-runner.ps1)
cp benchmark/runner.js react-native/benchmark/runner.js
cp benchmark/runner.js nativescript/src/benchmark/runner.js
mkdir -p nativephp/public/benchmark && cp benchmark/runner.js nativephp/public/benchmark/runner.js
for app in "${@:-rn ns nativephp}"; do for a in $app; do case $a in
  rn) (cd react-native && npm install && cd android && bash ./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a)
      cp react-native/android/app/build/outputs/apk/release/app-release.apk builds/react-native-release.apk ;;
  ns) (cd nativescript && npm install --legacy-peer-deps && npx --yes nativescript@9.1.1 build android --release --no-hmr \
        --key-store-path "$KS" --key-store-password android --key-store-alias androiddebugkey --key-store-alias-password android \
        --copy-to "$ROOT/builds/nativescript-release.apk") ;;
  nativephp) (cd nativephp && composer install -n && { [ -f .env ] || { cp .env.example .env; php artisan key:generate -n; }; } \
        && { grep -q '^NATIVEPHP_APP_VERSION=' .env || echo 'NATIVEPHP_APP_VERSION=1.0.0' >> .env; } \
        && sed -i '' "s/^NATIVEPHP_APP_VERSION=.*/NATIVEPHP_APP_VERSION=1.0.$(date +%y%m%d%H%M)/" .env \
        && touch database/database.sqlite && php artisan migrate --force -n \
        && { [ -d nativephp/android ] || php artisan native:install android -n; } \
        && php artisan native:run android NO_INSTALL --build=profileable --start-url=/ --no-tty -n || true)
      # A non-DEBUG NATIVEPHP_APP_VERSION matters: with DEBUG the app re-extracts the whole Laravel bundle on EVERY
      # launch (inflates cold start); a fresh version per build makes it extract once after install.
      # native:run installs+launches on the given serial; the bogus serial makes it build only (install fails harmlessly).
      cp nativephp/nativephp/android/app/build/outputs/apk/profileable/app-profileable.apk builds/nativephp-profileable.apk ;;
esac; done; done
ls -la builds
