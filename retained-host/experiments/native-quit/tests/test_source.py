"""Source checks and lexical balance only; not a Racket compiler or native run."""
import ast,hashlib,json,os,pathlib,re,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def lexical(p):
    s=p.read_text();stack=[];i=0
    while i<len(s):
        if s[i]==';':
            end=s.find('\n',i);i=len(s) if end<0 else end+1;continue
        if s.startswith('#\\',i):
            i+=2
            if i<len(s):
                if s[i].isspace() or s[i] in '()[]{}':i+=1
                else:
                    while i<len(s) and not s[i].isspace() and s[i] not in '()[]{}':i+=1
            continue
        if s[i]=='"':
            i+=1
            while i<len(s):
                if s[i]=='\\':i+=2
                elif s[i]=='"':i+=1;break
                else:i+=1
            else:raise AssertionError('Unterminated string '+str(p))
            continue
        if s[i] in '([{':stack.append(s[i])
        elif s[i] in ')]}':
            assert stack and stack.pop()=={')':'(',']':'[','}':'{'}[s[i]],(p,i)
        i+=1
    assert not stack,(p,stack)
class Source(unittest.TestCase):
    def setUp(self):self.s=(ROOT/'driver/tool.rkt').read_text();self.runner=(ROOT/'scripts/run-case.py').read_text()
    def test_racket_lexical_balance(self):
        for p in ROOT.rglob('*.rkt'):lexical(p)
    def test_python_ast_parse(self):
        for p in ROOT.rglob('*.py'):ast.parse(p.read_text(),str(p))
    def test_inert_separate_tool(self):
        self.assertIn('(when (file-exists? config-path) (start!))',self.s)
        self.assertFalse((ROOT/'driver/quit-config.json').exists())
        self.assertIn('test_actor #t',self.s)
    def test_only_get_original_quit_handler_and_no_direct_save(self):
        calls=re.findall(r'\(application-quit-handler\s*([^)]*)\)',self.s)
        self.assertTrue(calls);self.assertEqual(set(calls),{''})
        for text in ('preferences:set','set-modified','set-filename','load-file','save-file','custodian-shutdown-all','make-eventspace','(send frame show #f)','(send frame on-close)','(send frame can-close?)'):
            self.assertNotIn(text,self.s)
    def test_failure_only_explicit_exit(self):
        self.assertEqual(re.findall(r'\(exit\s+([^)]*)\)',self.s),['2'])
        failure=self.s[self.s.index('(define (fail!'):self.s.index('(define (gui!')]
        self.assertIn('(exit 2)',failure);self.assertLess(failure.index('"failure.json"'),failure.index('(exit 2)'))
        terminal=self.s[self.s.index('(define (terminal!'):self.s.index('(define (after-capture!')]
        self.assertNotIn('(exit',terminal)
    def test_genuine_modal_commands_and_bound_frame(self):
        for text in ('(send button command (new control-event% [event-type \'button]))','(send d get-message)','(send d get-parent)','(eq? request-frame frame)','(not (memq d request-windows))','"Same screenshot-acknowledged shown modal"','"Persistence checkbox remains unchecked"'):
            self.assertIn(text,self.s)
        self.assertNotIn('(send cb set-value',self.s)
    def test_cancel_focus_is_observed_not_forced(self):
        cancelled=self.s[self.s.index('[(cancelled)'):self.s.index('[else (error \'native-quit-driver "Unexpected timer state")')]
        self.assertIn('(eq? (get-top-level-focus-window) frame)',cancelled)
        self.assertIn('(eq? (get-top-level-edit-target-window) frame)',cancelled)
        self.assertIn('1000',cancelled);self.assertNotIn('(send dc focus)',cancelled);self.assertNotIn('(send frame show',cancelled)
    def test_unchanged_identity_and_input_sources(self):
        pin=json.loads((ROOT/'reports/INPUT-PINS.json').read_text());base=pathlib.Path(os.environ.get('OPENRACKET_QUIT_BASELINE_ROOT',pin['base']))
        self.assertTrue(base.is_absolute())
        for name,h in pin['files'].items():self.assertEqual(hashlib.sha256((base/name).read_bytes()).hexdigest(),h,name)
        expected=pin['files']['experiments/mac-app-observer/cocoa-identity.rkt']
        self.assertEqual(hashlib.sha256((ROOT/'driver/cocoa-identity.rkt').read_bytes()).hexdigest(),expected)
    def test_source_chain_complete(self):
        rows=json.loads((ROOT/'driver/source-pins.json').read_text());names={r['module'] for r in rows}
        self.assertEqual(len(names),11)
        for n in ('mred/private/app.rkt','mred/private/wxtop.rkt','framework/private/editor-misc.rkt','framework/gui-utils.rkt','mred/private/messagebox.rkt','drracket/private/unit.rkt'):self.assertIn(n,names)
    def test_supervisor_no_open_or_success_cleanup(self):
        self.assertNotIn("'/usr/bin/open'",self.runner);self.assertIn('start_new_session=True',self.runner)
        self.assertIn('returncode=p.wait(timeout=deadline-time.monotonic())',self.runner)
        self.assertIn('cleanup_used=False,failure_seen=failure_seen',self.runner)
        self.assertLess(self.runner.index("fresh_json(root/'supervisor-failure.json'"),self.runner.index("failure['cleanup']=failure_cleanup"))
        self.assertIn('deadline=start+150',self.runner)
    def test_actual_racket_contract_tests_not_marked_executed(self):
        self.assertEqual((ROOT/'tests/contract-test.rkt').read_text().count('(test-case '),8)
        self.assertIn('NOT RUN locally',(ROOT/'tests/contract-test.rkt').read_text())
if __name__=='__main__':unittest.main(verbosity=2)
