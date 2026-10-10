#!/usr/bin/env python3
"""Linux-only retention check for evaluator snapshots; not a GUI benchmark."""
import json,pathlib
from test_bridge import Bridge,text
b=Bridge();samples=[]
try:
    b.run('#lang racket\n(define p (make-parameter 1))')
    def sample(n):
        r=b.call('eval',source='(collect-garbage) (collect-garbage) (current-memory-use)')
        status=pathlib.Path('/proc',str(b.proc.pid),'status').read_text()
        rss=int(next(x for x in status.splitlines() if x.startswith('VmRSS:')).split()[1])
        samples.append({'submissions':n,'racket_heap_bytes_after_gc':int(text(r).strip()),'engine_rss_kib':rss})
    sample(0)
    for n in range(1,2001):
        assert text(b.call('eval',source='(p 42) (p)'))=='42\n'
        if n%500==0:sample(n)
    print(json.dumps({'scope':'Racket engine process only, Linux /proc RSS and current-memory-use after two explicit GCs; 2,000 sequential parameter-mutating submissions; excludes GUI.', 'samples':samples},indent=2))
finally:b.close()
