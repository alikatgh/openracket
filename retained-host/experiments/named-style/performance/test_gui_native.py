import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import prepare_gui
from test_gui_source import SOURCE, originals_for_arm
HERE=Path(__file__).resolve().parent
RACKET=Path(os.getenv('GUI_TEST_RACKET','/unavailable-native-racket'))

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RACKET.is_file():
            raise RuntimeError('Native Racket required; no skips or fallback interpreter permitted')
    def run_racket(self,arguments,observed=True):
        env={k:v for k,v in os.environ.items() if not k.startswith('OPENRACKET_')}
        if os.getenv('GUI_TEST_PROFILE'):env['PLTUSERHOME']=str(Path(os.environ['GUI_TEST_PROFILE']).resolve())
        env['OPENRACKET_GUI_OBSERVER']='1'
        if observed:env['OPENRACKET_GUI_PHASE_POINTS']='1'
        return subprocess.run([str(RACKET.resolve())]+arguments,env=env,capture_output=True,text=True,check=True,timeout=30)

    def test_scalar_gui_lifecycle_and_cancelled_queued_callbacks(self):
        self.run_racket(['-l','raco','test',str(HERE/'test_gui_observer.rkt')])

    def test_common_control_and_observed_existing_thread_inheritance(self):
        for observed in (False,True):
            self.run_racket(['-l','raco','test',str(HERE/'test_gui_phase.rkt')],observed)

    def test_actual_import_activation_refusals(self):
        self.run_racket(['-l','raco','test',str(HERE/'test_activation.rkt')],False)

    def test_cooperative_heartbeat_deadline_and_cleanup(self):
        self.run_racket(['-l','raco','test',str(HERE/'test_heartbeat.rkt')],False)

    def test_binding_public_export_shape_identity_and_witness(self):
        result = self.run_racket(['-l','raco','test',str(HERE/'test_binding_export.rkt')],False)
        self.assertIn('OPENRACKET_BINDING_GRAPH_TESTS_PASSED', result.stdout)

    def test_actual_style_list_scalar_witness_and_replacement(self):
        result = self.run_racket(['-l','raco','test',str(HERE/'test_style_witness.rkt')],False)
        self.assertIn('OPENRACKET_STYLE_WITNESS_TESTS_PASSED', result.stdout)

    def test_rackunit_failure_is_process_fatal_negative_control(self):
        # The same fatal handler used by every native helper test must propagate
        # one deliberately failing check to the subprocess status.
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            self.run_racket(['-e', '(begin (require rackunit) (current-check-handler raise) '
                             '(check-equal? 1 2) (displayln "INCORRECTLY_SURVIVED"))'],False)
        self.assertNotEqual(caught.exception.returncode, 0)
        self.assertNotIn('INCORRECTLY_SURVIVED', caught.exception.stdout)

    def test_generated_source_native_reader(self):
        for arm in ('stock', 'candidate'):
            for name,text in originals_for_arm(arm).items():
                with self.subTest(arm=arm, name=name), tempfile.TemporaryDirectory() as directory:
                    path=Path(directory).resolve()/Path(name).name
                    path.write_text(prepare_gui.TRANSFORMS[name](text))
                    code='(parameterize ([read-accept-reader #t]) (call-with-input-file '+json.dumps(str(path))+" (lambda (in) (void (read-syntax 'source in)))))"
                    self.run_racket(['-e',code])

    def test_flag_off_closures_never_load_helpers(self):
        body='''#lang racket/base
(define (getenv _) #f)
(define (dynamic-require . _) (error 'test "Unexpected helper load"))
'''+prepare_gui.GUI_PREFIX+prepare_gui.PHASE_PREFIX
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'disabled.rkt';path.write_text(body)
            self.run_racket([str(path)])

if __name__=='__main__':unittest.main()
