#!/usr/bin/env python3
"""Aggregate results/pixel9/APP-MODE-runN.json into markdown tables (printed to stdout and
written to results/pixel9/summary.md + summary.json).
Per case: median over runs of each run's per-case median (each run median = 5 samples after 1 warmup)."""
import glob, json, os, re, statistics as st, sys
os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))
D = 'results/pixel9'
ORDER = [('ns', 'default', 'NativeScript'), ('rn', 'default', 'React Native'),
         ('nativephp', 'pdo', 'NativePHP PHP loop · pdo_sqlite · raw PDO'),
         ('nativephp', 'laravel', 'NativePHP PHP loop · pdo_sqlite · Laravel DB'),
         ('nativephp', 'ui', 'NativePHP per-query WebView'), ('nativephp', 'supernative', 'NativePHP SuperNative')]
SHORT = {'NativeScript': 'NS', 'React Native': 'RN', 'NativePHP PHP loop · pdo_sqlite · raw PDO': 'PHP PDO',
         'NativePHP PHP loop · pdo_sqlite · Laravel DB': 'PHP PDO+Laravel',          'NativePHP per-query WebView': 'PHP per-query', 'NativePHP SuperNative': 'SuperNative'}
apps = []
for app, mode, label in ORDER:
    files = sorted(glob.glob(f'{D}/{app}-{mode}-run*.json'), key=lambda f: int(re.search(r'run(\d+)', f).group(1)))
    if not files: continue
    runs = [json.load(open(f, encoding='utf-8-sig')) for f in files]
    for r in runs:
        assert r['metadata']['integrity_check'] == 'ok' and len(r['results']) == 17 and all(x['status'] == 'ok' for x in r['results']), f
    apps.append(dict(label=label, short=SHORT[label], runs=runs, files=files))
if not apps: sys.exit('no results')
cases = [r['name'] for r in apps[0]['runs'][0]['results']]
ops = {r['name']: r['ops'] for r in apps[0]['runs'][0]['results']}
for a in apps:
    a['per_run'] = {c: [next(x for x in run['results'] if x['name'] == c)['median_ms'] for run in a['runs']] for c in cases}
    a['med'] = {c: st.median(v) for c, v in a['per_run'].items()}
    a['totals'] = [sum(next(x for x in run['results'] if x['name'] == c)['median_ms'] for c in cases) for run in a['runs']]
base = next((a for a in apps if a['short'] == 'NS'), apps[0])
fmt = lambda v: f'{v:,.3f}'
delta = lambda v, b: f'{(v / b - 1) * 100:+,.1f}%'
out = []
out.append('| Case | ' + ' | '.join(f"{a['short']} (n={len(a['runs'])})" + ('' if a is base else f" | {a['short']} Δ") for a in apps) + ' |')
out.append('| --- | ' + ' | '.join('---:' if a is base else '---: | ---:' for a in apps) + ' |')
for c in cases:
    cells = []
    for a in apps:
        cells.append(fmt(a['med'][c]))
        if a is not base: cells.append(delta(a['med'][c], base['med'][c]))
    out.append(f'| {c} ({ops[c]}) | ' + ' | '.join(cells) + ' |')
cells = []
for a in apps:
    t = st.median(a['totals']); cells.append(fmt(t))
    if a is not base: cells.append(delta(t, st.median(base['totals'])))
out.append('| **Sum of case medians** | ' + ' | '.join(cells) + ' |')
out.append('')
out.append('Per-call cost (case median ÷ operations, ms/op):')
out.append('')
key = ['point_select', 'insert_transaction', 'insert_autocommit', 'update_by_pk', 'indexed_filter', 'json_extract', 'transaction_rollback']
out.append('| Case | ' + ' | '.join(a['short'] for a in apps) + ' |')
out.append('| --- | ' + ' | '.join('---:' for a in apps) + ' |')
for c in key:
    out.append(f'| {c} | ' + ' | '.join(f"{a['med'][c] / ops[c]:.4f}" for a in apps) + ' |')
out.append('')
out.append('Run-to-run spread:')
out.append('')
out.append('| App/mode | runs | sum of case medians per run (ms) | spread (max-min)/median | worst single-case spread |')
out.append('| --- | ---: | --- | ---: | --- |')
for a in apps:
    t = a['totals']; m = st.median(t)
    worst = max(cases, key=lambda c: (max(a['per_run'][c]) - min(a['per_run'][c])) / a['med'][c])
    w = a['per_run'][worst]
    out.append(f"| {a['label']} | {len(t)} | {', '.join(f'{x:,.1f}' for x in t)} | {(max(t) - min(t)) / m * 100:.1f}% | {worst} {(max(w) - min(w)) / a['med'][worst] * 100:.0f}% |")
out.append('')
out.append('Reported metadata (first run):')
out.append('')
out.append('| App/mode | driver | SQLite | journal_mode | synchronous | integrity | extra |')
out.append('| --- | --- | --- | --- | --- | --- | --- |')
for a in apps:
    r = a['runs'][0]; m = r['metadata']
    extra = ', '.join(f'{k}={m[k]}' for k in ('handle_class', 'connection_driver', 'nativephp_mobile', 'php') if k in m)
    out.append(f"| {a['label']} | {r.get('driver', '')} | {m['sqlite_version']} | {m['journal_mode']} | {m['synchronous']} | {', '.join(sorted({x['metadata']['integrity_check'] for x in a['runs']}))} ({len(a['runs'])}/{len(a['runs'])}) | {extra} |")
md = '\n'.join(out)
open(f'{D}/summary.md', 'w').write(md + '\n')
json.dump({a['label']: {'files': a['files'], 'median_of_run_medians_ms': a['med'], 'per_run_medians_ms': a['per_run'], 'totals_ms': a['totals']} for a in apps}, open(f'{D}/summary.json', 'w'), indent=1)
print(md)
