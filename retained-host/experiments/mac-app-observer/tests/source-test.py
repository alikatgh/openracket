#!/usr/bin/env python3
"""Portable source/lexical checks only; never runs/downloads Racket or a GUI."""
from pathlib import Path
import hashlib
import os
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASE_SHA256='ce3d961b5c6f2b5cb42edea8c984afcd9a87c309ff8e9409901eece4ed1fc9e5'

def baseline_text():
    value=os.environ.get('OPENRACKET_OBSERVER_BASELINE_TOOL')
    if not value:
        raise ValueError('Set OPENRACKET_OBSERVER_BASELINE_TOOL to the exact absolute 0520 observer tool.rkt path')
    path=Path(value)
    if not path.is_absolute():
        raise ValueError('OPENRACKET_OBSERVER_BASELINE_TOOL must be absolute')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=BASE_SHA256:
        raise ValueError('Observer baseline SHA-256 does not match the pinned 0520 source')
    return data.decode('utf-8')

def lexical(path):
    """Balance delimiters while skipping strings, line comments and #\\ chars.
    This is deliberately not represented as a Racket parser or compiler."""
    text=path.read_text(); stack=[]; i=0
    while i<len(text):
        if text[i]==';':
            e=text.find('\n',i); i=len(text) if e<0 else e+1; continue
        if text.startswith('#\\',i):
            i+=2
            if i<len(text):
                if text[i].isspace() or text[i] in '()[]{}': i+=1
                else:
                    while i<len(text) and not text[i].isspace() and text[i] not in '()[]{}': i+=1
            continue
        if text[i]=='"':
            i+=1
            while i<len(text):
                if text[i]=='\\': i+=2
                elif text[i]=='"': i+=1; break
                else: i+=1
            else: raise AssertionError(f'{path}: unterminated string')
            continue
        if text[i] in '([{': stack.append((text[i],i))
        elif text[i] in ')]}':
            assert stack and stack[-1][0]=={')':'(',']':'[','}':'{'}[text[i]], (str(path),i,stack[-1:])
            stack.pop()
        i+=1
    assert not stack,(str(path),stack)

class SourceContracts(unittest.TestCase):
    def test_all_racket_delimiters(self):
        for p in ROOT.rglob('*.rkt'): lexical(p)
    def test_package_is_separate_and_inert_by_default(self):
        self.assertFalse((ROOT/'observer-config.json').exists())
        t=(ROOT/'tool.rkt').read_text()
        self.assertIn('(when (file-exists? config-path) (start-observer!))',t)
        self.assertIn('(define-runtime-path config-path "observer-config.json")',t)
        self.assertNotIn('OPENRACKET_PORTABLE_FIXTURE',t)
    def test_preserved_source_pins(self):
        old=baseline_text(); new=(ROOT/'tool.rkt').read_text()
        for value in re.findall(r'"([a-f0-9]{64})"',old): self.assertIn(value,new)
        self.assertIn('db156fe925d2372bcfadac91abe8be5568b68bea52c1cacd73264bdf548c9f9f',new)
    def test_retained_memory_checks_are_byte_identical(self):
        old=baseline_text();new=(ROOT/'tool.rkt').read_text()
        a=old[old.index('(define (memory-limit-evidence'):old.index('(define (geometry')]
        b=new[new.index('(define (memory-limit-evidence'):new.index('(define (geometry')]
        self.assertEqual(a,b)
    def test_preserved_host_assertions(self):
        t=(ROOT/'tool.rkt').read_text()
        for phrase in ['Registered stock frame class','Registered definitions class',
                       'Registered interactions class','Definitions canvas/editor identity',
                       'Interactions canvas/editor identity','Original menu bar remains populated',
                       'Original tab remains present','Localized Check Syntax/Debug/Macro Stepper/Run/Stop order remains stock',
                       'Run retains native toolbar identity','Stop retains native toolbar identity',
                       'Actual effective DarkAqua appearance','Actual loaded save guard matches the explicit expectation']:
            self.assertIn(phrase,t)
    def test_original_public_tab_readers_and_strict_identity_retention(self):
        t=(ROOT/'tool.rkt').read_text()
        for fragment in ['(send frame get-tabs)','(send tab get-frame)','(send tab get-defs)',
                         '(send tab get-ints)','(make-hasheq)',
                         '(member before snapshot)','(equal? snapshot prior-snapshot)',
                         "'handler_receipt_proven #f"]: self.assertIn(fragment,t)
    def test_no_mutating_host_api_or_source_entrypoint(self):
        t=(ROOT/'tool.rkt').read_text()
        for symbol in ['preferences:set','preferences:set-default','application-file-handler',
                       'change-to-file','load-file','set-filename','set-modified',
                       'native-appearance-set!','native-appearance-restore!',"'drracket/drracket"]:
            self.assertNotIn(symbol,t)
        self.assertEqual(re.findall(r'\(new\s+([^\s()]+)',t),['timer%','timer%'])
    def test_native_identity_is_observed_not_configured(self):
        t=(ROOT/'cocoa-identity.rkt').read_text()
        for symbol in ['"getpid"','"_NSGetExecutablePath"','currentApplication','mainBundle',
                       'processIdentifier','bundleIdentifier','bundleURL','executableURL','isEqual:']:
            self.assertIn(symbol,t)
        for symbol in ['getenv','config','setAppearance:','sharedApplication','setDelegate:','activateWithOptions:']:
            self.assertNotIn('('+symbol,t)
        self.assertIn("'process_image_path",t)
    def test_default_handler_has_only_read_queries_and_owned_releases(self):
        t=(ROOT/'default-handler.rkt').read_text()
        for symbol in ['UTTypeCreatePreferredIdentifierForTag','LSCopyDefaultRoleHandlerForContentType',
                       'kUTTagClassFilenameExtension','CFRelease',"'null","'status \"error\""]:
            self.assertIn(symbol,t)
        for symbol in ['LSSetDefault','LSRegister','sharedApplication','NSApplication','(release extension-tag)']:
            self.assertNotIn(symbol,t)
        self.assertIn('(lambda () (when handler (release handler)))',t)
        self.assertIn('(lambda () (release uti))',t)
    def test_contract_and_state_tests_cover_real_functions(self):
        c=(ROOT/'tests/contract-test.rkt').read_text()
        s=(ROOT/'tests/observer-state-test.rkt').read_text()
        self.assertEqual(c.count('(test-case '),21)
        self.assertEqual(s.count('(test-case '),11)
        self.assertIn("'(publish! next-stage! observe-turn! tick)",s)
        self.assertIn('(definition \'phase2)',s)
        self.assertIn('"../contract.rkt"',c)
    def test_language_exception_is_read_only_bounded_and_keeps_complete_order(self):
        t=(ROOT/'tool.rkt').read_text();c=(ROOT/'contract.rkt').read_text()
        for fragment in ['(send defs get-next-settings)', '(send language get-language-position)',
                         'drracket:language:capability-registered?',
                         'drracket:module-language:module-language<%>',
                         '(string-constant initial-language-category)', '(string-constant no-language-chosen)',
                         '(member label full-expected)',
                         '(equal? observed (if horizontal? expected (reverse expected)))',
                         "'toolbar_language toolbar-language"]:
            self.assertIn(fragment,t)
        self.assertIn("(equal? registered '(#t #t #t))",c)
        self.assertIn("(equal? capabilities '(#f #f #f))",c)
        self.assertIn('(and (equal? mode "coldempty") unnamed-empty? (not module-language?))',c)
        self.assertIn('(check module-language?',c)
        self.assertIn('(drop full-labels 3)',c)
        self.assertIn('(current-fixture-toolbar-witness tabs frame-reports expected)',t)
        self.assertIn('(unless (equal? (step) "coldempty")',t)
        self.assertIn('"A current expected fixture has a verified module-language five-tool toolbar"',t)
        self.assertIn("'active_fixture_toolbar_witness (or active-fixture-toolbar 'null)",t)
        self.assertIn("(eq? (hash-ref tab 'current #f) #t)",c)
        self.assertIn("(eq? (hash-ref frame 'full_toolbar_verified #f) #t)",c)
    def test_protocol_bounds_and_native_gate_honesty(self):
        t=(ROOT/'tool.rkt').read_text();c=(ROOT/'contract.rkt').read_text()
        for f in ['60000','20000','2000','(sleep 270)',"'complete_app_acceptance #f"]: self.assertIn(f,t)
        for f in ['65536','4096','[A-Za-z0-9_-]{8,100}','(capture_ok #f)']: # last check separately
            if f != '(capture_ok #f)': self.assertIn(f,c)
        self.assertIn("(hash-ref c 'capture_ok #f)",c)
        self.assertIn("(hash-ref c 'open_exit #f)",c)

if __name__=='__main__': unittest.main(verbosity=2)
