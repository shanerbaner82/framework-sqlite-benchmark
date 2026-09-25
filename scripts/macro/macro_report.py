#!/usr/bin/env python3
"""Summarise a Macrobenchmark run: scripts/macro/macro_report.py results/pixel9/macro/<RUN_TAG>
Writes <dir>/summary.md and <dir>/summary.json and prints the markdown."""
import glob, json, os, re, statistics as st, sys
D = sys.argv[1].rstrip('/')
TESTS = [('nativescript', 'NativeScript (release)', 'NS'), ('reactnative', 'React Native (release)', 'RN'),
         ('nativephpPdo', 'NativePHP PHP loop · pdo_sqlite · raw PDO', 'PHP pdo'),
         ('nativephpLaravel', 'NativePHP PHP loop · pdo_sqlite · Laravel DB', 'PHP pdo+Laravel'),
]
CASES = ["schema_create_drop", "insert_autocommit", "insert_transaction", "point_select", "indexed_filter", "range_scan",
         "full_scan_aggregate", "order_limit", "join_aggregate", "like_search", "json_extract", "update_by_pk", "delete_by_pk",
         "upsert", "transaction_rollback", "blob_insert_length", "index_create"]
apps = []
for t, label, short in TESTS:
    f = f'{D}/{t}/com.sqlitebenchmark.macro-benchmarkData.json'
    if not os.path.exists(f): continue
    mb = json.load(open(f))
    b = mb['benchmarks'][0]; m = b['metrics']
    inapp = [json.load(open(x, encoding='utf-8-sig')) for x in sorted(glob.glob(f'{D}/{t}/inapp-*.json'), key=lambda x: int(re.search(r'iter(\d+)', x).group(1)))]
    for r in inapp:
        assert r['metadata']['integrity_check'] == 'ok' and len(r['results']) == 17 and all(x['status'] == 'ok' for x in r['results']), (t, 'in-app report failed')
    counts = {c: m[f'case_{c}_countCount']['runs'] for c in CASES}
    assert all(all(v == 5 for v in counts[c]) for c in CASES), (t, 'missing trace sections', counts)
    a = dict(test=t, label=label, short=short, ctx=mb['context'], iterations=len(m['timeToInitialDisplayMs']['runs']),
             trace_runs={c: m[f'case_{c}_avgAverageMs']['runs'] for c in CASES},
             ttid=m['timeToInitialDisplayMs']['runs'], ttfd=m.get('timeToFullDisplayMs', {}).get('runs'),
             inapp_runs={c: [next(x for x in r['results'] if x['name'] == c)['median_ms'] for r in inapp] for c in CASES},
             inapp=inapp)
    a['trace'] = {c: st.median(v) for c, v in a['trace_runs'].items()}
    a['inapp_med'] = {c: st.median(v) for c, v in a['inapp_runs'].items()} if inapp else {}
    a['trace_totals'] = [sum(a['trace_runs'][c][i] for c in CASES) for i in range(a['iterations'])]
    a['inapp_totals'] = [sum(a['inapp_runs'][c][i] for c in CASES) for i in range(len(inapp))]
    apps.append(a)
if not apps: sys.exit('no data')
ops = {r['name']: r['ops'] for r in apps[0]['inapp'][0]['results']}
base = next((a for a in apps if a['short'] == 'NS'), apps[0])
f3 = lambda v: f'{v:,.3f}'
dl = lambda v, b: f'{(v / b - 1) * 100:+,.1f}%'

def table(key, totals_key, title_extra=''):
    out = ['| Case (ops) | ' + ' | '.join(a['short'] + ('' if a is base else f" | {a['short']} Δ") for a in apps) + ' |',
           '| --- | ' + ' | '.join('---:' if a is base else '---: | ---:' for a in apps) + ' |']
    for c in CASES:
        cells = []
        for a in apps:
            cells.append(f3(a[key][c]))
            if a is not base: cells.append(dl(a[key][c], base[key][c]))
        out.append(f'| {c} ({ops[c]}) | ' + ' | '.join(cells) + ' |')
    cells = []
    for a in apps:
        v = st.median(a[totals_key]); cells.append(f'**{f3(v)}**')
        if a is not base: cells.append(dl(v, st.median(base[totals_key])))
    out.append('| **Sum of 17 cases** | ' + ' | '.join(cells) + ' |')
    return out

md = []
md.append(f"### A. Macrobenchmark TraceSectionMetric (ms per timed sample; median of {apps[0]['iterations']} iterations)")
md.append('')
md += table('trace', 'trace_totals')
cells = []
for a in apps:
    v = st.median(a['ttid']); cells.append(f3(v))
    if a is not base: cells.append(dl(v, st.median(base['ttid'])))
md.append('| *Cold start timeToInitialDisplay* | ' + ' | '.join(cells) + ' |')
if any(a['ttfd'] for a in apps):
    md.append('| *Cold start timeToFullDisplay* | ' + ' | '.join((f3(st.median(a['ttfd'])) if a['ttfd'] else 'n/a') + ('' if a is base else ' | ') for a in apps) + ' |')
md.append('')
md.append('### B. In-app timers from the same iterations (median of 5 samples per run; median over runs)')
md.append('')
md += table('inapp_med', 'inapp_totals')
md.append('')
md.append('### C. Per-call cost (trace median ÷ ops, ms per SQL call)')
md.append('')
key = ['point_select', 'insert_transaction', 'insert_autocommit', 'update_by_pk', 'indexed_filter', 'transaction_rollback', 'json_extract']
md.append('| Case | ' + ' | '.join(a['short'] for a in apps) + ' |')
md.append('| --- | ' + ' | '.join('---:' for a in apps) + ' |')
for c in key:
    md.append(f'| {c} | ' + ' | '.join(f"{a['trace'][c] / ops[c]:.4f}" for a in apps) + ' |')
md.append('')
md.append('### D. Run-to-run spread (sum of the 17 per-case values, per iteration)')
md.append('')
md.append('| App/mode | iterations | trace sum per iteration (ms) | spread (max-min)/median | CV | in-app sum per iteration (ms) | worst case CV (trace) |')
md.append('| --- | ---: | --- | ---: | ---: | --- | --- |')
for a in apps:
    t = a['trace_totals']; m_ = st.median(t)
    cv = st.pstdev(t) / st.mean(t) * 100
    worst = max(CASES, key=lambda c: st.pstdev(a['trace_runs'][c]) / st.mean(a['trace_runs'][c]))
    wcv = st.pstdev(a['trace_runs'][worst]) / st.mean(a['trace_runs'][worst]) * 100
    md.append(f"| {a['label']} | {len(t)} | {', '.join(f'{x:,.1f}' for x in t)} | {(max(t) - min(t)) / m_ * 100:.1f}% | {cv:.1f}% | {', '.join(f'{x:,.1f}' for x in a['inapp_totals'])} | {worst} {wcv:.0f}% |")
md.append('')
md.append('### E. Reported SQLite metadata')
md.append('')
md.append('| App/mode | driver | SQLite | journal_mode | synchronous | integrity_check | extra |')
md.append('| --- | --- | --- | --- | --- | --- | --- |')
for a in apps:
    r = a['inapp'][0]; m_ = r['metadata']
    extra = ', '.join(f'{k}={m_[k]}' for k in ('handle_class', 'connection_driver', 'database_file', 'nativephp_mobile', 'php') if k in m_)
    ic = sorted({x['metadata']['integrity_check'] for x in a['inapp']})
    md.append(f"| {a['label']} | {r.get('driver', '')} | {m_['sqlite_version']} | {m_['journal_mode']} | {m_['synchronous']} | {','.join(ic)} ({len(a['inapp'])}/{len(a['inapp'])}) | {extra} |")
c = apps[0]['ctx']
md.append('')
md.append(f"Macrobenchmark context: {c['build']['model']} ({c['build']['device']}), {c['build']['fingerprint']}, cpuCoreCount={c['cpuCoreCount']}, cpuLocked={c['cpuLocked']}, cpuMaxFreqHz={c['cpuMaxFreqHz']}, sustainedPerformanceMode={c['sustainedPerformanceModeEnabled']}.")
out = '\n'.join(md)
open(f'{D}/summary.md', 'w').write(out + '\n')
json.dump({a['label']: {k: a[k] for k in ('test', 'iterations', 'trace', 'trace_runs', 'inapp_med', 'inapp_runs', 'ttid', 'ttfd', 'trace_totals', 'inapp_totals')} for a in apps}, open(f'{D}/summary.json', 'w'), indent=1)
print(out)
