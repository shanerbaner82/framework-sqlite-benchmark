#!/usr/bin/env python3
"""Inspect one Macrobenchmark perfetto trace: for a case section, show which thread ran it, how many
other slices were emitted inside it (tracing overhead), and CPU placement of the app's busiest threads.
usage: .venv-perfetto/bin/python scripts/macro/trace_inspect.py TRACE [case]"""
import sys
from perfetto.trace_processor import TraceProcessor
tp = TraceProcessor(trace=sys.argv[1])
case = sys.argv[2] if len(sys.argv) > 2 else 'point_select'
q = lambda s: list(tp.query(s))
secs = q(f"""select s.ts, s.dur, t.name tname, t.utid, p.name pname from slice s join thread_track tt on s.track_id=tt.id
          join thread t using(utid) join process p using(upid) where s.name='case:{case}' order by s.ts""")
if not secs: sys.exit('no section')
s = secs[len(secs) // 2]
print(f"{sys.argv[1].split('/')[-1]}: case:{case} x{len(secs)} on thread '{s.tname}' ({s.pname}); middle sample {s.dur/1e6:.2f} ms")
inner = q(f"""select count(*) n from slice x join thread_track tt on x.track_id=tt.id join thread t using(utid)
           join process p using(upid) where p.name='{s.pname}' and x.ts>={s.ts} and x.ts+x.dur<={s.ts+s.dur} and x.name not like 'case:%'""")[0].n
top = q(f"""select x.name, count(*) n from slice x join thread_track tt on x.track_id=tt.id join thread t using(utid)
           join process p using(upid) where p.name='{s.pname}' and x.ts>={s.ts} and x.ts+x.dur<={s.ts+s.dur} and x.name not like 'case:%'
           group by x.name order by n desc limit 6""")
print(f"  other app slices inside that sample: {inner}; top: " + ', '.join(f'{r.name[:40]}x{r.n}' for r in top))
rows = q(f"""select t.name tname, sc.cpu, sum(min(sc.ts+sc.dur,{s.ts+s.dur})-max(sc.ts,{s.ts})) run from sched sc join thread t using(utid)
            join process p using(upid) where p.name='{s.pname}' and sc.ts<{s.ts+s.dur} and sc.ts+sc.dur>{s.ts} group by t.name, sc.cpu""")
by = {}
for r in rows: by.setdefault(r.tname, {})[r.cpu] = r.run
for t, cpus in sorted(by.items(), key=lambda kv: -sum(kv[1].values()))[:4]:
    tot = sum(cpus.values())
    little = sum(v for c, v in cpus.items() if c <= 3); mid = sum(v for c, v in cpus.items() if 4 <= c <= 6); big = cpus.get(7, 0)
    print(f"  thread {t[:20]:20s} running {tot/1e6:7.2f} ms of {s.dur/1e6:.2f} ms: little {little/tot*100:4.0f}% mid {mid/tot*100:4.0f}% big {big/tot*100:4.0f}%")
