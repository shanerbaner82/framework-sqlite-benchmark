# Android SQLite benchmark

Three CLI-created apps run the same 17 SQLite cases on Android:

| App | SQLite implementation |
| --- | --- |
| `react-native/` | React Native 0.87.1 with [`react-native-nitro-sqlite`](https://github.com/margelo/react-native-nitro-sqlite) 9.7.0 |
| `nativescript/` | SolidJS with [`@edusperoni/nativescript-sqlite`](https://github.com/edusperoni/nativescript-plugins/pull/7), PR 7 commit `4c2e152e31edbdf289be1eeef0bf67ace44cfcc5` |
| `nativephp/` | NativePHP Mobile 4.4.1 and its default Laravel SQLite PDO connection; SuperNative (native UI), direct PHP, and per-query WebView modes |

The NativeScript fork source is checked out in `native-sqlite-fork/` and installed as a local npm dependency. A ZIP of the pinned plugin snapshot, including its native sources, compiled JavaScript entry files, license, and provenance, is at [nativescript/nativescript-sqlite-pr7-4c2e152.zip](nativescript/nativescript-sqlite-pr7-4c2e152.zip). Its Android runtime is pinned to NativeScript 8.9.2 because the fork's V8 bindings do not link with the 9.1 runtime. The published Solid template requires `--legacy-peer-deps` for npm installation.

## Workload

Each run creates a fresh 2,000-row deterministic `items` fixture and matching `events` rows. Fixture setup and post-case validation are outside timed intervals; query cases also check returned values during each timed operation. Every case has one untimed warmup and five timed samples; the report contains all samples, median, p95, and throughput. Operations are sequential on one connection or transaction. Each app requests WAL journal mode, `synchronous=FULL`, and foreign keys. The report records the values read back from its SQLite connection and runs `PRAGMA integrity_check` at the end.

| Case | Timed work |
| --- | --- |
| `schema_create_drop` | 30 create/drop cycles |
| `insert_autocommit` | 400 bound inserts |
| `insert_transaction` | 400 bound inserts in one transaction |
| `point_select` | 400 primary-key lookups |
| `indexed_filter` | 100 indexed equality queries |
| `range_scan` | 100 indexed score ranges with ordering |
| `full_scan_aggregate` | 40 full-table sums |
| `order_limit` | 100 ordered, limited and offset queries |
| `join_aggregate` | 100 indexed joins with counts |
| `like_search` | 50 substring searches |
| `json_extract` | 100 JSON field filters |
| `update_by_pk` | 400 primary-key updates |
| `delete_by_pk` | 200 primary-key deletes |
| `upsert` | 400 conflict-handling inserts |
| `transaction_rollback` | 50 insert-and-rollback transactions |
| `blob_insert_length` | 100 4 KiB BLOB inserts and length reads |
| `index_create` | One index build over 2,000 rows |

The two JavaScript apps and NativePHP's per-query WebView mode use the identical file `benchmark/runner.js` copied by `scripts/sync-runner.ps1`. The direct PHP port uses the same SQL, row counts, warmups, samples, and checks. Async JavaScript calls include native-call and scheduling cost for each operation. NativePHP's **Run SuperNative benchmark** mode is a NativePHP v4 native screen (`nativephp/app/NativeComponents/SqliteBenchmark.php`: Jetpack Compose UI driven by PHP in the persistent runtime). A native tap starts the PHP port of the suite, and every SQL call is one runloop round-trip: the screen's poll timer wakes PHP, PHP runs one call, the screen re-renders and publishes a frame, and the loop waits for the next tick. The case timer spans all of those round-trips, so this mode includes NativePHP's native UI-to-PHP scheduling cost per operation in the same way the JavaScript apps include each awaited native call. **Run PHP loop** runs the same PHP port inside one WebView request for the entire suite with no round-trips; its case timer wraps only the PDO calls, which is the SQLite floor for NativePHP. Every NativePHP mode uses the `pdo_sqlite` extension compiled into NativePHP's embedded PHP. **Run per-query UI benchmark** sends each SQL call from WebView JavaScript to a Laravel route, awaits its result, and checks query results in JavaScript before continuing. That mode includes a WebView-to-PHP request and response for every operation. SQLite versions can differ. Interpret these as **application API timings with different call boundaries**, and inspect the reported SQLite settings and versions before comparing.

## Build on Windows

Prerequisites: Node 24, Java 21, Android SDK with API 35 build tools, Android NDK and CMake, an Android emulator, and PHP 8.4 with Composer for NativePHP. NativePHP must run directly on Windows rather than WSL. The PHP binary and Composer used here are portable under `.tools/`; `scripts/composer.cmd` exposes them to NativePHP's build command.

```powershell
# From the repository root:
cd react-native
npm install
cd ..
node scripts/build-native-fork.js
.\scripts\sync-runner.ps1
node scripts/smoke-runner.mjs

cd react-native\android
.\gradlew.bat assembleDebug

cd ..\..\nativescript
npm install --legacy-peer-deps
npx nativescript@9.1.1 build android --no-hmr

cd ..\nativephp
composer install
php artisan native:plugin:list  # nativephp/mobile-ui must be registered; it ships the native text and button renderers
Copy-Item .env.example .env
php artisan key:generate
php artisan migrate --force
php artisan native:install android --no-interaction
php artisan native:run android --no-tty
```

The React Native debug APK needs Metro: run `npm start` in `react-native/` and `adb reverse tcp:8081 tcp:8081` before opening it. The NativePHP app ID and `NATIVEPHP_START_URL=/native` are included in `.env.example`; the app starts on its SuperNative screen, and its **Open WebView benchmark** button leaves to the legacy WebView screen with the other two modes. On a fresh Windows machine, configure PHP's `openssl.cafile` and `curl.cainfo` so the NativePHP installer can fetch its PHP binary manifest.

## Run and collect

Use one emulator and run one app at a time. Build and run all apps with the same build type. The debug builds are for functional checks; use release builds for performance claims. Close other apps and repeat complete runs before drawing conclusions.

1. Open each app and tap **Run benchmark**. NativePHP opens on its native screen with **Run SuperNative benchmark**; its WebView screen has separate **Run PHP loop** and **Run per-query UI benchmark** buttons. Wait for **Complete**. Each case is validated; errors remain visible in the result list. The per-query mode makes many WebView requests and takes substantially longer.
2. NativeScript saves `sqlite-benchmark-results.json` in app documents. Run `.\scripts\collect-nativescript.ps1` from the repository root to copy it into `results/nativescript.json`.
3. React Native displays and shares its JSON. For ADB collection, clear logcat immediately before the run with `adb logcat -c`, then run `.\scripts\collect-react-native.ps1` to reassemble its numbered log chunks into `results/react-native.json`.
4. NativePHP's native screen lists its results, and its WebView displays and downloads JSON. Its Laravel app saves every report. Run `.\scripts\collect-nativephp.ps1 -Mode native` for the SuperNative run (`results/nativephp-native.json`), `.\scripts\collect-nativephp.ps1` for the PHP loop (`results/nativephp.json`) and `.\scripts\collect-nativephp.ps1 -Mode ui` for the per-query run (`results/nativephp-ui.json`).
5. Compare reports with `python scripts/compare.py results/nativescript.json results/react-native.json results/nativephp-ui.json`; the first report is the delta baseline. Include `results/nativephp-native.json` and `results/nativephp.json` to see all three NativePHP modes.

For signed release APKs on a physical device, clear that device's logcat immediately before each run. After the app shows **Complete**, run `powershell -ExecutionPolicy Bypass -File scripts/collect-release-logcat.ps1 -Serial DEVICE_SERIAL -Output results/pixel7/APP-release.json`. The release collector verifies the completion marker, all 17 case statuses, and `integrity_check=ok`. Use NativePHP's **Run per-query UI benchmark** button for the WebView comparison. For the SuperNative run, tap **Export report to logcat** after **Complete**; it opens a WebView page that logs the saved report in the same chunk format, then run the collector with `-Output results/pixel7/nativephp-native-release.json`.

The benchmark resets only its own `items`, `events`, `writes`, and `blobs` tables on every run. It does not touch Laravel's application tables.

## Verification

- `node scripts/smoke-runner.mjs` runs all 17 JavaScript cases on Node's built-in SQLite.
- `php nativephp/benchmark-cli.php` runs the PHP suite against the development SQLite database.
- React Native TypeScript checking: `cd react-native; npx tsc --noEmit`.
- Android functional verification uses the `Medium_Phone_API_36.1` emulator and checks the result list plus `integrity_check`.

The measured emulator comparison is in [RESULTS.md](RESULTS.md). The connected Pixel 7 release comparison, signed APKs, and raw reports are in [RESULTS-PIXEL7.md](RESULTS-PIXEL7.md).

## Automated runs (Jetpack Macrobenchmark)

`macrobenchmark/` is a standalone Gradle project that drives each app over repeated cold starts instead of one manual run, so results come with per-iteration values and a run-to-run spread rather than a single sample. Each app wraps every timed sample in an `android.os.Trace` section, and `TraceSectionMetric` reads them back; `Mode.Count` verifies no sample was dropped. `scripts/macro/` holds a bash port of the build steps above plus the run and reporting scripts.

```bash
scripts/macro/build.sh              # rn ns nativephp -> builds/*.apk
scripts/macro/macro.sh <SERIAL> 5   # 5 cold-start iterations per app/mode, with cooldowns
python3 scripts/macro/table_png.py results/pixel9/macro/<RUN_TAG>
```

A Pixel 9 comparison produced this way, including the caveat about NativePHP's PHP-loop mode having no per-call boundary, is in [RESULTS-PIXEL9.md](RESULTS-PIXEL9.md).
