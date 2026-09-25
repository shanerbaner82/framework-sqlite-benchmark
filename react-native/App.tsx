import React, { useState } from 'react';
import { Button, NativeModules, ScrollView, Share, StatusBar, StyleSheet, Text, View } from 'react-native';
import { openBenchmarkDatabase } from './benchmark/database';
import { runBenchmark } from './benchmark/runner';

export default function App() {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('Ready');
  const [report, setReport] = useState<any>(null);

  const run = async () => {
    setBusy(true);
    setReport(null);
    const db = openBenchmarkDatabase();
    try {
      // android.os.Trace sections (case:<name>) on the JS thread for Macrobenchmark's TraceSectionMetric.
      const trace = NativeModules.BenchTrace ? { begin: (n: string) => NativeModules.BenchTrace.beginSection(n), end: () => NativeModules.BenchTrace.endSection() } : null;
      const result = await runBenchmark(db, (name: string) => setStatus(`Running ${name}`), 5, trace);
      const completed = { framework: 'React Native', driver: 'react-native-nitro-sqlite', ...result };
      const json = JSON.stringify(completed);
      const runId = Date.now();
      const chunks = Math.ceil(json.length / 900);
      for (let i = 0; i < chunks; i++) console.log(`SQLITE_BENCHMARK_PART ${runId} ${i + 1}/${chunks} ${json.slice(i * 900, (i + 1) * 900)}`);
      console.log(`SQLITE_BENCHMARK_DONE ${runId}`);
      setReport(completed);
      setStatus('Complete');
    } catch (error) {
      setStatus(String(error));
    } finally {
      db.close();
      setBusy(false);
    }
  };

  return <View style={styles.page}>
    <StatusBar barStyle="dark-content" />
    <Text style={styles.title}>SQLite benchmark · React Native</Text>
    <Text>2,000 fixture rows · 17 cases · 1 warmup + 5 samples</Text>
    <Button title={busy ? 'Running…' : 'Run benchmark'} onPress={run} disabled={busy} />
    <Text accessibilityLabel="benchmark-status">{status}</Text>
    {report && <Button title="Share JSON results" onPress={() => Share.share({ message: JSON.stringify(report, null, 2) })} />}
    <ScrollView>
      {report?.results.map((r: any) => <Text key={r.name} style={styles.row}>
        {r.name}: {r.status === 'ok' ? `${r.median_ms.toFixed(2)} ms · ${r.ops_per_second} ops/s` : `ERROR ${r.error}`}
      </Text>)}
      {report && <Text selectable style={styles.json}>{JSON.stringify(report, null, 2)}</Text>}
    </ScrollView>
  </View>;
}

const styles = StyleSheet.create({
  page: { flex: 1, padding: 20, paddingTop: 48, gap: 12, backgroundColor: '#fff' },
  title: { fontSize: 22, fontWeight: '700' },
  row: { paddingVertical: 6, borderBottomWidth: 1, borderColor: '#ddd' },
  json: { fontFamily: 'monospace', fontSize: 11, marginTop: 16 },
});
