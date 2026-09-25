<?php

use App\Benchmark;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Route;

Route::view('/', 'benchmark');
// PHP loop: the whole suite runs inside this one request, no per-call boundary.
// api: "pdo" = raw PDO handle (prepare/execute/fetchAll), "laravel" = Laravel DB connection
// statement()/select(). Both run the same SQL, counts, warmups and samples on the default
// sqlite connection (the pdo_sqlite extension compiled into NativePHP's embedded PHP).
Route::post('/run', function (Request $request) {
    $api = $request->input('api') === 'laravel' ? 'laravel' : 'pdo';
    if (! file_exists($file = config('database.connections.sqlite.database'))) touch($file);
    $connection = DB::connection('sqlite');
    $handle = $connection->getPdo();
    $benchmark = new Benchmark($handle, $api === 'laravel' ? $connection : null);
    $benchmark->tracer = app(\Nativephp\MobileTrace\Tracer::class);
    $metadata = $benchmark->prepare();
    $results = array_map(fn ($case) => $benchmark->runCase($case), $benchmark->cases());
    $driver = 'pdo_sqlite via '.($api === 'laravel' ? 'Laravel DB connection' : 'raw handle').' (PHP loop)';
    $report = $benchmark->report($metadata + [
        'mode' => "php-loop-sqlite-$api",
        'connection' => 'sqlite',
        'connection_driver' => $connection->getDriverName(),
        'handle_class' => get_class($handle),
        'database_file' => basename(config('database.connections.sqlite.database')),
        'api' => $api,
        'nativephp_mobile' => \Composer\InstalledVersions::getPrettyVersion('nativephp/mobile'),
        'php' => PHP_VERSION,
        'traced' => $benchmark->tracer->available(),
    ], $results, $driver);
    file_put_contents(storage_path("app/sqlite-benchmark-results-sqlite-$api.json"), json_encode($report, JSON_THROW_ON_ERROR));
    return response()->json($report);
});

Route::post('/sql', function (Request $request) {
    $db = DB::connection()->getPdo();
    $action = $request->input('action');
    if ($action === 'begin') $db->beginTransaction();
    elseif ($action === 'commit') $db->commit();
    elseif ($action === 'rollback') $db->rollBack();
    elseif ($action === 'exec' || $action === 'rows') {
        $statement = $db->prepare($request->input('sql'));
        $statement->execute($request->input('params', []));
        $rows = $action === 'rows' ? $statement->fetchAll(PDO::FETCH_ASSOC) : [];
        $statement->closeCursor();
        return response()->json(['rows' => $rows]);
    } else abort(400, 'Unknown benchmark operation');
    return response()->json(['in_transaction' => $db->inTransaction()]);
});

Route::post('/report', function (Request $request) {
    $report = $request->all();
    file_put_contents(storage_path('app/sqlite-benchmark-ui-results.json'), json_encode($report, JSON_THROW_ON_ERROR));
    return response()->json(['saved' => true]);
});

Route::native('/native', App\NativeComponents\SqliteBenchmark::class);

// Shows the saved SuperNative report and logs it to logcat in the same chunk format as the WebView
// benchmark, so scripts/collect-release-logcat.ps1 can collect it from a non-debuggable release build.
Route::view('/native-report', 'native-report');
Route::get('/native-report.json', fn () => response()->file(storage_path('app/sqlite-benchmark-native-results.json')));
