#!/usr/bin/env python3
"""Local process/IPC baseline; not a UI responsiveness or comparison benchmark."""
import json, statistics, time
from test_bridge import Bridge, text

def describe(xs):
    s=sorted(xs)
    return {'n':len(s),'min_ms':round(s[0],2),'median_ms':round(statistics.median(s),2),
            'p95_ms':round(s[min(len(s)-1,int(len(s)*.95))],2),'max_ms':round(s[-1],2)}
startups=[]
for _ in range(5):
    b=Bridge();startups.append(b.start_ms);b.close()
b=Bridge()
run=[]
source='#lang racket\n(define (square x) (* x x))\n(define exact 1/3)'
for _ in range(10):
    t=time.perf_counter();events=b.run(source);assert events[-1]['status']=='ok';run.append((time.perf_counter()-t)*1000)
evals=[]
for _ in range(50):
    t=time.perf_counter();events=b.call('eval',source='(square exact)');assert text(events)=='1/9\n';evals.append((time.perf_counter()-t)*1000)
checks=[]
for _ in range(50):
    t=time.perf_counter();events=b.call('check',source='(list "(" #\\( #;ignored 1)');assert events[-1]['status']=='ok';checks.append((time.perf_counter()-t)*1000)
breaks=[]
for _ in range(5):
    i=b.send('eval',source='(let loop () (loop))');b.next();time.sleep(.01)
    t=time.perf_counter();b.send('break');events=b.until_done(i);assert events[-1]['status']=='interrupted';breaks.append((time.perf_counter()-t)*1000)
b.close()
print(json.dumps({'racket_version':b.ready['racket_version'],'startup':describe(startups),
  'run_small_module':describe(run),'warm_interaction':describe(evals),'reader_check':describe(checks),
  'cooperative_break':describe(breaks), 'scope':'Linux x86_64 cloud, warm filesystem cache, subprocess NDJSON round trips; excludes Rust GUI/rendering.'},indent=2))
