#!/usr/bin/env python3
"""LOCAL CACHED-SOURCE EVIDENCE ONLY, not a portable CI acceptance command.

Reads the explicitly hard-coded historical /tmp cache locations below. The
portable native handoff does not depend on this script or those paths. Its saved
report is provenance from this local workspace, not proof of native compilation
or of sources installed on a later runner.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRRACKET = Path('/tmp/17916276491791627649681-drracket')
CORE = Path('/tmp/17916276701791627670599-drracket-core-lib')
GUI = Path('/tmp/17916293651791629365355-gui-lib')
MACRO = Path('/tmp/17916276991791627699800-macro-debugger')
HTDP = Path('/tmp/17916276541791627654466-htdp-lib')
SOURCES = [
    (DRRACKET, 'gui-debugger/debug-tool.rkt', [
        '(define-local-member-name debug-callback)',
        '(callback (λ (button) (send frame debug-callback)))',
        '(define/public (get-break-status)', '(define/public (get-stack-frames)',
        '(define/public (get-pc)', '(define/public (get-current-frame-endpoints)',
        '(define/public (get-step-button)', '(define/public (get-resume-button)',
        ';; the opt-out button handles this language']),
    (DRRACKET, 'macro-debugger/tool.rkt', [
        '(define-local-member-name run-macro-stepper)',
        '(callback (lambda (button) (send frame run-macro-stepper)))',
        '(send the-tab disable-evaluation)', '(send the-tab enable-evaluation)']),
    (MACRO, 'macro-debugger/view/stepper.rkt', [
        '(notify:define-notify current-step-index', '(define/public (get-view)',
        '(define/public-final (navigate-next)', '(define/public-final (navigate-to-end)',
        '(send/i term term-record<%> has-next?)', '(send/i term term-record<%> get-step-index)',
        '(list navigate-next-icon "Step" \'right)', '(list navigate-previous-icon "Step" \'left)']),
    (MACRO, 'macro-debugger/view/term-record.rkt', [
        '(define/public-final (get-step-index)', '(and steps (cursor-position steps))',
        '(define/public-final (get-step-count)']),
    (GUI, 'framework/private/notify.rkt', [
        '(format-id name "get-~a"', '(define/public-final (get-name)']),
    (GUI, 'framework/private/frame.rkt', [
        '(define/public (close)', '(when (can-close?)\n        (on-close)\n        (show #f))']),
    (GUI, 'mred/private/mritem.rkt', ['[get-label (lambda () label)]',
                                     '[command (lambda (e) (void (callback this e)))']),
    (GUI, 'mred/private/wxme/text.rkt', ['(def/public (call-clickback']),
    (CORE, 'drracket/private/rep.rkt', [
        '(define/public (get-user-namespace)', '(define/public (run-in-evaluation-thread thunk)',
        '(define/public (get-error-ranges)', '(make-srcloc definitions-text']),
    (HTDP, 'test-engine/test-tool.rkt', ['(define/public (get-test-editor)',
                                       '(define/public (get-test-window)']),
    (HTDP, 'test-engine/test-engine.rkt', ['(current-test-object (-> test-object?))',
                                         '(struct (unequal fail-reason)',
                                         '(define (run-tests!)']),
    (HTDP, 'test-engine/syntax.rkt', ['(syntax-line stx)', '(syntax-column stx)',
                                    '(syntax-position stx)', '(syntax-span stx)']),
    (HTDP, 'test-engine/test-markup.rkt', ['test-engine-m-of-n-tests-failed',
                                         'test-engine-in-at-line-column',
                                         'test-engine-both-tests-passed']),
    (HTDP, 'test-engine/markup-gui.rkt', ['(send text set-clickback',
                                       '(send current-rep highlight-errors']),
    (HTDP, 'test-engine/test-display-gui.rkt', ['(define (clear-test-display!',
                                              '(define/public (clear)',
                                              '(send editor delete 0 (send editor get-end-position))']),
]

def main():
    rows = []
    for package, relative, anchors in SOURCES:
        path = package / relative
        raw = path.read_bytes()
        text = raw.decode()
        locations = []
        for anchor in anchors:
            offset = text.find(anchor)
            if offset < 0:
                raise AssertionError(f'Missing source anchor in {relative}: {anchor}')
            locations.append({'anchor': anchor, 'line': text[:offset].count('\n')+1})
        rows.append({'module': relative, 'cached_source': str(path),
                     'sha256': hashlib.sha256(raw).hexdigest(), 'anchors': locations})
    report = {'status': 'source-audited', 'native_compile': 'not-run',
              'native_execution': 'not-run', 'source_count': len(rows), 'sources': rows}
    output = ROOT/'reports/stock-tool-source-audit.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(f'{len(rows)} cached source files / {sum(len(row["anchors"]) for row in rows)} API anchors verified')

if __name__ == '__main__': main()
