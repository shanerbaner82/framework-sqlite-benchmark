// The same file is copied into both JavaScript apps by scripts/sync-runner.ps1.
const ROWS = 2000;
const WRITE_ROWS = 400;
const INSERT = 'INSERT INTO writes (id, category, score, title, payload) VALUES (?, ?, ?, ?, ?)';
const SEED = `WITH d(v) AS (VALUES(0),(1),(2),(3),(4),(5),(6),(7),(8),(9))
  INSERT INTO items (id, category, score, title, payload, metadata)
  SELECT n + 1, n % 100, n % 1000, printf('item-%04d', n + 1),
         printf('payload-%08d-abcdefghijklmnopqrstuvwxyz', n),
         json_object('tag', printf('tag-%d', n % 10))
  FROM (SELECT a.v + 10*b.v + 100*c.v + 1000*e.v AS n
        FROM d a CROSS JOIN d b CROSS JOIN d c CROSS JOIN d e)
  WHERE n < 2000`;

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());
const check = (ok, message) => { if (!ok) throw new Error(message); };
const scalar = async (db, sql, params = []) => {
  const rows = await db.rows(sql, params);
  return Number(Object.values(rows[0])[0]);
};
const resetWrites = async (db, count = 0) => {
  await db.exec('DELETE FROM writes');
  if (count) {
    await db.exec(`INSERT INTO writes (id, category, score, title, payload)
      SELECT id, category, score, title, payload FROM items WHERE id <= ${count}`);
  }
};
const rowArgs = i => [i, i % 100, i % 1000, `item-${i}`, `payload-${i}`];

const cases = [
  {
    name: 'schema_create_drop', ops: 30,
    run: async db => { for (let i = 0; i < 30; i++) { await db.exec('CREATE TABLE bench_ddl (id INTEGER PRIMARY KEY, value TEXT)'); await db.exec('DROP TABLE bench_ddl'); } },
  },
  {
    name: 'insert_autocommit', ops: WRITE_ROWS, setup: db => resetWrites(db),
    run: async db => { for (let i = 1; i <= WRITE_ROWS; i++) await db.exec(INSERT, rowArgs(i)); },
    verify: async db => check(await scalar(db, 'SELECT count(*) FROM writes') === WRITE_ROWS, 'insert count'),
  },
  {
    name: 'insert_transaction', ops: WRITE_ROWS, setup: db => resetWrites(db),
    run: db => db.transaction(async tx => { for (let i = 1; i <= WRITE_ROWS; i++) await tx.exec(INSERT, rowArgs(i)); }),
    verify: async db => check(await scalar(db, 'SELECT count(*) FROM writes') === WRITE_ROWS, 'transaction insert count'),
  },
  {
    name: 'point_select', ops: 400,
    run: async db => { for (let i = 0; i < 400; i++) { const id = (i * 37) % ROWS + 1; const r = await db.rows('SELECT id, title FROM items WHERE id = ?', [id]); check(Number(r[0]?.id) === id, 'point lookup'); } },
  },
  {
    name: 'indexed_filter', ops: 100,
    run: async db => { for (let i = 0; i < 100; i++) check((await db.rows('SELECT id, score FROM items WHERE category = ?', [i])).length === 20, 'indexed filter'); },
  },
  {
    name: 'range_scan', ops: 100,
    run: async db => { for (let i = 0; i < 100; i++) { const r = await db.rows('SELECT id, score FROM items WHERE score BETWEEN ? AND ? ORDER BY score', [i * 9, i * 9 + 9]); check(r.length >= 18, 'range scan'); } },
  },
  {
    name: 'full_scan_aggregate', ops: 40,
    run: async db => { for (let i = 0; i < 40; i++) check(await scalar(db, 'SELECT sum(score) FROM items') === 999000, 'aggregate'); },
  },
  {
    name: 'order_limit', ops: 100,
    run: async db => { for (let i = 0; i < 100; i++) { const r = await db.rows('SELECT id, score FROM items ORDER BY score DESC LIMIT 20 OFFSET ?', [i]); check(r.length === 20, 'order limit'); } },
  },
  {
    name: 'join_aggregate', ops: 100,
    run: async db => { for (let i = 0; i < 100; i++) check(await scalar(db, 'SELECT count(*) FROM items i JOIN events e ON e.item_id = i.id WHERE i.category = ?', [i]) === 20, 'join'); },
  },
  {
    name: 'like_search', ops: 50,
    run: async db => { for (let i = 0; i < 50; i++) check(await scalar(db, "SELECT count(*) FROM items WHERE title LIKE '%item-19%'") === 100, 'LIKE'); },
  },
  {
    name: 'json_extract', ops: 100,
    run: async db => { for (let i = 0; i < 100; i++) check(await scalar(db, "SELECT count(*) FROM items WHERE json_extract(metadata, '$.tag') = ?", [`tag-${i % 10}`]) === 200, 'JSON'); },
  },
  {
    name: 'update_by_pk', ops: WRITE_ROWS, setup: db => resetWrites(db, WRITE_ROWS),
    run: async db => { for (let i = 1; i <= WRITE_ROWS; i++) await db.exec('UPDATE writes SET score = score + 1 WHERE id = ?', [i]); },
    verify: async db => check(await scalar(db, 'SELECT count(*) FROM writes WHERE score = (id - 1) % 1000 + 1') === WRITE_ROWS, 'update'),
  },
  {
    name: 'delete_by_pk', ops: 200, setup: db => resetWrites(db, WRITE_ROWS),
    run: async db => { for (let i = 1; i <= 200; i++) await db.exec('DELETE FROM writes WHERE id = ?', [i]); },
    verify: async db => check(await scalar(db, 'SELECT count(*) FROM writes') === 200, 'delete'),
  },
  {
    name: 'upsert', ops: WRITE_ROWS, setup: db => resetWrites(db, 200),
    run: async db => { for (let i = 1; i <= WRITE_ROWS; i++) await db.exec(`${INSERT} ON CONFLICT(id) DO UPDATE SET score=excluded.score`, rowArgs(i)); },
    verify: async db => check(await scalar(db, 'SELECT count(*) FROM writes') === WRITE_ROWS, 'upsert'),
  },
  {
    name: 'transaction_rollback', ops: 50, setup: db => resetWrites(db),
    run: async db => { for (let i = 1; i <= 50; i++) { try { await db.transaction(async tx => { await tx.exec(INSERT, rowArgs(i)); throw new Error('rollback'); }); } catch (e) { if (e.message !== 'rollback') throw e; } } },
    verify: async db => check(await scalar(db, 'SELECT count(*) FROM writes') === 0, 'rollback'),
  },
  {
    name: 'blob_insert_length', ops: 100, setup: db => db.exec('DELETE FROM blobs'),
    run: async db => { for (let i = 1; i <= 100; i++) { await db.exec('INSERT INTO blobs (id, data) VALUES (?, zeroblob(4096))', [i]); check(await scalar(db, 'SELECT length(data) FROM blobs WHERE id = ?', [i]) === 4096, 'BLOB length'); } },
  },
  {
    name: 'index_create', ops: 1, setup: db => db.exec('DROP INDEX IF EXISTS bench_category_idx'),
    run: db => db.exec('CREATE INDEX bench_category_idx ON items(category)'),
    verify: async db => check(await scalar(db, "SELECT count(*) FROM sqlite_master WHERE type='index' AND name='bench_category_idx'") === 1, 'index'),
  },
];

// trace (optional): { begin(name), end() } -> android.os.Trace sections named `case:<name>` around
// each TIMED sample only (not the warmup), outside the per-query loop. Read by Macrobenchmark.
export async function runBenchmark(db, onProgress = (_name) => {}, sampleCount = 5, trace = null) {
  await db.exec('PRAGMA journal_mode=WAL');
  await db.exec('PRAGMA synchronous=FULL');
  await db.exec('PRAGMA foreign_keys=ON');
  await db.exec('DROP TABLE IF EXISTS events');
  await db.exec('DROP TABLE IF EXISTS items');
  await db.exec('DROP TABLE IF EXISTS writes');
  await db.exec('DROP TABLE IF EXISTS blobs');
  await db.exec('CREATE TABLE items (id INTEGER PRIMARY KEY, category INTEGER NOT NULL, score INTEGER NOT NULL, title TEXT NOT NULL, payload TEXT NOT NULL, metadata TEXT NOT NULL)');
  await db.exec('CREATE INDEX items_category_idx ON items(category)');
  await db.exec('CREATE INDEX items_score_idx ON items(score)');
  await db.exec('CREATE TABLE events (id INTEGER PRIMARY KEY, item_id INTEGER NOT NULL, kind INTEGER NOT NULL)');
  await db.exec('CREATE INDEX events_item_idx ON events(item_id)');
  await db.exec('CREATE TABLE writes (id INTEGER PRIMARY KEY, category INTEGER, score INTEGER, title TEXT, payload BLOB)');
  await db.exec('CREATE TABLE blobs (id INTEGER PRIMARY KEY, data BLOB)');
  await db.exec(SEED);
  await db.exec('INSERT INTO events (id, item_id, kind) SELECT id, id, id % 5 FROM items');
  check(await scalar(db, 'SELECT count(*) FROM items') === ROWS, 'fixture count');
  const metadata = {
    sqlite_version: (await db.rows('SELECT sqlite_version() AS v'))[0].v,
    journal_mode: (await db.rows('PRAGMA journal_mode'))[0].journal_mode,
    synchronous: (await db.rows('PRAGMA synchronous'))[0].synchronous,
    fixture_rows: ROWS,
    warmups: 1,
    samples: sampleCount,
  };
  const results = [];
  for (const c of cases) {
    onProgress(c.name);
    const samples = [];
    try {
      for (let repeat = -1; repeat < sampleCount; repeat++) {
        if (c.setup) await c.setup(db);
        const traced = trace && repeat >= 0;
        if (traced) trace.begin('case:' + c.name);
        let elapsed;
        const start = now();
        try {
          await c.run(db);
          elapsed = now() - start;
        } finally {
          if (traced) trace.end();
        }
        if (c.verify) await c.verify(db);
        if (repeat >= 0) samples.push(elapsed);
      }
      const ordered = [...samples].sort((a, b) => a - b);
      const median = ordered[Math.floor(ordered.length / 2)];
      results.push({ name: c.name, ops: c.ops, samples_ms: samples, median_ms: median, p95_ms: ordered[Math.ceil(0.95 * ordered.length) - 1], ops_per_second: Math.round(c.ops * 1000 / median), status: 'ok' });
    } catch (e) {
      results.push({ name: c.name, ops: c.ops, samples_ms: samples, status: 'error', error: String(e) });
    }
  }
  metadata.integrity_check = (await db.rows('PRAGMA integrity_check'))[0].integrity_check;
  return { benchmark_version: 1, metadata, results };
}
