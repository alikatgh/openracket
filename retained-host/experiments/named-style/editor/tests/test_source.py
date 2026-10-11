"""Static source checks only; never imports/executes Racket or changes runtimes."""
from pathlib import Path
import hashlib
import json
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import compare

def balanced(text):
    """Delimiter lint for these three ordinary Racket files, not a Racket parser.
    Handles comments, strings, regexp/bytes string prefixes, and character data.
    Passing this is deliberately not called compilation or macro expansion.
    """
    stack=[]; i=0; line=1
    while i<len(text):
        c=text[i]
        if c=='\n': line+=1; i+=1; continue
        if c==';':
            i=text.find('\n',i)
            if i<0: break
            continue
        if text.startswith('#|',i):
            depth=1; i+=2
            while depth and i<len(text):
                if text.startswith('#|',i): depth+=1; i+=2
                elif text.startswith('|#',i): depth-=1; i+=2
                else:
                    line+=text[i]=='\n'; i+=1
            if depth: raise AssertionError("unterminated block comment")
            continue
        if text.startswith('#\\',i):
            i+=2
            if i<len(text):
                i+=1
                while i<len(text) and (text[i].isalnum() or text[i] in '-'): i+=1
            continue
        if c=='"':
            i+=1
            while i<len(text) and text[i]!='"':
                if text[i]=='\\': i+=2
                else: line+=text[i]=='\n'; i+=1
            if i==len(text): raise AssertionError("unterminated string")
            i+=1; continue
        if c in '([{': stack.append((c,line))
        elif c in ')]}':
            if not stack or {'(':')','[':']','{':'}'}[stack[-1][0]]!=c:
                raise AssertionError(f"delimiter mismatch on line {line}: {stack[-1:]}")
            stack.pop()
        i+=1
    if stack: raise AssertionError(f"unclosed delimiters {stack}")
    return True

class SourceTests(unittest.TestCase):
    def test_native_delimiter_lint(self):
        for path in (ROOT/"native").glob("*.rkt"):
            with self.subTest(path=path.name): self.assertTrue(balanced(path.read_text()))
    def test_bootstrap_actual_runtime_source_before_gui(self):
        s=(ROOT/"native/bootstrap.rkt").read_text()
        self.assertLess(s.index('(parameterize ([use-compiled-file-paths'),s.index("(dynamic-require gate-path"))
        for anchor in ("resolve-module-path module-name", "(module->namespace resolved)",
                       "(eq? already-loaded-namespace (module->namespace resolved))",
                       "(define missing (gensym", "(lambda () missing)", "private-list%"):
            self.assertIn(anchor,s)
        self.assertNotIn('(require racket/gui',s)
        self.assertNotIn('dynamic-require source',s)
        self.assertNotIn('namespace-attach-module',s)
    def test_actual_framework_editor_no_color_simulation(self):
        s=(ROOT/"native/editor-gate.rkt").read_text()
        for anchor in ("(class racket:text%", "(new editor-canvas%", "(send frame show #t)",
                       "(send t get-style-list)", "(is-a? sl private-list%)",
                       "(if state (state sl) 'null)", "(send t is-lexer-valid?)",
                       "(send t get-token-range p)", "(send t classify-position p)",
                       "(send t forward-match p n)", "(send t backward-match p 0)",
                       "(yield (alarm-evt", "(send rich save-file path 'standard)",
                       "(send restored load-file path 'standard)", "(send bitmap set-argb-pixels",
                       "same-identities! original-snips", "same-identities! original-styles",
                       "(make-eventspace)", "(original-error-display message e)",
                       "(record! 'gui_callback_errors callback-errors)") :
            self.assertIn(anchor,s)
        # Comment mentions the forbidden shortcut; executable calls must not.
        for forbidden in ("(send t start-colorer","(send t freeze-colorer","(send t force-stop-colorer",
                          "(send t stop-colorer","(send t set-style-list","(send sl find-named-style"):
            self.assertNotIn(forbidden,s[s.index("(define (run-on-handler!"):])
        before=s.index("(define initial-diagnostics")
        insert=s.index("(send t insert original)",before)
        self.assertLess(before,insert)
    def test_public_style_index_graph_not_first_seen_ids(self):
        s=(ROOT/"native/snapshot.rkt").read_text()
        for anchor in ("(send sl number)", "(send sl index-to-style i)", "(send sl style-to-index s)",
                       "(send s get-base-style)", "(send s get-shift-style)", "(send s get-delta delta)",
                       "(send s get-style)", "(send s next)", "'shared_style_list"):
            self.assertIn(anchor,s)
        self.assertNotIn("(sort",s)
        self.assertNotIn("remove-duplicates",s)
    def test_fixture_search_has_explicit_scope_and_native_negative_controls(self):
        s=(ROOT/"native/editor-gate.rkt").read_text()
        for anchor in ("(send t find-string query 'forward 0 'eof)",
                       "(send t find-string query 'forward length 'eof)",
                       "(send t find-string absent-query 'forward 0 'eof)",
                       "(define default-target (send t find-string query))",
                       "(send t get-start-position)", "(send t get-end-position)",
                       "(same! selection-start length", "(same! selection-end length",
                       "(same! default-target #f", "(same! eof-target #f", "(same! absent-target #f",
                       "(same! found-text query", "(define target (fixture-target! t record!))"):
            self.assertIn(anchor,s)
        # The only cursor-dependent lookup is an intentional negative control.
        calls=[line.strip() for line in s.splitlines() if "(send t find-string " in line]
        self.assertEqual(len(calls),4)
        self.assertEqual([line for line in calls if "'forward" not in line],
                         ["(define default-target (send t find-string query))"])
        self.assertLess(s.index("(record! 'fixture_search"),s.index("(same! selection-start length"))
        self.assertLess(s.index("(record! 'initial initial)"),s.index("(define target (fixture-target! t record!))"))
        self.assertIn('(string-length "#lang racket/base\\n(define café ")',s)
        self.assertEqual(len("#lang racket/base\n(define café "),compare.ORIGINAL.index('"λ"'))
    def test_pinned_search_and_insert_contract_explains_caret_scope(self):
        s=(ROOT/"vendor/text-class.scrbl").read_text()
        for anchor in ("[start (or/c exact-nonnegative-integer? 'start) 'start]",
                       "starts at the start of the selection", "selection is left at the end",
                       "If the string is not found, @racket[#f] is returned"):
            self.assertIn(anchor,s)
    def test_dependencies_match_vendored_official_bytes(self):
        mapping={"framework/private/color":"color.rkt","framework/private/racket":"racket.rkt",
                 "mred/private/wxme/editor":"editor.rkt","mred/private/wxme/editor-snip":"editor-snip.rkt",
                 "mred/private/wxme/editor-snip-class":"editor-snip-class.rkt"}
        for module,name in mapping.items():
            self.assertEqual(hashlib.sha256((ROOT/"vendor"/name).read_bytes()).hexdigest(),compare.DEPENDENCY_PINS[module])
    def test_official_style_pin(self):
        self.assertEqual(hashlib.sha256((ROOT/"vendor/style.rkt").read_bytes()).hexdigest(),compare.STOCK_SHA)
    def test_official_style_and_mode_source_anchors(self):
        style=(ROOT/"vendor/style.rkt").read_text()
        racket=(ROOT/"vendor/racket.rkt").read_text()
        editor=(ROOT/"vendor/editor.rkt").read_text()
        color=(ROOT/"vendor/color.rkt").read_text()
        self.assertIn('(def/public (find-named-style [string? name])',style)
        self.assertIn('(list-ref members (- member-count i 1))',style)
        self.assertIn('(set-surrogate (new text-mode%))',racket)
        self.assertIn('(get-token (wrap-get-token module-lexer/waived',racket)
        self.assertIn('(token-sym->style short-sym->style-name)',racket)
        self.assertIn('(format "framework:syntax-color:scheme:~a"',racket)
        self.assertIn('(send (get-style-list) find-named-style style-name)',color)
        self.assertIn('(set-style-list new-list)',editor)
        self.assertIn('(read-styles-from-file s-style-list',editor)
    def test_public_documents_cover_operations(self):
        docs={p.name:p.read_text() for p in (ROOT/"vendor").glob("*.scrbl")}
        for term,name in (("(set-style-list","editor-intf.scrbl"),("(save-file","editor-intf.scrbl"),
                          ("(load-file","editor-intf.scrbl"),("(get-token-range","color.scrbl"),
                          ("(is-lexer-valid?","color.scrbl"),("(find-snip","text-class.scrbl"),
                          ("(get-margin","editor-snip-class.scrbl"),("(get-inset","editor-snip-class.scrbl"),
                          ("(get-style)","snip-class.scrbl"),("(get-base-style)","style-intf.scrbl")):
            self.assertIn(term,docs[name])
    def test_runner_does_not_install_or_publish(self):
        s=(ROOT/"scripts/run_native.py").read_text()
        for term in ("--authorize-native-execution","stdout.bin","stderr.bin","TimeoutExpired","process.json"):
            self.assertIn(term,s)
        for forbidden in ("urllib","curl","requests.","raco","git push","overlay.apply","write_bytes(candidate"):
            self.assertNotIn(forbidden,s)

if __name__=="__main__": unittest.main()
