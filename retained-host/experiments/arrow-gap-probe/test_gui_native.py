import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import prepare_gui
from test_gui_source import SOURCE
HERE=Path(__file__).resolve().parent
RACKET=Path(os.getenv('GUI_TEST_RACKET','/unavailable-native-racket'))

@unittest.skipUnless(RACKET.is_file(),'Native Racket required; no local runtime/GUI installation')
class NativeTests(unittest.TestCase):
    def run_racket(self,arguments,observed=True,application=False):
        env={k:v for k,v in os.environ.items() if not k.startswith('OPENRACKET_')}
        if os.getenv('GUI_TEST_PROFILE'):env['PLTUSERHOME']=str(Path(os.environ['GUI_TEST_PROFILE']).resolve())
        env['OPENRACKET_GUI_OBSERVER']='1'
        if observed:env['OPENRACKET_GUI_PHASE_POINTS']='1'
        if application:env['OPENRACKET_GUI_APPLICATION_POINTS']='1'
        return subprocess.run([str(RACKET.resolve())]+arguments,env=env,capture_output=True,text=True,check=True,timeout=30)

    def test_scalar_gui_lifecycle_and_cancelled_queued_callbacks(self):
        self.run_racket(['-l','raco','test',str(HERE/'test_gui_observer.rkt')])

    def test_common_control_and_observed_existing_thread_inheritance(self):
        for observed in (False,True):
            self.run_racket(['-l','raco','test',str(HERE/'test_gui_phase.rkt')],observed)

    def test_application_fixed_buckets_lifecycle_and_failure_states(self):
        for observed in (False,True):
            self.run_racket(['-l','raco','test',str(HERE/'test_application_probe.rkt')],
                            observed=False,application=observed)

    def test_nested_arrow_hooks_short_circuit_exceptions_and_stale_context(self):
        for observed in (False, True):
            self.run_racket(['-l','raco','test',str(HERE/'test_arrow_probe.rkt')],
                            observed=False, application=observed)

    def test_queued_sampler_races_stop_bounds_and_delayed_scheduling(self):
        self.run_racket(['-l','raco','test',str(HERE/'test_queued_sampler.rkt')],
                        observed=False, application=True)

    def test_generated_arrow_method_preserves_guards_values_and_original_exceptions(self):
        text = prepare_gui.transform_arrow(prepare_gui.verify_sources(SOURCE)['syncheck/gui.rkt'])
        start = text.index('            (define/public (syncheck:add-arrow/name-dup/pxpy start-text')
        stop = text.index('            ;; syncheck:add-tail-arrow', start)
        method = text[start:stop]
        body = r'''#lang racket/base
(require rackunit racket/class)
(current-check-handler raise) ; Direct execution must fail nonzero on a check failure.
(define helper (string->path HELPER_PATH))
(define h (dynamic-require helper 'application-hook))
(define openracket-arrow-hook (dynamic-require helper 'application-arrow-hook))
(define summary (dynamic-require helper 'application-summary))
(define arrow-records #t)
(define preference #t)
(define binding-result #t)
(define events '())
(define failure-at #f)
(define original-exn (exn:fail "original stock exception" (current-continuation-marks)))
(define (record! x) (set! events (append events (list x))))
(define (preferences:get key) (record! 'preference) preference)
(define (add-to-bindings-table . args)
  (record! 'binding)
  (when (eq? failure-at 'binding) (raise original-exn))
  binding-result)
(define (make-var-arrow . args) (record! 'allocate) 'arrow)
(define (add-to-range/key text . args)
  (record! text)
  (when (eq? failure-at text) (raise original-exn))
  (if (eq? text 'end) (values 'result-one 'result-two) (void)))
(define probe% (class object% (super-new) ORIGINAL_METHOD))
(define obj (new probe%))
(define (invoke)
  (send obj syncheck:add-arrow/name-dup/pxpy 'start 0 1 0 0 'end 2 3 0 0 #t 0 #f #f))
;; No selected replay: normal calls remain ordinary and produce no errors.
(check-equal? (call-with-values invoke list) '(result-one result-two))
(for ([scenario '(outer-false pref-false binding-false success binding start end)]
      [id (in-naturals 1)])
  (set! arrow-records (not (eq? scenario 'outer-false)))
  (set! preference (not (eq? scenario 'pref-false)))
  (set! binding-result (not (eq? scenario 'binding-false)))
  (set! failure-at (and (memq scenario '(binding start end)) scenario))
  (set! events '())
  (define r (h 'begin (vector-immutable id 1))) (h 'batch-start r)
  (h 'entry-before r 'syncheck:add-arrow/name-dup/pxpy)
  (define answer (with-handlers ([exn:fail? values]) (call-with-values invoke list)))
  (cond
    [failure-at
     (check-eq? answer original-exn)
     (define rec (list-ref (hash-ref (summary) 'records) (sub1 id)))
     (check-equal? (hash-ref rec 'open_entry_depth) 1)
     (check-true (hash-ref (hash-ref rec 'arrow_detail) 'open_nested))]
    [else
     (if (eq? scenario 'success) (check-equal? answer '(result-one result-two))
         (check-true (and (= (length answer) 1) (void? (car answer)))))
     (h 'entry-after r) (h 'finish r #t)
     (check-equal? (hash-ref (list-ref (hash-ref (summary) 'records) (sub1 id)) 'errors) 0)])
  (check-equal? events
    (case scenario
      [(outer-false) '()]
      [(pref-false) '(preference)]
      [(binding-false binding) '(preference binding)]
      [(start) '(preference binding allocate start)]
      [else '(preference binding allocate start end)])))
'''
        body = body.replace('HELPER_PATH', json.dumps(str(HERE/'application-probe.rkt'))).replace('ORIGINAL_METHOD', method)
        body += '\n(displayln "ARROW-SEMANTICS-PASSED")\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'actual-arrow-method.rkt'; path.write_text(body)
            passed = self.run_racket([str(path)], observed=False, application=True)
            self.assertIn('ARROW-SEMANTICS-PASSED', passed.stdout)
            # Prove direct-racket RackUnit failures cannot silently exit zero.
            wrong = body.replace("'(result-one result-two)", "'(deliberate-wrong-result)", 1)
            self.assertNotEqual(wrong, body)
            path.write_text(wrong)
            with self.assertRaises(subprocess.CalledProcessError) as rejected:
                self.run_racket([str(path)], observed=False, application=True)
            self.assertNotIn('ARROW-SEMANTICS-PASSED', rejected.exception.stdout)

    def test_generated_source_native_reader(self):
        for name,text in prepare_gui.verify_sources(SOURCE).items():
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory).resolve()/Path(name).name
                path.write_text(prepare_gui.TRANSFORMS[name](text))
                code='(parameterize ([read-accept-reader #t]) (call-with-input-file '+json.dumps(str(path))+" (lambda (in) (void (read-syntax 'source in)))))"
                self.run_racket(['-e',code])

    def test_flag_off_closures_never_load_helpers(self):
        body='''#lang racket/base
(define (getenv _) #f)
(define (dynamic-require . _) (error 'test "Unexpected helper load"))
'''+prepare_gui.GUI_PREFIX+prepare_gui.PHASE_PREFIX+prepare_gui.APPLICATION_PREFIX
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'disabled.rkt';path.write_text(body)
            self.run_racket([str(path)])

if __name__=='__main__':unittest.main()
