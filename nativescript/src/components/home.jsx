import { createSignal } from 'solid-js';
import { File, knownFolders } from '@nativescript/core';
import { openDatabase } from '@edusperoni/nativescript-sqlite';
import { runBenchmark } from '../benchmark/runner';

export default function Home() {
  const [busy, setBusy] = createSignal(false);
  const [status, setStatus] = createSignal('Ready');
  const [summary, setSummary] = createSignal('');

  async function run() {
    setBusy(true);
    setSummary('');
    const db = openDatabase({ path: knownFolders.documents().path + '/sqlite-benchmark.sqlite' });
    const adapter = {
      exec: (sql, params = []) => db.execute(sql, params),
      rows: (sql, params = []) => db.select(sql, params),
      transaction: fn => db.transaction(tx => fn({ exec: (sql, params = []) => tx.execute(sql, params) })),
    };
    try {
      // android.os.Trace sections (case:<name>) for Macrobenchmark's TraceSectionMetric; JS runs on the main thread here.
      const trace = { begin: name => android.os.Trace.beginSection(name), end: () => android.os.Trace.endSection() };
      const result = await runBenchmark(adapter, setStatus, 5, trace);
      const report = { framework: 'NativeScript SolidJS', driver: '@edusperoni/nativescript-sqlite', ...result };
      const output = knownFolders.documents().path + '/sqlite-benchmark-results.json';
      await File.fromPath(output).writeText(JSON.stringify(report, null, 2));
      console.log('SQLITE_BENCHMARK_READY ' + output);
      const json = JSON.stringify(report);
      const runId = Date.now();
      const chunks = Math.ceil(json.length / 900);
      for (let i = 0; i < chunks; i++) console.log(`SQLITE_BENCHMARK_PART ${runId} ${i + 1}/${chunks} ${json.slice(i * 900, (i + 1) * 900)}`);
      console.log(`SQLITE_BENCHMARK_DONE ${runId}`);
      setSummary(result.results.map(r => r.status === 'ok' ? `${r.name}: ${r.median_ms.toFixed(2)} ms · ${r.ops_per_second} ops/s` : `${r.name}: ERROR ${r.error}`).join('\n'));
      setStatus('Complete · JSON saved to app documents');
    } catch (error) {
      setStatus(String(error));
    } finally {
      await db.close();
      setBusy(false);
    }
  }

  return <>
    <actionbar title="SQLite benchmark · NativeScript" />
    <stacklayout padding="16">
      <label text="2,000 fixture rows · 17 cases · 1 warmup + 5 samples" textWrap="true" />
      <button text={busy() ? 'Running…' : 'Run benchmark'} isEnabled={!busy()} on:tap={run} />
      <label text={status()} textWrap="true" />
      <scrollview height="80%"><label text={summary()} textWrap="true" /></scrollview>
    </stacklayout>
  </>;
}
