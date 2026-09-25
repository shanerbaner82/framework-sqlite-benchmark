<?php

require __DIR__.'/vendor/autoload.php';
$app = require __DIR__.'/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
// usage: php benchmark-cli.php [pdo|laravel]   -- raw PDO handle, or Laravel's DB connection
$api = $argv[1] ?? 'pdo';
$connection = Illuminate\Support\Facades\DB::connection();
if (! file_exists($file = config('database.connections.'.$connection->getName().'.database'))) touch($file);
echo json_encode((new App\Benchmark($connection->getPdo(), $api === 'laravel' ? $connection : null))->run(), JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR), PHP_EOL;
