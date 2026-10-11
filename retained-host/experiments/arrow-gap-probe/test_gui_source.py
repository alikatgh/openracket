import hashlib
import os
from pathlib import Path
import re
import tempfile
import unittest
import prepare_gui as prepare

HERE=Path(__file__).resolve().parent
SOURCE=Path(os.getenv('GUI_TEST_SOURCE_DIR','/tmp/17916276701791627670599-drracket-core-lib/drracket/private')).resolve()


def remove_insertions(text):
    return re.sub(r'\n;; GUI-OBSERVE-BEGIN [^\n]+\n.*?\n;; GUI-OBSERVE-END [^\n]+\n','',text,flags=re.S)


def balanced(text):
    """Static delimiter check only; this never substitutes for the native reader."""
    stack=[];i=0;comment=0;string=False;escape=False
    closes={')':'(',']':'[','}':'{'}
    while i<len(text):
        c=text[i];pair=text[i:i+2]
        if comment:
            if pair=='#|':comment+=1;i+=2;continue
            if pair=='|#':comment-=1;i+=2;continue
            i+=1;continue
        if string:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':string=False
            i+=1;continue
        if pair=='#|':comment=1;i+=2;continue
        if pair=='#;':i+=2;continue
        if pair=='#\\':
            i+=2
            if i<len(text):
                i+=1
                while i<len(text) and text[i].isalpha():i+=1
            continue
        if c==';':
            i=text.find('\n',i)
            if i<0:break
            continue
        if c=='"':string=True
        elif c in '([{':stack.append((c,i))
        elif c in closes:
            if not stack or stack[-1][0]!=closes[c]:
                raise AssertionError(f'Bad delimiter at{ i}: {text[max(0,i-100):i+50]}')
            stack.pop()
        i+=1
    if stack or string or comment:raise AssertionError(f'Unclosed delimiters{stack[-3:]} string={string} block_comment={comment}')


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=prepare.verify_sources(SOURCE)

    def test_exact_four_pins_and_insertion_removal(self):
        self.assertEqual(len(self.original),4)
        for name,original in self.original.items():
            transformed=prepare.TRANSFORMS[name](original)
            self.assertEqual(remove_insertions(transformed),original,name)
            balanced(transformed)

    def test_new_helpers_static_delimiters(self):
        for name in ('gui-observer.rkt','gui-phase.rkt','test_gui_observer.rkt','test_gui_phase.rkt','application-probe.rkt','test_application_probe.rkt','test_arrow_probe.rkt','queued-sampler.rkt','test_queued_sampler.rkt'):
            balanced((HERE/name).read_text())

    def test_source_callback_order_and_post_terminal_emission(self):
        worker=prepare.transform_worker(self.original['expanding-place.rkt'])
        sender=worker.index("(place-channel-put response-pc (vector 'handler-results")
        self.assertLess(sender,worker.index("(openracket-phase-hook 'emit)",sender))
        self.assertNotIn('worker-ready!',worker)
        self.assertNotIn('openracket-expansion-replay',worker)
        gui=prepare.transform_gui(self.original['syncheck/gui.rkt'])
        self.assertEqual(gui.count('(process-trace-element known-dead-place-channels defs-text (car val))'),1)
        self.assertIn('(20 . <= . (- (current-inexact-milliseconds) start-time))',gui)
        live=gui.index("(openracket-gui-hook 'application-live?")
        reset=gui.index('(set-syncheck-running-mode #f)',live)
        complete=gui.index("(openracket-gui-hook 'application-complete",reset)
        self.assertLess(live,reset);self.assertLess(reset,complete)
        caller=prepare.transform_language(self.original['module-language.rkt'])
        self.assertEqual(caller.count('(show-results res)'),1)
        self.assertEqual(caller.count('(monitor-status (vector-ref res 1) (vector-ref res 2))'),1)
        self.assertLess(caller.index("'terminal-callback-enter"),caller.index('(set-pending-thread #f #f)',caller.index("'terminal-callback-enter")))

    def test_gui_hooks_have_no_file_writes_or_extra_payload_roots(self):
        source=(HERE/'gui-observer.rkt').read_text()
        hooks=source[source.index('(define (request!'):]
        self.assertNotIn('write-atomic!',hooks)
        self.assertNotIn('persist!',hooks)
        for key in ("'snapshot snapshot", "'result result", "'payload payload"):
            self.assertNotIn(key,hooks)
        self.assertIn('Identity evidence exceeds 1024 characters',source)
        self.assertIn('stale_application_events',source)
        phase=(HERE/'gui-phase.rkt').read_text()
        for forbidden in ('make-log-receiver','continuation-marks','module->namespace','xref','(thread ', '(thread\n','place-channel-put','sync/timeout'):
            self.assertNotIn(forbidden,phase)
        self.assertIn('(define max-jobs 8)',phase)
        self.assertIn('(when (and job collect-points?)',phase)

    def test_application_fixed_storage_and_no_payload_or_counter_snapshots(self):
        helper = (HERE/'application-probe.rkt').read_text()
        for text in ('(define records (make-vector 8 #f))', '(build-vector 13', '(build-vector 4',
                     "(define (application-hook action r [arg #f])", 'snapshot_quiescent'):
            self.assertIn(text, helper)
        for forbidden in ('current-memory-use', 'current-gc-milliseconds', 'current-process-milliseconds',
                          'write-json', 'call-with-output-file', '(thread ', '(thread\n',
                          'place-channel', 'current-continuation-marks', '(make-hash'):
            self.assertNotIn(forbidden, helper)
        self.assertNotIn('record payload', helper)
        self.assertNotIn('record trace', helper)

    def test_application_seam_and_final_call_order(self):
        text = prepare.transform_gui(self.original['syncheck/gui.rkt'])
        start = text.index('(define/public (replay-compile-comp-trace defs-text val bx)')
        stop = text.index('(define/public (reset-previous-check-syntax-information', start)
        method = text[start:stop]
        call = '(process-trace-element known-dead-place-channels defs-text (car val))'
        before = method.index("'entry-before")
        after = method.index("'entry-after")
        self.assertLess(before, method.index(call)); self.assertLess(method.index(call), after)
        entry = method[before:after]
        for forbidden in ('lambda', 'with-handlers', 'dynamic-wind', 'parameterize'):
            self.assertNotIn(forbidden, entry)
        q = method.index('(queue-callback')
        self.assertLess(q, method.index("'batch-yield"))
        self.assertLess(method.index("'batch-resume"), method.index('(when (unbox bx)', q))
        reset = method.index('(set-syncheck-running-mode #f)')
        self.assertLess(reset, method.index("'final-after openracket-application-profile 3"))
        self.assertLess(method.index("'final-after openracket-application-profile 3"),
                        method.index("'application-complete openracket-application-token"))
        self.assertNotIn('20 . < .', method)
        self.assertEqual(method.count('(queue-callback'), 1)

    def test_nested_arrow_exact_guards_expressions_and_no_last_position_change(self):
        stock = self.original['syncheck/gui.rkt']
        text = prepare.transform_gui(stock)
        start = text.index('(define/public (syncheck:add-arrow/name-dup/pxpy start-text')
        stop = text.index(';; syncheck:add-tail-arrow', start)
        method = text[start:stop]
        self.assertLess(method.index('(and arrow-records'), method.index("'before openracket-arrow-profile 0"))
        self.assertLess(method.index('(preferences:get'), method.index('(add-to-bindings-table'))
        self.assertLess(method.index("'binding-after"), method.index('(make-var-arrow'))
        self.assertLess(method.index('(make-var-arrow'), method.index("'before openracket-arrow-profile 1"))
        self.assertLess(method.index("'endpoint-after openracket-arrow-profile 1"),
                        method.index("'before openracket-arrow-profile 2"))
        self.assertEqual(method.count('(add-to-bindings-table'), 1)
        self.assertEqual(method.count('(add-to-range/key'), 2)
        for forbidden in ('lambda', 'with-handlers', 'dynamic-wind', 'parameterize', 'last-position'):
            self.assertNotIn(forbidden, method)
        # Dynamic editor length reads and private interval-map implementation are
        # byte-for-byte stock, not inferred from just the three wrapped calls.
        original_private = stock[stock.index('            (define/private (add-to-range/key'):stock.index('            (inherit get-top-level-window)', stock.index('            (define/private (add-to-range/key'))]
        self.assertIn(original_private, text)

    def test_sampler_publication_and_host_absolute_deadline_join_order(self):
        helper = (HERE/'application-probe.rkt').read_text()
        self.assertIn('(vector-immutable (record-id r) (record-generation r)', helper)
        self.assertIn('(set-box! application-pending-box #f)', helper)
        self.assertNotIn('box-cas!', helper)
        host = (HERE/'capture-host.rkt').read_text()
        self.assertIn('(eventspace-handler-thread (current-eventspace)) (current-thread)', host)
        self.assertIn('(make-weak-box (current-thread))', host)
        self.assertIn('(alarm-evt deadline #t)', host)
        join = host.index('     (stop-and-join-sampler! deadline)')
        for after in ('(define after-join-record (complete-observation))',
                      "(hash-set! report 'final_snapshot_characters", "(persist-application! #t)"):
            self.assertLess(join, host.index(after, join))
        self.assertIn("(hash-ref last-observation 'request_count)", host[join:])
        self.assertIn('(not (unbox application-pending-box))', host[join:])
        self.assertIn("#:encode 'control", host)
        for forbidden in ('kill-thread', 'custodian-shutdown-all', 'make-custodian'):
            self.assertNotIn(forbidden, host)

    def test_sampler_fixed_storage_weak_handler_and_public_stack_api(self):
        source = (HERE/'queued-sampler.rkt').read_text()
        for text in ('(define sample-period-ms 100.0)', '(define attempt-cap 1024)',
                     '(define frame-cap 8)', '(define text-cap 240)',
                     '(continuation-mark-set->context (continuation-marks actual))',
                     '(weak-box-value weak-handler)', '(eq? token (unbox pending-box))',
                     '(thread-dead-evt (sampler-worker h))'):
            self.assertIn(text, source)
        self.assertGreaterEqual(source.count('(eq? token (unbox pending-box))'), 2)
        for forbidden in ('(kill-thread', '(custodian-shutdown-all', '(make-custodian',
                          '(make-log-receiver', '(box-cas!', '(write-json', '(call-with-output-file'):
            self.assertNotIn(forbidden, source)
        native = (HERE/'test_gui_native.py').read_text()
        self.assertIn("test_queued_sampler.rkt", native)
        preflight = (HERE/'native_preflight.py').read_text()
        self.assertIn('if result.skipped or not result.wasSuccessful():return 1', preflight)

    def test_application_reporting_only_final_and_failure_with_quiescence(self):
        host = (HERE/'capture-host.rkt').read_text()
        balanced(host)
        self.assertEqual(host.count('(persist-application!'), 3)
        self.assertIn('(persist-application! #t)', host)
        self.assertIn('(jsexpr->string (application-summary quiescent?))', host)
        polling = host[host.index('(define completed-record'):host.index('(define points (hash-ref completed-record')]
        self.assertNotIn('application-summary', polling)
        self.assertNotIn('persist-application!', polling)

    def test_wrong_pins_and_escaped_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve()
            (root/'syncheck').mkdir()
            for name,text in self.original.items():(root/name).write_text(text)
            self.assertEqual(prepare.verify_sources(root),self.original)
            (root/'syncheck/gui.rkt').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'Unexpected pinned source'):prepare.verify_sources(root)

    def test_source_aliases_resolve_but_linked_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            parent=Path(temp).resolve()
            root=parent/'root';root.mkdir();(root/'syncheck').mkdir()
            for name,text in self.original.items():(root/name).write_text(text)
            alias=parent/'alias';alias.symlink_to(root,target_is_directory=True)
            self.assertEqual(prepare.verify_sources(alias),self.original)
            target=root/'module-language.rkt'
            outside=parent/'outside.rkt';outside.write_text(self.original['module-language.rkt'])
            target.unlink();target.symlink_to(outside)
            with self.assertRaisesRegex(ValueError,'independently cloned'):
                prepare.verify_sources(root)
            target.unlink();target.hardlink_to(outside)
            with self.assertRaisesRegex(ValueError,'independently cloned'):
                prepare.verify_sources(root)
            target.unlink();target.write_text(self.original['module-language.rkt'])
            with self.assertRaisesRegex(ValueError,'independently cloned'):
                prepare.verify_sources(root,parent/'unrelated')

    def test_copied_fixture_matches_exact_snapshot(self):
        from fixtures import generate
        base,position=generate(1048576)
        self.assertEqual(position,524139)
        self.assertEqual(hashlib.sha256(base).hexdigest(),
                         '766af354720de3e235cd60d9eb511f0469c35b36a99b599a071453d22a1b499e')
        self.assertEqual(hashlib.sha256(base[:position]+b'x'+base[position:]).hexdigest(),
                         'f66aacc13f5cec59fd57f20a0fc82fa2c159a3cb4a77cbc57d4eddbd1f107735')

    def test_each_transform_requires_unique_anchors(self):
        for name,fn in prepare.TRANSFORMS.items():
            with self.assertRaises(ValueError):fn('')

if __name__=='__main__':unittest.main()
