#!/usr/bin/env python3
"""Pure transport checks and real-Racket NDJSON tests; Python stdlib only."""
import io, json, os, pathlib, queue, shutil, statistics, subprocess, tempfile, threading, time, unittest
from unittest import mock
ROOT = pathlib.Path(__file__).resolve().parents[1]
RACKET = os.environ.get('RACKET_BIN', 'racket')
BRIDGE = ROOT / 'runtime' / 'bridge.rkt'

class Bridge:
    def __init__(self):
        self.start = time.perf_counter()
        self.proc = subprocess.Popen([RACKET, str(BRIDGE)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', bufsize=1)
        self.events = queue.Queue()
        self.raw_stderr = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=lambda: self.raw_stderr.extend(self.proc.stderr), daemon=True).start()
        self.ready = self.next(10)
        assert self.ready['event'] == 'ready', self.ready
        self.start_ms = (time.perf_counter() - self.start) * 1000
        self.id = 0
    def _read(self):
        try:
            for line in self.proc.stdout:
                try: self.events.put(json.loads(line))
                except Exception: self.events.put({'event':'invalid-json', 'line':line})
        finally: self.events.put({'event':'eof'})
    def next(self, timeout=5):
        return self.events.get(timeout=timeout)
    def send(self, op, **kw):
        self.id += 1
        self.proc.stdin.write(json.dumps({'id':self.id,'op':op,**kw}, ensure_ascii=False)+'\n')
        self.proc.stdin.flush()
        return self.id
    def until_done(self, id, timeout=5):
        return self.until_done_ids({id}, timeout)
    def until_done_ids(self, ids, timeout=5):
        # Control acknowledgements and the active operation can finish in either
        # order. Collect both in one wait so neither terminal event is lost.
        pending=set(ids); results=[]; deadline=time.monotonic()+timeout
        while pending:
            remaining=deadline-time.monotonic()
            if remaining <= 0:
                raise AssertionError(f'Timed out waiting for done IDs {pending}; events={results[-8:]}')
            try:
                e=self.next(remaining)
            except queue.Empty:
                raise AssertionError(f'Timed out waiting for done IDs {pending}; events={results[-8:]}') from None
            results.append(e)
            assert e['event'] not in ('invalid-json','eof'), (e,self.raw_stderr)
            if e['event']=='done':pending.discard(e['id'])
        return results
    def call(self, op, **kw):
        return self.until_done(self.send(op, **kw))
    def run(self, source, cwd=None, path=None):
        return self.call('run', source=source,cwd=str(cwd or ROOT),path=str(path) if path else None)
    def close(self):
        if self.proc.poll() is None:
            try:self.call('shutdown')
            except Exception: self.proc.kill()
        self.proc.wait(timeout=3)
        for p in (self.proc.stdin,self.proc.stdout,self.proc.stderr): p.close()

def text(events, stream='value'):
    return ''.join(e['text'] for e in events if e['event']==stream)
def errors(events):return [e for e in events if e['event']=='error']

class BridgeHarnessTests(unittest.TestCase):
    """Script transport events only; these tests do not emulate evaluation."""
    def bridge(self, events=()):
        b=Bridge.__new__(Bridge)
        b.events=queue.Queue(); b.raw_stderr=[]
        for event in events:b.events.put(event)
        return b

    def test_control_and_active_done_are_collected_in_either_order(self):
        active={'event':'done','id':1,'status':'interrupted'}
        ack={'event':'done','id':2,'status':'ok'}
        unrelated={'event':'done','id':99,'status':'ok'}
        for terminals in ([ack,active],[active,ack]):
            with self.subTest(terminals=terminals):
                b=self.bridge([unrelated,*terminals,{'event':'stdout','id':1,'text':'later'}])
                self.assertEqual(b.until_done_ids({1,2}),[unrelated,*terminals])
                self.assertEqual(b.next()['text'],'later')

    def test_break_ack_alone_does_not_complete_active_operation(self):
        b=self.bridge()
        with mock.patch.object(b,'next',side_effect=[{'event':'done','id':2,'status':'ok'},queue.Empty]):
            with self.assertRaisesRegex(AssertionError,r'done IDs \{1\}'):
                b.until_done_ids({1,2})

    def test_eof_or_invalid_json_after_break_ack_is_a_failure(self):
        for event in ('eof','invalid-json'):
            with self.subTest(event=event):
                b=self.bridge([{'event':'done','id':2,'status':'ok'},{'event':event}])
                with self.assertRaisesRegex(AssertionError,event):b.until_done_ids({1,2})

    def test_output_does_not_extend_completion_deadline(self):
        output={'event':'stdout','id':1,'text':'still running'}
        terminal={'event':'done','id':1,'status':'ok'}
        b=self.bridge([output,output,output,terminal])
        with mock.patch.object(time,'monotonic',side_effect=[0,0,.4,.8,1]):
            with self.assertRaisesRegex(AssertionError,'Timed out'):b.until_done(1,timeout=1)
        self.assertEqual(b.next(),terminal)

    def test_reader_reports_invalid_json_and_process_eof(self):
        b=self.bridge()
        b.proc=mock.Mock(stdout=io.StringIO('{broken\n{"event":"done","id":1,"status":"ok"}\n'))
        b._read()
        self.assertEqual([b.next()['event'] for _ in range(3)],['invalid-json','done','eof'])

    def test_reader_rejects_entire_malformed_frame_then_recovers(self):
        terminal={'event':'done','id':1,'status':'ok'}
        valid=json.dumps(terminal)
        frames=[valid+suffix for suffix in ('{}',' null',' true',' 42',' "tail"',' garbage','\x00')]
        frames += ['', ' \t', '{"event":"done",}',
                   r'{"event":"done","text":"\q"}',
                   r'{"event":"done","text":"\u12"}',
                   '{"event":"done","text":"literal\tcontrol"}']
        for frame in frames:
            with self.subTest(frame=frame):
                b=self.bridge()
                b.proc=mock.Mock(stdout=io.StringIO(frame+'\n'+valid+'\n'))
                b._read()
                self.assertEqual(b.next(),{'event':'invalid-json','line':frame+'\n'})
                self.assertEqual(b.next(),terminal)
                self.assertEqual(b.next(),{'event':'eof'})
                self.assertTrue(b.events.empty())

    def test_reader_accepts_crlf_whitespace_and_escaped_newlines(self):
        event={'event':'stdout','id':1,'text':'λ🌱\n{"event":"done","id":999}'}
        b=self.bridge()
        b.proc=mock.Mock(stdout=io.StringIO('\t '+json.dumps(event,ensure_ascii=False)+' \t\r\n'))
        b._read()
        self.assertEqual(b.next(),event)
        self.assertEqual(b.next(),{'event':'eof'})
        self.assertTrue(b.events.empty())

    def test_reader_distinguishes_complete_and_truncated_final_frame_at_eof(self):
        terminal={'event':'done','id':1,'status':'ok'}
        complete=json.dumps(terminal)
        for frame in (complete,complete[:-1]):
            with self.subTest(frame=frame):
                b=self.bridge()
                b.proc=mock.Mock(stdout=io.StringIO(frame))
                b._read()
                if frame==complete:
                    self.assertEqual(b.until_done(1),[terminal])
                    self.assertEqual(b.next(),{'event':'eof'})
                else:
                    with self.assertRaisesRegex(AssertionError,'invalid-json'):b.until_done(1)
                    self.assertEqual(b.next(),{'event':'eof'})
                self.assertTrue(b.events.empty())

    def test_eof_without_target_done_fails_even_after_output(self):
        for prefix in ([],[{'event':'stdout','id':1,'text':'last output'}]):
            with self.subTest(prefix=prefix):
                b=self.bridge()
                b.proc=mock.Mock(stdout=io.StringIO(''.join(json.dumps(e)+'\n' for e in prefix)))
                b._read()
                with self.assertRaisesRegex(AssertionError,'eof'):b.until_done(1)

    def test_null_and_duplicate_done_ids_do_not_complete_other_targets_or_reset_timeout(self):
        events=[{'event':'done','id':None,'status':'error'},
                {'event':'done','id':1,'status':'ok'},
                {'event':'done','id':1,'status':'ok'},
                {'event':'done','id':2,'status':'interrupted'}]
        b=self.bridge()
        with mock.patch.object(time,'monotonic',side_effect=[100,100,100.25,100.5,100.75]), \
             mock.patch.object(b,'next',side_effect=events) as next_event:
            self.assertEqual(b.until_done_ids({1,2},timeout=1),events)
        self.assertEqual(next_event.call_args_list,[mock.call(1),mock.call(.75),mock.call(.5),mock.call(.25)])

    def test_null_id_can_be_an_explicit_completion_target(self):
        unrelated={'event':'done','id':1,'status':'ok'}
        terminal={'event':'done','id':None,'status':'error'}
        b=self.bridge([unrelated,terminal])
        self.assertEqual(b.until_done(None),[unrelated,terminal])

    def test_zero_timeout_does_not_consume_queued_terminal(self):
        terminal={'event':'done','id':1,'status':'ok'}
        b=self.bridge([terminal])
        with mock.patch.object(time,'monotonic',return_value=100):
            self.assertEqual(b.until_done_ids(set(),timeout=0),[])
            with self.assertRaisesRegex(AssertionError,r'done IDs \{1\}'):b.until_done(1,timeout=0)
        self.assertEqual(b.next(),terminal)

    def test_send_preserves_unicode_and_embedded_newlines_in_one_frame(self):
        b=self.bridge(); b.id=0; b.proc=mock.Mock(stdin=io.StringIO())
        source='λ🌱\n{"event":"done","id":999}'
        self.assertEqual(b.send('eval',source=source),1)
        frames=b.proc.stdin.getvalue().splitlines()
        self.assertEqual(len(frames),1)
        self.assertEqual(json.loads(frames[0]),{'id':1,'op':'eval','source':source})

@unittest.skipUnless(shutil.which(RACKET), 'Racket not found; set RACKET_BIN to run integration tests')
class RuntimeTests(unittest.TestCase):
    def setUp(self):self.b=Bridge()
    def tearDown(self):self.b.close()
    def ok(self, events):self.assertEqual(events[-1]['status'],'ok',events);self.assertFalse(errors(events),events)
    def test_run_reuse_exact_fractions_and_multiple_values(self):
        self.ok(self.b.run('#lang racket\n(define answer 1/3)\nanswer'))
        r=self.b.call('eval',source='(values (+ answer 1) 2/7 "λ🍰")')
        self.ok(r);self.assertEqual(text(r),'4/3\n2/7\n"λ🍰"\n')
    def test_module_values_are_values_not_stdout(self):
        r=self.b.run('#lang racket\n(display "hello")\n(eprintf "oops")\n1/3')
        self.ok(r);self.assertEqual(text(r),'1/3\n');self.assertEqual(text(r,'stdout'),'hello');self.assertEqual(text(r,'stderr'),'oops')
    def test_rerun_resets_module_and_interaction_definitions(self):
        self.ok(self.b.run('#lang racket\n(define old 42)'))
        self.ok(self.b.call('eval',source='(define added 7)'))
        self.ok(self.b.run('#lang racket\n(define fresh 5)'))
        for name in ('old','added'):
            self.assertEqual(self.b.call('eval',source=name)[-1]['status'],'error')
        self.assertEqual(text(self.b.call('eval',source='fresh')),'5\n')
    def test_definition_and_mutation_in_interactions(self):
        self.ok(self.b.run('#lang racket\n(define x 2)'))
        self.ok(self.b.call('eval',source='(set! x 3)\n(define y (+ x 1))'))
        self.assertEqual(text(self.b.call('eval',source='y')),'4\n')
    def test_unsaved_source_relative_require_and_working_directory(self):
        with tempfile.TemporaryDirectory() as d:
            d=pathlib.Path(d)
            (d/'helper.rkt').write_text('#lang racket/base\n(provide factor)\n(define factor 9)')
            (d/'main.rkt').write_text('#lang racket\n(error "STALE DISK")')
            (d/'data.txt').write_text('current working directory')
            src='#lang racket\n(require "helper.rkt")\n(define x (* factor 2))\n(file->string "data.txt")'
            r=self.b.run(src,d,d/'main.rkt');self.ok(r)
            self.assertIn('current working directory',text(r))
            self.assertEqual(text(self.b.call('eval',source='x')),'18\n')
            self.assertIn('STALE DISK',(d/'main.rkt').read_text())
    def test_current_directory_persists_between_submissions(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);target=root/'next';target.mkdir();(target/'data.txt').write_text('new cwd')
            self.ok(self.b.run('#lang racket',root,root/'main.rkt'))
            self.ok(self.b.call('eval',source='(current-directory '+json.dumps(str(target))+')'))
            r=self.b.call('eval',source='(file->string "data.txt")');self.ok(r);self.assertEqual(text(r),'"new cwd"\n')
            self.assertIn(str(target),text(self.b.call('eval',source='(current-directory)')))
    def test_module_parameter_changes_persist(self):
        with tempfile.TemporaryDirectory() as d:
            self.ok(self.b.run('#lang racket\n(current-directory '+json.dumps(d)+')\n(print-as-expression #f)'))
            self.assertIn(d,text(self.b.call('eval',source='(current-directory)')))
            self.assertEqual(text(self.b.call('eval',source='(print-as-expression)')),'#f\n')
    def test_user_parameters_persist_and_error_keeps_changes(self):
        self.ok(self.b.call('eval',source='(define user-p (make-parameter 1)) (user-p 37)'))
        self.assertEqual(text(self.b.call('eval',source='(user-p)')),'37\n')
        r=self.b.call('eval',source='(user-p 42) (error "test")');self.assertEqual(r[-1]['status'],'error')
        self.assertEqual(text(self.b.call('eval',source='(user-p)')),'42\n')
    def test_read_case_parameter_persists(self):
        self.ok(self.b.call('eval',source='(read-case-sensitive #f)'))
        self.ok(self.b.call('eval',source='(define MixedCase 42)'))
        self.assertEqual(text(self.b.call('eval',source='MIXEDCASE')),'42\n')
    def test_custom_readtable_and_reader_persist(self):
        source=r'''(define old-reader (current-read-interaction))
(define (custom-reader src p) (old-reader src p))
(current-read-interaction custom-reader)
(current-readtable (make-readtable #f #\@ 'terminating-macro
  (case-lambda [(ch in) 17]
    [(ch in src line col pos) (datum->syntax #f 17 (list src line col pos 1))])))'''
        self.ok(self.b.call('eval',source=source))
        r=self.b.call('check',source='@');self.ok(r);self.assertTrue(any(e.get('status')=='complete' for e in r))
        self.assertEqual(text(self.b.call('eval',source='@')),'17\n')
        self.assertEqual(text(self.b.call('eval',source='(eq? (current-read-interaction) custom-reader)')),'#t\n')
    def test_custom_printer_persists_and_ports_refresh(self):
        self.ok(self.b.call('eval',source='(define old-printer (current-print)) (define old-output (current-output-port)) (current-print (lambda (v) (display "custom:") (old-printer v)))'))
        r=self.b.call('eval',source='1/3');self.ok(r);self.assertEqual(text(r),'custom:1/3\n')
        r=self.b.call('eval',source='(eq? old-output (current-output-port))');self.assertEqual(text(r),'custom:#f\n')
        r=self.b.call('eval',source='(display "stdout") (eprintf "stderr")');self.ok(r)
        self.assertEqual(text(r,'stdout'),'stdout');self.assertEqual(text(r,'stderr'),'stderr')
        self.assertTrue(all(e['id']==r[-1]['id'] for e in r))
    def test_reserved_ports_refresh_after_user_redirect(self):
        self.ok(self.b.call('eval',source='(current-output-port (open-output-string)) (current-error-port (open-output-string))'))
        r=self.b.call('eval',source='(display "visible") (eprintf "error-visible") 7');self.ok(r)
        self.assertEqual(text(r,'stdout'),'visible');self.assertEqual(text(r,'stderr'),'error-visible');self.assertEqual(text(r),'7\n')
    def test_parameters_survive_break_then_reset_on_run(self):
        self.ok(self.b.run('#lang racket\n(define p (make-parameter 1))'))
        self.ok(self.b.call('eval',source='(p 19) (print-as-expression #f)'))
        i=self.b.send('eval',source='(let loop () (loop))');self.b.next();self.b.send('break')
        self.assertEqual(self.b.until_done(i)[-1]['status'],'interrupted')
        self.assertEqual(text(self.b.call('eval',source='(p)')),'19\n')
        self.assertEqual(text(self.b.call('eval',source='(print-as-expression)')),'#f\n')
        self.ok(self.b.run('#lang racket\n(define p (make-parameter 1))'))
        self.assertEqual(text(self.b.call('eval',source='(p)')),'1\n')
        self.assertEqual(text(self.b.call('eval',source='(print-as-expression)')),'#t\n')
    def test_dependency_changes_reload_across_run(self):
        with tempfile.TemporaryDirectory() as d:
            d=pathlib.Path(d);helper=d/'helper.rkt';source='#lang racket\n(require "helper.rkt")\nx'
            for n in (1,99):
                helper.write_text('#lang racket\n(provide x)\n(define x '+str(n)+')')
                r=self.b.run(source,d,d/'main.rkt');self.ok(r);self.assertEqual(text(r),str(n)+'\n')
    def test_relative_interaction_require(self):
        with tempfile.TemporaryDirectory() as d:
            d=pathlib.Path(d);(d/'helper.rkt').write_text('#lang racket/base\n(provide x)\n(define x 81)')
            self.ok(self.b.run('#lang racket',d,d/'main.rkt'))
            r=self.b.call('eval',source='(require "helper.rkt")\nx');self.ok(r);self.assertEqual(text(r),'81\n')
    def test_main_submodule(self):
        r=self.b.run('#lang racket\n(module+ main (displayln "main ran"))')
        self.ok(r);self.assertEqual(text(r,'stdout'),'main ran\n')
    def test_syntax_and_reader_locations(self):
        r=self.b.run('#lang racket\n(define x (+ 1 2)')
        self.assertEqual(r[-1]['status'],'error');e=errors(r)[0]
        self.assertTrue(e['locations'],e);self.assertEqual(e['locations'][0]['line'],2)
        r=self.b.run('#lang racket\nunknown-variable')
        self.assertEqual(errors(r)[0]['kind'],'syntax');self.assertEqual(errors(r)[0]['locations'][0]['line'],2)
    def test_runtime_locations(self):
        self.ok(self.b.run('#lang racket\n(define (f) (+ 1 (/ 1 0)))'))
        r=self.b.call('eval',source='(f)')
        self.assertEqual(r[-1]['status'],'error');e=errors(r)[0];self.assertTrue(e['locations'])
        self.assertTrue(any(loc['line']==2 for loc in e['locations']),e)
    def test_missing_lang_is_actionable_no_silent_fallback(self):
        r=self.b.run('(define x 7)');self.assertEqual(r[-1]['status'],'error')
        self.assertEqual(errors(r)[0]['kind'],'missing-language');self.assertIn('#lang racket',errors(r)[0]['message'])
    def test_real_reader_completeness(self):
        cases={ '(+ 1':'incomplete','"unfinished':'incomplete','#| unfinished':'incomplete',
          '':'complete', ' \n; comment only':'complete', '42 (+ 1':'incomplete',
          '#| outer #| inner |#':'incomplete', '#;':'incomplete',
          '#; (ignored) (+ 2':'incomplete',
          '(list "(")':'complete', '; (((\n42':'complete', '#\\(':'complete',
          '(]':'error', '(+ 1\n 2)':'complete', '#; (ignored) 4':'complete',
          "'":'incomplete', '#<<END\nhello\n':'incomplete', '#<<END\nhello\nEND\n':'complete'}
        for source,status in cases.items():
            with self.subTest(source=source):
                r=self.b.call('check',source=source)
                self.assertEqual([e['status'] for e in r if e['event']=='check'],[status],r)
                self.assertEqual(r[-1]['status'],'error' if status=='error' else 'ok',r)
                self.assertEqual([e['kind'] for e in errors(r)],['read'] if status=='error' else [],r)
    def test_check_does_not_evaluate_or_change_namespace(self):
        r=self.b.call('check',source='(define checked-only 42) (/ 1 0) (display "not evaluated")')
        self.ok(r);self.assertEqual(text(r,'stdout'),'');self.assertEqual(text(r),'')
        self.assertEqual(self.b.call('eval',source='checked-only')[-1]['status'],'error')
        self.assertEqual(text(self.b.call('eval',source='(+ 1 2)')),'3\n')
    def test_incomplete_eval_keeps_prior_forms_and_recovers(self):
        r=self.b.call('eval',source='(define kept-before-eof 41) (+ kept-before-eof')
        self.assertEqual(r[-1]['status'],'error');self.assertEqual(errors(r)[0]['kind'],'incomplete')
        self.assertEqual(text(self.b.call('eval',source='(+ kept-before-eof 1)')),'42\n')
    def test_error_stops_later_forms_without_rolling_back_prior_forms(self):
        r=self.b.call('eval',source='(define before-error 1) (/ 1 0) (define after-error 2)')
        self.assertEqual(r[-1]['status'],'error');self.assertEqual(errors(r)[0]['kind'],'runtime')
        self.assertEqual(text(self.b.call('eval',source='before-error')),'1\n')
        self.assertEqual(self.b.call('eval',source='after-error')[-1]['status'],'error')
    def test_error_does_not_destroy_namespace(self):
        self.ok(self.b.run('#lang racket\n(define x 77)'))
        self.assertEqual(self.b.call('eval',source='(/ 1 0)')[-1]['status'],'error')
        self.assertEqual(text(self.b.call('eval',source='x')),'77\n')
    def test_standard_input_and_eof(self):
        i=self.b.send('eval',source='(read-line)')
        events=[]
        while True:
            e=self.b.next();events.append(e)
            if e['event']=='input-request':break
        self.b.send('input',text='hello λ\n')
        events+=self.b.until_done(i)
        self.assertEqual(text(events),'"hello λ"\n')
        i=self.b.send('eval',source='(read)')
        while self.b.next()['event']!='input-request':pass
        self.b.send('input',eof=True)
        events=self.b.until_done(i);self.assertEqual(text(events),'#<eof>\n')
    def test_break_tight_loop_and_reuse(self):
        self.ok(self.b.run('#lang racket\n(define kept 17)'))
        i=self.b.send('eval',source='(let loop () (loop))')
        self.assertEqual(self.b.next()['event'],'started')
        start=time.monotonic();interrupt=self.b.send('break');r=self.b.until_done_ids({i,interrupt})
        self.assertLess(time.monotonic()-start,2)
        self.assertEqual({e['id']:e['status'] for e in r if e['event']=='done'},{i:'interrupted',interrupt:'ok'})
        self.assertEqual(sum(e['event']=='done' for e in r),2)
        self.assertFalse(any(e['event']=='ready' for e in r))
        self.assertEqual(text(self.b.call('eval',source='kept')),'17\n')
    def test_disabled_break_cancel_custodian(self):
        i=self.b.send('eval',source='(parameterize-break #f (let loop () (loop)))')
        self.assertEqual(self.b.next()['event'],'started');time.sleep(.05)
        start=time.monotonic();self.b.send('break');r=self.b.until_done(i)
        self.assertLess(time.monotonic()-start,2);self.assertEqual(r[-1]['status'],'interrupted')
        self.assertEqual(text(self.b.call('eval',source='(+ 1 2)')),'3\n')
    def test_infinite_output_is_bounded_and_breakable(self):
        i=self.b.send('eval',source='(let loop () (display "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx") (loop))')
        all_events=[]
        while True:
            e=self.b.next();all_events.append(e)
            if e['event']=='truncated':break
        self.b.send('break');all_events+=self.b.until_done(i)
        self.assertLessEqual(len(text(all_events,'stdout').encode()),262144)
        self.assertEqual(all_events[-1]['status'],'interrupted')
        self.assertEqual(text(self.b.call('eval',source='1/3')),'1/3\n')
    def test_unicode_split_at_chunk_boundary(self):
        r=self.b.call('eval',source='(display (make-string 2000 #\\λ))')
        self.ok(r);self.assertEqual(text(r,'stdout'),'λ'*2000)
        r=self.b.call('eval',source='(for ([b (in-bytes (string->bytes/utf-8 "🍰λ"))]) (write-byte b) (flush-output))')
        self.ok(r);self.assertEqual(text(r,'stdout'),'🍰λ')
    def test_reset_and_process_restart(self):
        self.ok(self.b.call('eval',source='(define lost 42)'))
        self.ok(self.b.call('reset'))
        self.assertEqual(self.b.call('eval',source='lost')[-1]['status'],'error')
        self.b.close();self.b=Bridge();self.assertEqual(text(self.b.call('eval',source='(+ 1 2)')),'3\n')
    def test_reset_clears_module_bindings_and_reader_parameters_without_restart(self):
        self.ok(self.b.run('#lang racket\n(define module-only 17)'))
        self.ok(self.b.call('eval',source='(define repl-only 42) (read-case-sensitive #f) (print-as-expression #f)'))
        pid=self.b.proc.pid
        self.assertEqual([e['event'] for e in self.b.call('reset')],['done'])
        self.assertEqual(self.b.proc.pid,pid);self.assertIsNone(self.b.proc.poll())
        for name in ('module-only','repl-only'):
            self.assertEqual(self.b.call('eval',source=name)[-1]['status'],'error')
        r=self.b.call('eval',source='(values (read-case-sensitive) (print-as-expression))')
        self.ok(r);self.assertEqual(text(r),'#t\n#t\n')
        self.ok(self.b.run('#lang racket/base\n(define fresh 9)'))
        self.assertEqual(text(self.b.call('eval',source='fresh')),'9\n')
    def test_protocol_injection_output_remains_text(self):
        source='(displayln "{\\\"event\\\":\\\"done\\\",\\\"id\\\":999,\\\"status\\\":\\\"ok\\\"}")'
        r=self.b.call('eval',source=source);self.ok(r)
        self.assertIn('999',text(r,'stdout'));self.assertEqual(sum(e['event']=='done' for e in r),1)
    def assert_protocol_frame_rejected(self,frame):
        self.b.proc.stdin.write(frame+'\n');self.b.proc.stdin.flush()
        events=self.b.until_done(None)
        self.assertEqual([e['event'] for e in events],['error','done'],events)
        self.assertTrue(all(e['id'] is None for e in events),events)
        self.assertEqual(events[0]['kind'],'protocol',events)
        self.assertEqual(events[-1]['status'],'error',events)
    def test_malformed_string_escapes_and_nested_json_recover(self):
        frames=[r'{"id":999,"op":"eval","source":"\q"}',
                r'{"id":999,"op":"eval","source":"\u12"}',
                '{"id":999,"op":"eval","source":"literal\tcontrol"}',
                '{"id":999,"op":"eval","source":"unterminated}',
                '{"id":999,"op":"eval","source":"42",}',
                '{"id":999,"op":"eval","source":[1,]}']
        for frame in frames:
            with self.subTest(frame=frame):
                self.assert_protocol_frame_rejected(frame)
                self.assertEqual(text(self.b.call('eval',source='(+ 1 2)')),'3\n')
    def test_trailing_data_cannot_dispatch_reset_or_shutdown(self):
        self.ok(self.b.call('eval',source='(define frame-survivor 17)'))
        for operation in ('reset','shutdown'):
            for suffix in ('{}','[]','false','"tail"','\x00','/* comment */'):
                with self.subTest(operation=operation,suffix=suffix):
                    prefix=json.dumps({'id':999,'op':operation})
                    self.assert_protocol_frame_rejected(prefix+suffix)
                    self.assertIsNone(self.b.proc.poll())
                    self.assertEqual(text(self.b.call('eval',source='frame-survivor')),'17\n')
    def test_exit_is_reported_without_losing_process(self):
        r=self.b.call('eval',source='(exit 5)');self.assertEqual(r[-1]['status'],'error')
        self.assertEqual(text(self.b.call('eval',source='42')),'42\n')
    def test_background_thread_is_killed_by_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            marker=pathlib.Path(d)/'marker'
            src='#lang racket\n(thread (lambda () (sleep 0.3) (call-with-output-file '+json.dumps(str(marker))+' (lambda (p) (display "leaked" p)))))'
            self.ok(self.b.run(src));self.ok(self.b.run('#lang racket\n1'))
            time.sleep(.4);self.assertFalse(marker.exists())
    def test_user_thread_shutdown_reports_error_and_recovers(self):
        for source in ('(kill-thread (current-thread))', '(custodian-shutdown-all (current-custodian))'):
            with self.subTest(source=source):
                r=self.b.call('eval',source=source)
                self.assertEqual(r[-1]['status'],'error');self.assertIn('stopped before completing',errors(r)[0]['message'])
                self.assertEqual(text(self.b.call('eval',source='(+ 1 2)')),'3\n')
    def test_busy_request_does_not_replace_active(self):
        i=self.b.send('eval',source='(sleep 10)');self.b.next()
        r=self.b.call('eval',source='42');self.assertEqual(errors(r)[0]['kind'],'busy')
        self.b.send('break');self.assertEqual(self.b.until_done(i)[-1]['status'],'interrupted')
    def test_long_value_truncates(self):
        r=self.b.call('eval',source='(make-string 400000 #\\a)');self.ok(r)
        self.assertTrue(any(e['event']=='truncated' for e in r))
        self.assertLessEqual(len(text(r).encode()),262144)

if __name__=='__main__':unittest.main(verbosity=2)
