#!/usr/bin/env python3
"""Source boundaries only, not Racket reader, runtime, or native GUI proof."""
import hashlib
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stock_source', ROOT/'tests/stock-tool-source-test.py')
stock_source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stock_source)

OLD_BRANCH = '''             ;; Return each action to the GUI event loop before coordinator polling.
             ((dynamic-require stock-tool-module 'run-native-tool-check!)
              frame (string->symbol follow-on-case) on-gui wait-for
              (lambda (created)
                (unless (memq created created-frames)
                  (set! created-frames (cons created created-frames)))))]'''
NEW_BRANCH = '''             ;; Requiring racket/gui/base made this module's loading thread the
             ;; initial GUI handler. Merely leaving on-gui does not leave it.
             (parameterize ([current-eventspace (send frame get-eventspace)])
               (call-in-tool-coordinator
                (lambda ()
                  ((dynamic-require stock-tool-module 'run-native-tool-check!)
                   frame (string->symbol follow-on-case) on-gui wait-for
                   (lambda (created)
                     (unless (memq created created-frames)
                       (set! created-frames (cons created created-frames))))))
                yield))]'''

class DispatchSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = (ROOT/'tests/independent-native-host.rkt').read_text()
        cls.bridge = (ROOT/'tests/native-tool-dispatch.rkt').read_text()
        cls.driver = (ROOT/'tests/native-tool-dispatch-standalone.rkt').read_text()

    def test_only_import_and_stock_dispatch_changed_in_host(self):
        # Remove the separately audited additive diagnostics before checking the
        # already-passed dispatch-only derivative against its original pin.
        host = self.host.replace('\n         "native-tool-failure-diagnostics.rkt"', '')
        host = host.replace("               'failure_payload (failure->diagnostic exception)\n", '')
        host = host.replace('''        (report-failure!
         e
         (lambda (original)
           (eprintf "OPENRACKET_NATIVE_FAILURE ~a\\n" (exn-message original))
           (failure-diagnostics! original)))''',
                            '''        (eprintf "OPENRACKET_NATIVE_FAILURE ~a\\n" (exn-message e))
        (failure-diagnostics! e)''')
        self.assertEqual(self.host.count(NEW_BRANCH), 1)
        requirement = 'json mrlib/switchable-button "native-tool-dispatch.rkt")'
        self.assertEqual(host.count(requirement), 1)
        restored = host.replace(NEW_BRANCH, OLD_BRANCH).replace(
            requirement, 'json mrlib/switchable-button)')
        self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(),
                         '2673ccd7ccd62d3dd9b43674120bf20b704b80684faed6487d7383bd317de4f5')

    def test_original_tool_and_strict_coordinator_and_driver_bytes_preserved(self):
        pins = {
            'native-tool-coordinator.rkt': 'a86f91cd5d55b27e1f9f7c535f387d935791daa7ba41b2934e6e3810fecf6384',
            'native-tool-coordinator-test.rkt': '72e040a7e14997477a420024714b810b98f6ecd52dc66ef510c6f9572ee1866d',
            'native-tool-coordinator-standalone.rkt': '1d35e1ad291c45fbfe850aaf75063cf29eb1dc9a00eff8aabd421503859c0949',
        }
        for name, digest in pins.items():
            self.assertEqual(hashlib.sha256((ROOT/'tests'/name).read_bytes()).hexdigest(), digest)

    def test_bridge_preserves_real_eventspace_and_handler_pump(self):
        self.assertIn('(parameterize ([current-eventspace (send frame get-eventspace)])', NEW_BRANCH)
        self.assertIn('                yield))]', NEW_BRANCH)
        for banned in ('make-eventspace', 'racket/gui', '(exit ', 'current-check-handler',
                       'sync/timeout', 'alarm-evt', 'sleep', 'OPENRACKET_NATIVE_READY'):
            self.assertNotIn(banned, self.bridge)
        self.assertEqual(self.bridge.count('(thread\n'), 1)
        self.assertIn('(wait-for-thread (thread-dead-evt coordinator))', self.bridge)

    def test_bridge_returns_or_reraises_after_worker_death_and_always_joins(self):
        for phrase in ("(lambda (failure) (cons 'error failure))",
                       "(cons 'value (thunk))", '(raise (cdr result))',
                       '(unless (thread-dead? coordinator)', '(unless result',
                       '(dynamic-wind', '(kill-thread coordinator)', '(thread-wait coordinator)'):
            self.assertIn(phrase, self.bridge)
        self.assertLess(self.bridge.index('(wait-for-thread (thread-dead-evt coordinator))'),
                        self.bridge.index('(raise (cdr result))'))
        self.assertEqual(self.bridge.count('(with-handlers'), 1)
        self.assertNotIn("(cons 'value #f)", self.bridge)

    def test_headless_regression_models_initial_thread_as_handler(self):
        for phrase in ('(define handler (current-thread))',
                       '(check-not-eq? coordinator handler)',
                       '(check-eq? (gui current-thread) handler)',
                       '(check-eq? (gui context)',
                       '(parameterize ([current-check-handler (lambda (_) (void))])',
                       '(make-checked-coordinator on-handler fake-wait handler)',
                       '(gui (lambda () (check-equal? 1 2)))',
                       '(eq? failure handler-failure)', '(check-false callback-active?)',
                       '(check-equal? last-timeout 20)', '(thread-dead? coordinator)',
                       "(for ([mode '(interrupted premature)])", 'terminated without a result'):
            self.assertIn(phrase, self.driver)
        self.assertNotIn('racket/gui/base"', self.driver)

    def test_injected_wrong_result_is_real_return_value_and_uncaught_typed_failure(self):
        negative = self.driver.split('  (when (equal? arguments #("--inject-wrong-result"))')[1]
        self.assertIn("(define actual (coordinate (lambda () (gui (lambda () 'actual)))))", negative)
        self.assertIn("(check-equal? actual 'deliberately-wrong)", negative)
        self.assertIn('[exn:test:check?', negative)
        self.assertEqual(negative.count('(raise failure)'), 1)
        self.assertIn('(flush-output)))\n            (raise failure))])', negative)
        for phrase in ("(eq? name 'check-equal?)", '(pretty-info? got)',
                       '(pretty-info? expected)', "(eq? (pretty-info-value got) 'actual)",
                       "(eq? (pretty-info-value expected) 'deliberately-wrong)"):
            self.assertIn(phrase, negative)
        self.assertLess(negative.index("(check-equal? actual 'deliberately-wrong)"),
                        negative.index('OPENRACKET_NATIVE_TOOL_DISPATCH_OK'))
        for marker in ('OPENRACKET_NATIVE_TOOL_DISPATCH_OK',
                       'OPENRACKET_NATIVE_TOOL_DISPATCH_INJECTING_FAILURE',
                       'OPENRACKET_NATIVE_TOOL_DISPATCH_FAILURE'):
            self.assertEqual(self.driver.count(marker), 1)

    def test_nonexception_identity_assertion_is_outside_its_exact_call_catch(self):
        expected = '''  (define raised-token (gensym 'raised-value))
  (define received-token
    (with-handlers ([(lambda (_) #t) (lambda (failure) failure)])
      (coordinate (lambda () (raise raised-token)))
      'returned-without-raising))
  ;; The strict assertion is outside the catch; normal return cannot satisfy it.
  (check-eq? received-token raised-token)'''
        self.assertIn(expected, self.driver)
        self.assertNotIn('(check-exn (lambda (failure) (eq? failure raised-token))', self.driver)

    def test_new_racket_lexical_delimiters(self):
        stock_source.delimiter_check(self.bridge)
        stock_source.delimiter_check(self.driver)

if __name__ == '__main__':
    unittest.main(verbosity=2)
