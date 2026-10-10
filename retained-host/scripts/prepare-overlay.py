#!/usr/bin/env python3
"""Make a precise, presentation-only patch. Never edit an upstream installation."""
import argparse, hashlib, json, difflib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, default=ROOT/'vendor/switchable-button-v9.3.rkt')
a = p.parse_args()
raw_source = a.source.read_bytes()
s = raw_source.decode("utf-8")
# Verified official v9.3 source; fail closed for other releases, no heuristic patching.
expected = (ROOT/'vendor/upstream-sha256.txt').read_text().split()[0]
if hashlib.sha256(raw_source).hexdigest() != expected:
    raise SystemExit('STOP: stock source differs from inspected v9.3; review required.')
class_start = s.index('(define switchable-button%\n')
paint_start = s.index('    (define/override (on-paint)\n', class_start)
paint_end = s.index('    (define/private (draw-the-bitmap', paint_start)
old_paint = s[paint_start:paint_end]
replacement = '''    ;; OpenRacket presentation seam: retain all stock state and callbacks.
    (define/override (on-paint)
      (if (modern-ui?)
          (let-values ([(cw ch) (get-client-size)])
            (parameterize ([current-modern-theme
                            (if (eq? (get-modern-host-theme) 'auto)
                                (if (white-on-black-panel-scheme?) 'dark 'light)
                                (get-modern-host-theme))])
              (paint-modern-button (get-dc) cw ch label bitmap alternate-bitmap
                                   has-label? disabled? in? down? (get-small-width)
                                   (modern-control-font normal-control-font))))
          (paint-stock-button)))

''' + old_paint.replace('(define/override (on-paint)', '(define/private (paint-stock-button)', 1)
s = s[:paint_start] + replacement + s[paint_end:]
s = s.replace('         "private/panel-wob.rkt")',
              '         "private/panel-wob.rkt"\n         "private/openracket-paint.rkt")', 1)
for name, before, after in [('gap',4,6),('margin',2,4),('w-circle-space',6,10),('h-circle-space',6,8)]:
    old=f'(define {name} {before})'
    assert s.count(old)==1
    s=s.replace(old,f'(define {name} (if (modern-ui?) {after} {before}))',1)
# Only two measurement sites use the chosen font. Original paint stays intact.
for method in ('update-sizes', 'get-large-width'):
    start=s.index(f'    (define/{"private" if method=="update-sizes" else "public"} ({method})')
    end=s.index('\n    (define/',start+5)
    chunk=s[start:end]
    assert chunk.count('label normal-control-font')==1
    chunk=chunk.replace('label normal-control-font', 'label (modern-control-font normal-control-font)')
    s=s[:start]+chunk+s[end:]
overlay=ROOT/'overlay/mrlib'
(overlay/'private').mkdir(parents=True,exist_ok=True)
(overlay/'switchable-button.rkt').write_text(s)
(overlay/'private/openracket-paint.rkt').write_text((ROOT/'src/paint.rkt').read_text())
original=raw_source.decode('utf-8')
(ROOT/'artifacts/stock-toolbar-9.3.patch').write_text(''.join(difflib.unified_diff(
 original.splitlines(True),s.splitlines(True),fromfile='gui-lib/mrlib/switchable-button.rkt',
 tofile='gui-lib/mrlib/switchable-button.rkt')))
manifest={'racket':'9.3','source':str(a.source),'upstream_sha256':expected,
 'patched_sha256':hashlib.sha256(s.encode()).hexdigest(),
 'painter_sha256':hashlib.sha256((ROOT/'src/paint.rkt').read_bytes()).hexdigest(),
 'added_import':'private/openracket-paint.rkt',
 'changed_methods':['on-paint','update-sizes','get-large-width'],
 'added_method':'paint-stock-button','changed_constants':['gap','margin','w-circle-space','h-circle-space'],
 'event_and_callback_changes':False,'native_window_run':False}
(ROOT/'reports/patch-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Prepared version-pinned overlay and patch; original source unchanged.')
