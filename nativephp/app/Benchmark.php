<?php

namespace App;

use Generator;
use Illuminate\Database\Connection;
use PDO;
use RuntimeException;
use Throwable;

final class Benchmark
{
    private const ROWS = 2000;
    private const WRITE_ROWS = 400;
    private const INSERT = 'INSERT INTO writes (id, category, score, title, payload) VALUES (?, ?, ?, ?, ?)';

    /**
     * $db is the raw PDO handle.
     * When $connection is given, every call goes through Laravel's DB connection
     * (statement()/select()/beginTransaction()) instead of the raw handle: same SQL, same counts.
     */
    public function __construct(private object $db, private ?Connection $connection = null) {}

    /** Optional object with begin(string)/end(): android.os.Trace `case:<name>` sections around each timed sample (Macrobenchmark). */
    public ?object $tracer = null;

    private function exec(string $sql, array $params = []): void
    {
        if ($this->connection) {
            $this->connection->statement($sql, $params);
            return;
        }
        $statement = $this->db->prepare($sql);
        $statement->execute($params);
        $statement->closeCursor();
    }

    private function rows(string $sql, array $params = []): array
    {
        if ($this->connection) {
            return array_map(fn ($row) => (array) $row, $this->connection->select($sql, $params));
        }
        $statement = $this->db->prepare($sql);
        $statement->execute($params);
        return $statement->fetchAll(PDO::FETCH_ASSOC);
    }

    private function scalar(string $sql, array $params = []): int
    {
        return (int) array_values($this->rows($sql, $params)[0])[0];
    }

    private function check(bool $condition, string $message): void
    {
        if (!$condition) throw new RuntimeException($message);
    }

    private function args(int $i): array
    {
        return [$i, $i % 100, $i % 1000, "item-$i", "payload-$i"];
    }

    private function resetWrites(int $count = 0): void
    {
        $this->exec('DELETE FROM writes');
        if ($count) $this->exec("INSERT INTO writes (id, category, score, title, payload) SELECT id, category, score, title, payload FROM items WHERE id <= $count");
    }

    /** Timed case bodies are generators that yield after every SQL call, so a driver can interleave each call with a UI round-trip. */
    private function transaction(callable $callback): Generator
    {
        $tx = $this->connection ?? $this->db;
        $tx->beginTransaction();
        yield;
        try {
            yield from $callback();
            $tx->commit();
            yield;
        } catch (Throwable $e) {
            $tx->rollBack();
            yield;
            throw $e;
        }
    }

    public function prepare(): array
    {
        $this->exec('PRAGMA journal_mode=WAL');
        $this->exec('PRAGMA synchronous=FULL');
        $this->exec('PRAGMA foreign_keys=ON');
        foreach (['events', 'items', 'writes', 'blobs'] as $table) $this->exec("DROP TABLE IF EXISTS $table");
        $this->exec('CREATE TABLE items (id INTEGER PRIMARY KEY, category INTEGER NOT NULL, score INTEGER NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL, metadata TEXT NOT NULL)');
        $this->exec('CREATE INDEX items_category_idx ON items(category)');
        $this->exec('CREATE INDEX items_score_idx ON items(score)');
        $this->exec('CREATE TABLE events (id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL, kind INTEGER NOT NULL)');
        $this->exec('CREATE INDEX events_item_idx ON events(item_id)');
        $this->exec('CREATE TABLE writes (id INTEGER PRIMARY KEY, category INTEGER, score INTEGER, title TEXT, payload BLOB)');
        $this->exec('CREATE TABLE blobs (id INTEGER PRIMARY KEY, data BLOB)');
        $this->exec(<<<'SQL'
            WITH d(v) AS (VALUES(0),(1),(2),(3),(4),(5),(6),(7),(8),(9))
            INSERT INTO items (id, category, score, title, payload, metadata)
            SELECT n + 1, n % 100, n % 1000, printf('item-%04d', n + 1),
                   printf('payload-%08d-abcdefghijklmnopqrstuvwxyz', n),
                   json_object('tag', printf('tag-%d', n % 10))
            FROM (SELECT a.v + 10*b.v + 100*c.v + 1000*e.v AS n
                  FROM d a CROSS JOIN d b CROSS JOIN d c CROSS JOIN d e)
            WHERE n < 2000
            SQL);
        $this->exec('INSERT INTO events (id, item_id, kind) SELECT id, id, id % 5 FROM items');
        $this->check($this->scalar('SELECT count(*) FROM items') === self::ROWS, 'fixture count');
        return [
            'sqlite_version' => $this->rows('SELECT sqlite_version() AS v')[0]['v'],
            'journal_mode' => $this->rows('PRAGMA journal_mode')[0]['journal_mode'],
            'synchronous' => (int) $this->rows('PRAGMA synchronous')[0]['synchronous'],
            'fixture_rows' => self::ROWS,
            'warmups' => 1,
            'samples' => 5,
        ];
    }

    public function cases(): array
    {
        return [
            ['schema_create_drop', 30, null, function () { for ($i = 0; $i < 30; $i++) { $this->exec('CREATE TABLE bench_ddl (id INTEGER PRIMARY KEY, value TEXT)'); yield; $this->exec('DROP TABLE bench_ddl'); yield; } }],
            ['insert_autocommit', 400, fn () => $this->resetWrites(), function () { for ($i = 1; $i <= 400; $i++) { $this->exec(self::INSERT, $this->args($i)); yield; } }, fn () => $this->check($this->scalar('SELECT count(*) FROM writes') === 400, 'insert count')],
            ['insert_transaction', 400, fn () => $this->resetWrites(), fn () => $this->transaction(function () { for ($i = 1; $i <= 400; $i++) { $this->exec(self::INSERT, $this->args($i)); yield; } }), fn () => $this->check($this->scalar('SELECT count(*) FROM writes') === 400, 'transaction insert count')],
            ['point_select', 400, null, function () { for ($i = 0; $i < 400; $i++) { $id = ($i * 37) % self::ROWS + 1; $this->check((int) $this->rows('SELECT id, title FROM items WHERE id = ?', [$id])[0]['id'] === $id, 'point lookup'); yield; } }],
            ['indexed_filter', 100, null, function () { for ($i = 0; $i < 100; $i++) { $this->check(count($this->rows('SELECT id, score FROM items WHERE category = ?', [$i])) === 20, 'indexed filter'); yield; } }],
            ['range_scan', 100, null, function () { for ($i = 0; $i < 100; $i++) { $this->check(count($this->rows('SELECT id, score FROM items WHERE score BETWEEN ? AND ? ORDER BY score', [$i * 9, $i * 9 + 9])) >= 18, 'range scan'); yield; } }],
            ['full_scan_aggregate', 40, null, function () { for ($i = 0; $i < 40; $i++) { $this->check($this->scalar('SELECT sum(score) FROM items') === 999000, 'aggregate'); yield; } }],
            ['order_limit', 100, null, function () { for ($i = 0; $i < 100; $i++) { $this->check(count($this->rows('SELECT id, score FROM items ORDER BY score DESC LIMIT 20 OFFSET ?', [$i])) === 20, 'order limit'); yield; } }],
            ['join_aggregate', 100, null, function () { for ($i = 0; $i < 100; $i++) { $this->check($this->scalar('SELECT count(*) FROM items i JOIN events e ON e.item_id = i.id WHERE i.category = ?', [$i]) === 20, 'join'); yield; } }],
            ['like_search', 50, null, function () { for ($i = 0; $i < 50; $i++) { $this->check($this->scalar("SELECT count(*) FROM items WHERE title LIKE '%item-19%'") === 100, 'LIKE'); yield; } }],
            ['json_extract', 100, null, function () { for ($i = 0; $i < 100; $i++) { $this->check($this->scalar("SELECT count(*) FROM items WHERE json_extract(metadata, '$.tag') = ?", ['tag-'.($i % 10)]) === 200, 'JSON'); yield; } }],
            ['update_by_pk', 400, fn () => $this->resetWrites(400), function () { for ($i = 1; $i <= 400; $i++) { $this->exec('UPDATE writes SET score = score + 1 WHERE id = ?', [$i]); yield; } }, fn () => $this->check($this->scalar('SELECT count(*) FROM writes WHERE score = (id - 1) % 1000 + 1') === 400, 'update')],
            ['delete_by_pk', 200, fn () => $this->resetWrites(400), function () { for ($i = 1; $i <= 200; $i++) { $this->exec('DELETE FROM writes WHERE id = ?', [$i]); yield; } }, fn () => $this->check($this->scalar('SELECT count(*) FROM writes') === 200, 'delete')],
            ['upsert', 400, fn () => $this->resetWrites(200), function () { for ($i = 1; $i <= 400; $i++) { $this->exec(self::INSERT.' ON CONFLICT(id) DO UPDATE SET score=excluded.score', $this->args($i)); yield; } }, fn () => $this->check($this->scalar('SELECT count(*) FROM writes') === 400, 'upsert')],
            ['transaction_rollback', 50, fn () => $this->resetWrites(), function () { for ($i = 1; $i <= 50; $i++) { try { yield from $this->transaction(function () use ($i) { $this->exec(self::INSERT, $this->args($i)); yield; throw new RuntimeException('rollback'); }); } catch (RuntimeException $e) { if ($e->getMessage() !== 'rollback') throw $e; } } }, fn () => $this->check($this->scalar('SELECT count(*) FROM writes') === 0, 'rollback')],
            ['blob_insert_length', 100, fn () => $this->exec('DELETE FROM blobs'), function () { for ($i = 1; $i <= 100; $i++) { $this->exec('INSERT INTO blobs (id, data) VALUES (?, zeroblob(4096))', [$i]); yield; $this->check($this->scalar('SELECT length(data) FROM blobs WHERE id = ?', [$i]) === 4096, 'BLOB length'); yield; } }],
            ['index_create', 1, fn () => $this->exec('DROP INDEX IF EXISTS bench_category_idx'), function () { $this->exec('CREATE INDEX bench_category_idx ON items(category)'); yield; }, fn () => $this->check($this->scalar("SELECT count(*) FROM sqlite_master WHERE type='index' AND name='bench_category_idx'") === 1, 'index')],
        ];
    }

    /**
     * Runs one case, yielding after every SQL call inside the timed body.
     * The case timer spans the whole sample, so a driver that suspends the
     * generator between calls includes its round-trip cost in the sample.
     * The result row is the generator's return value.
     */
    public function steps(array $case): Generator
    {
        [$name, $ops, $setup, $body, $verify] = array_pad($case, 5, null);
        $samples = [];
        try {
            for ($repeat = -1; $repeat < 5; $repeat++) {
                if ($setup) $setup();
                $traced = $this->tracer && $repeat >= 0;
                if ($traced) $this->tracer->begin("case:$name");
                $start = hrtime(true);
                try {
                    yield from $body();
                    $elapsed = (hrtime(true) - $start) / 1_000_000;
                } finally {
                    if ($traced) $this->tracer->end();
                }
                if ($verify) $verify();
                if ($repeat >= 0) $samples[] = $elapsed;
            }
            $ordered = $samples;
            sort($ordered);
            $median = $ordered[intdiv(count($ordered), 2)];
            return ['name' => $name, 'ops' => $ops, 'samples_ms' => $samples, 'median_ms' => $median, 'p95_ms' => $ordered[(int) ceil(.95 * count($ordered)) - 1], 'ops_per_second' => (int) round($ops * 1000 / $median), 'status' => 'ok'];
        } catch (Throwable $e) {
            return ['name' => $name, 'ops' => $ops, 'samples_ms' => $samples, 'status' => 'error', 'error' => $e->getMessage()];
        }
    }

    public function runCase(array $case): array
    {
        $steps = $this->steps($case);
        foreach ($steps as $_);
        return $steps->getReturn();
    }

    public function integrityCheck(): string
    {
        return $this->rows('PRAGMA integrity_check')[0]['integrity_check'];
    }

    public function report(array $metadata, array $results, string $driver = 'Laravel SQLite PDO'): array
    {
        $metadata['integrity_check'] = $this->integrityCheck();
        return ['framework' => 'NativePHP', 'driver' => $driver, 'benchmark_version' => 1, 'metadata' => $metadata, 'results' => $results];
    }

    public function run(): array
    {
        $metadata = $this->prepare();
        $results = array_map(fn ($case) => $this->runCase($case), $this->cases());
        return $this->report($metadata, $results);
    }
}
