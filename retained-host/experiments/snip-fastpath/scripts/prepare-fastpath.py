#!/usr/bin/env python3
"""Generate one exact-version, opt-in stock cache experiment. Never install it."""
from pathlib import Path
import hashlib, json, difflib
ROOT=Path(__file__).resolve().parents[1]
PIN='7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638'
raw=(ROOT/'vendor/text-misc-v9.3.rkt').read_bytes()
if hashlib.sha256(raw).hexdigest()!=PIN: raise SystemExit('Refuse byte-different upstream source')
s=raw.decode('utf-8')
anchor='''      (inherit find-first-snip find-snip)
'''
assert s.count(anchor)==1
helpers='''
      ;; OpenRacket experiment: stable stock all-string knowledge can avoid
      ;; repeated scans when the colorer opens another editor-backed input port.
      ;; No new scan, lexer setting, style update, or evaluator behavior is added.
      (define openracket-fast-path-enabled?
        (equal? (getenv "OPENRACKET_ALL_STRING_FAST_PATH") "1"))
      (define openracket-mutations-pending null)
      (define openracket-fast-path-safe? #t)

      (define/private (openracket-before-mutation kind start len thunk)
        (cond
          [(not openracket-fast-path-enabled?) (thunk)]
          [else
           (define entered? #f)
           (define completed? #f)
           (define token (vector kind start len #f))
           (dynamic-wind
             (lambda ()
               ;; Rich/unknown history is outside this shortcut's plain-stock
               ;; eligibility. Never re-enable after an unexamined insertion.
               (unless (eq? all-string-snips-state #t)
                 (set! openracket-fast-path-safe? #f))
               ;; Reentering any captured callback continuation fails closed.
               (when entered? (set! openracket-fast-path-safe? #f))
               (set! entered? #t)
               (set! openracket-mutations-pending
                     (cons token openracket-mutations-pending)))
             (lambda ()
               (begin0 (thunk)
                 (set! completed? #t)
                 (vector-set! token 3 #t)))
             (lambda ()
               (unless completed?
                 ;; This covers raised values and all other nonlocal escapes.
                 ;; Never infer that the existing stock cache was updated.
                 (set! openracket-fast-path-safe? #f)
                 (set! openracket-mutations-pending null))))]))

      (define/private (openracket-after-mutation kind start len thunk)
        (cond
          [(not openracket-fast-path-enabled?) (thunk)]
          [else
           (define entered? #f)
           (define completed? #f)
           (define token (and (pair? openracket-mutations-pending)
                              (car openracket-mutations-pending)))
           (define matching?
             (and token (eq? kind (vector-ref token 0))
                  (equal? start (vector-ref token 1))
                  (equal? len (vector-ref token 2)) (vector-ref token 3)))
           (dynamic-wind
             (lambda ()
               (unless (and (not entered?) matching?)
                 (set! openracket-fast-path-safe? #f))
               (set! entered? #t))
             (lambda () (begin0 (thunk) (set! completed? #t)))
             (lambda ()
               (unless completed? (set! openracket-fast-path-safe? #f))
               ;; An unmatched callback cannot consume some other pending edit.
               (if (and matching? (pair? openracket-mutations-pending)
                        (eq? token (car openracket-mutations-pending)))
                   (set! openracket-mutations-pending (cdr openracket-mutations-pending))
                   (set! openracket-fast-path-safe? #f))))]))

      (define/augment (on-insert start len)
        (openracket-before-mutation 'insert start len
          (lambda () (inner (void) on-insert start len))))

      (define/augment (after-delete start len)
        (openracket-after-mutation 'delete start len
          (lambda () (inner (void) after-delete start len))))

      (define/override (find-next-non-string-snip snip)
        (if (and openracket-fast-path-enabled?
                 openracket-fast-path-safe?
                 (null? openracket-mutations-pending)
                 (eq? all-string-snips-state #t)
                 ;; Keep the exact arity and stock detached-snip contract.
                 ;; Only an exact native string snip has the known field-only
                 ;; get-admin method. Subclasses/custom/invalid arguments always
                 ;; delegate, without invoking an additional virtual callback.
                 ;; A detached native snip delegates too: stock object=? raises
                 ;; for its #f admin, even when this editor is empty.
                 (or (not snip)
                     (and (is-a? snip string-snip%)
                          (eq? (object-interface snip) (class->interface string-snip%))
                          (send snip get-admin))))
            #f
            (super find-next-non-string-snip snip)))
'''
s=s.replace(anchor,anchor+helpers)
# A custom string subclass can split/merge into a rich snip without ordinary
# insertion callbacks. Observe exact native string identity in the ORIGINAL
# after-insert range walk; no extra virtual scan or subclass call is introduced.
scan_start=s.index('      (define/augment (after-insert ',s.index('  (define all-string-snips-mixin'))
scan_end=s.index('      (define/augment (on-delete',scan_start)
scan=s[scan_start:scan_end]
scan_needle='              [(is-a? s string-snip%)\n               (define size (send s get-count))'
scan_replacement='              [(is-a? s string-snip%)\n               (when (and openracket-fast-path-enabled?\n                          (not (eq? (object-interface s) (class->interface string-snip%))))\n                 (set! openracket-fast-path-safe? #f))\n               (define size (send s get-count))'
assert scan.count(scan_needle)==1
s=s[:scan_start]+scan.replace(scan_needle,scan_replacement)+s[scan_end:]
for name,next_marker,guard in [
 ('after-insert','      (define/augment (on-delete',"openracket-after-mutation 'insert start len"),
 ('on-delete','      ;; (or/c',"openracket-before-mutation 'delete start end")]:
 start=s.index('      (define/augment ('+name+' ', s.index('  (define all-string-snips-mixin'))
 stop=s.index(next_marker,start)
 old=s[start:stop].rstrip()
 first,body=old.split('\n',1)
 assert body.endswith(')')
 body=body[:-1]
 wrapped=first+'\n        ('+guard+'\n          (lambda ()\n'+''.join('    '+line+'\n' for line in body.splitlines())+'          )))'
 s=s[:start]+wrapped+'\n\n'+s[stop:]
# Do not patch Framework's exported generic mixin. The experiment is private
# to DrRacket's known stock superclass composition, whose inner dispatch has
# no competing find-next-non-string-snip override in the exact source set.
unit_pin='535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5'
unit_raw=(ROOT/'vendor/unit-v9.3.rkt').read_bytes()
if hashlib.sha256(unit_raw).hexdigest()!=unit_pin:
    raise SystemExit('Refuse byte-different DrRacket composition source')
unit=unit_raw.decode('utf-8')
require_anchor='         "insulated-read-language.rkt"\n'
call_anchor='                         (text:all-string-snips-mixin\n'
assert unit.count(require_anchor)==1 and unit.count(call_anchor)==1
unit=unit.replace(require_anchor,require_anchor+'         "openracket-all-string-snips.rkt"\n')
unit=unit.replace(call_anchor,call_anchor.replace('text:all-string-snips-mixin',
                                                'openracket:all-string-snips-mixin'))
start=s.index('  (define all-string-snips-mixin\n')
stop=s.index('  (define overwrite-disable<%>',start)
clone=s[start:stop].rstrip()
helper_header='''#lang racket/base
;; Derived only from the exact Racket 9.3 Framework all-string-snips mixin.
;; See vendor licenses and reports/fastpath-manifest.json for provenance.
;; This private helper is used ONLY at the pinned stock DrRacket composition.
;; The public Framework mixin/module remains byte-for-byte original.
(require racket/class racket/gui/base
         (only-in framework text:all-string-snips<%> text:all-string-snips-mixin))
(provide openracket:all-string-snips-mixin openracket-fast-path-selected?)
;; Reuse the real public interface object; never create a replacement interface.
(define all-string-snips<%> text:all-string-snips<%>)
'''
helper_footer='''
;; Default-off selection uses the exact stock mixin, not a behavior-simulating
;; wrapper. Native CI must explicitly prove the selected activation flag.
(define openracket-fast-path-selected?
  (equal? (getenv "OPENRACKET_ALL_STRING_FAST_PATH") "1"))
(define openracket:all-string-snips-mixin
  (if openracket-fast-path-selected? all-string-snips-mixin text:all-string-snips-mixin))
'''
helper=helper_header+clone+'\n'+helper_footer
outdir=ROOT/'overlay/drracket/private';outdir.mkdir(parents=True,exist_ok=True)
unit_out=outdir/'unit.rkt';unit_out.write_text(unit)
helper_out=outdir/'openracket-all-string-snips.rkt';helper_out.write_text(helper)
# Retire the earlier broad generated experiment; no Framework file is an overlay.
broad=ROOT/'overlay/framework/private/text-misc.rkt'
if broad.exists(): broad.unlink()
manifest={
 'racket':'9.3',
 'sources': {
   'framework/private/text-misc.rkt': {'package':'gui-lib','package_catalog_sha1':'31187c9593c5eaabcb1850c0120408d7d9734496','upstream_sha256':PIN,'modified':False},
   'drracket/private/unit.rkt': {'package':'drracket-core-lib','package_catalog_sha1':'d55515fcc1d1da846555ea0b5c1b593c4af619ef','upstream_sha256':unit_pin,'patched_sha256':hashlib.sha256(unit_out.read_bytes()).hexdigest()}},
 'helper_module':'drracket/private/openracket-all-string-snips.rkt',
 'helper_sha256':hashlib.sha256(helper_out.read_bytes()).hexdigest(),
 'opt_in_environment':'OPENRACKET_ALL_STRING_FAST_PATH=1',
 'scope':'one private stock DrRacket definitions composition; generic Framework mixin is unchanged',
 'default_off':'uses exact stock text:all-string-snips-mixin object',
 'eligibility':'exact native string-snip% only; rich/unknown history and subclasses permanently delegate',
 'native_run':False,'speedup_proven':False}
(ROOT/'reports/fastpath-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(ROOT/'reports/stock-all-string-fastpath.patch').write_text(''.join(difflib.unified_diff(unit_raw.decode().splitlines(True),unit.splitlines(True),fromfile='stock9.3/drracket/private/unit.rkt',tofile='candidate/drracket/private/unit.rkt')))
print(unit_out)
print(helper_out)
