<!doctype html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>SQLite benchmark · NativePHP</title>
    <style>
        body { font: 16px system-ui, sans-serif; margin: 20px; color: #17202a; }
        button { font: inherit; padding: 10px 16px; margin: 8px 8px 8px 0; }
        td { border-bottom: 1px solid #ddd; padding: 6px; }
        table { border-collapse: collapse; width: 100%; font-size: 14px; }
        pre { overflow-wrap: anywhere; white-space: pre-wrap; font-size: 11px; }
    </style>
</head>
<body>
    <h2>SQLite benchmark · NativePHP</h2>
    <p>2,000 fixture rows · 17 cases · 1 warmup + 5 samples</p>
    <button id="run">Run PHP loop</button><button id="run-laravel">PHP loop Laravel DB</button><button id="run-ui">Run per-query UI benchmark</button><button id="download" hidden>Download JSON</button>
    <p id="status">Ready</p>
    <table id="results"></table>
    <pre id="json"></pre>
    <script type="module">
        import { runBenchmark } from '/benchmark/runner.js';

        let report;
        const csrf = document.querySelector('meta[name="csrf-token"]').content;
        const post = async (url, body) => {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'X-CSRF-TOKEN': csrf, 'Accept': 'application/json', 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!response.ok) throw new Error(`${url}: ${response.status} ${await response.text()}`);
            return response.json();
        };
        const db = {
            exec: async (sql, params = []) => { await post('/sql', { action: 'exec', sql, params }); },
            rows: async (sql, params = []) => (await post('/sql', { action: 'rows', sql, params })).rows,
            transaction: async fn => {
                await post('/sql', { action: 'begin' });
                try {
                    const result = await fn({ exec: db.exec });
                    await post('/sql', { action: 'commit' });
                    return result;
                } catch (error) {
                    await post('/sql', { action: 'rollback' });
                    throw error;
                }
            },
        };
        const show = result => {
            report = result;
            document.getElementById('status').textContent = `Complete · ${result.driver} · SQLite ${result.metadata.sqlite_version} · integrity ${result.metadata.integrity_check}`;
            document.getElementById('results').innerHTML = result.results.map(r => `<tr><td>${r.name}</td><td>${r.status === 'ok' ? r.median_ms.toFixed(2) + ' ms · ' + r.ops_per_second + ' ops/s' : 'ERROR ' + r.error}</td></tr>`).join('');
            document.getElementById('json').textContent = JSON.stringify(result, null, 2);
            document.getElementById('download').hidden = false;
            const json = JSON.stringify(result);
            const runId = Date.now();
            const chunks = Math.ceil(json.length / 900);
            for (let i = 0; i < chunks; i++) console.log(`SQLITE_BENCHMARK_PART ${runId} ${i + 1}/${chunks} ${json.slice(i * 900, (i + 1) * 900)}`);
            console.log(`SQLITE_BENCHMARK_DONE ${runId}`);
        };
        const run = async mode => {
            document.querySelectorAll('button').forEach(b => b.disabled = true);
            document.getElementById('status').textContent = 'Running benchmark…';
            document.getElementById('results').innerHTML = '';
            document.getElementById('download').hidden = true;
            try {
                if (mode === 'ui') {
                    const result = await runBenchmark(db, name => { document.getElementById('status').textContent = `Running ${name}`; });
                    const completed = { framework: 'NativePHP WebView', driver: 'per-query fetch to Laravel SQLite PDO', ...result };
                    await post('/report', completed);
                    show(completed);
                } else show(await post('/run', mode));
            } catch (error) {
                document.getElementById('status').textContent = String(error);
            } finally {
                document.querySelectorAll('button').forEach(b => b.disabled = false);
            }
        };
        document.getElementById('run').onclick = () => run({ api: 'pdo' });
        document.getElementById('run-laravel').onclick = () => run({ api: 'laravel' });
        document.getElementById('run-ui').onclick = () => run('ui');
        document.getElementById('download').onclick = () => {
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
            a.download = 'nativephp-sqlite-benchmark.json';
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        };
    </script>
</body>
</html>
