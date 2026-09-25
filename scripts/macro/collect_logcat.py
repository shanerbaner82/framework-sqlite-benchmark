#!/usr/bin/env python3
"""Bash/python port of scripts/collect-release-logcat.ps1.

usage: collect_logcat.py SERIAL OUTPUT.json [--wait SECONDS]
Reassembles the SQLITE_BENCHMARK_PART chunks of the last SQLITE_BENCHMARK_DONE run in
logcat, verifies 17 ok cases + integrity_check=ok, writes OUTPUT.json.
With --wait, polls logcat until a DONE marker appears (or the timeout elapses).
"""
import json, os, re, subprocess, sys, time

adb = os.environ.get('ADB', 'adb')

def read(serial):
    return subprocess.run([adb, '-s', serial, 'logcat', '-d', '-v', 'raw'], capture_output=True, text=True, errors='replace').stdout.splitlines()

def main():
    serial, output = sys.argv[1], sys.argv[2]
    wait = float(sys.argv[sys.argv.index('--wait') + 1]) if '--wait' in sys.argv else 0
    deadline = time.time() + wait
    while True:
        lines = read(serial)
        done = [m.group(1) for l in lines for m in [re.search(r'SQLITE_BENCHMARK_DONE (\d+)', l)] if m]
        if done or time.time() > deadline:
            break
        time.sleep(3)
    if not done:
        sys.exit('No completed benchmark in logcat.')
    run_id = done[-1]
    parts, total = {}, 0
    pat = re.compile(r'SQLITE_BENCHMARK_PART %s (\d+)/(\d+) (.*?)(?: -- From line \d+)?$' % run_id)
    for l in lines:
        m = pat.search(l)
        if m:
            parts[int(m.group(1))] = m.group(3)
            total = int(m.group(2))
    if not total or len(parts) != total:
        sys.exit(f'Expected {total} result chunks; found {len(parts)}.')
    raw = ''.join(parts[i] for i in range(1, total + 1))
    report = json.loads(raw)
    bad = [r['name'] for r in report['results'] if r.get('status') != 'ok']
    if report['metadata'].get('integrity_check') != 'ok' or len(report['results']) != 17 or bad:
        sys.exit(f'Incomplete or failed benchmark report: integrity={report["metadata"].get("integrity_check")} failed={bad}')
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        f.write(raw)
    print(output)

main()
