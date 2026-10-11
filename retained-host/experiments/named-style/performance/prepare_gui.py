#!/usr/bin/env python3
"""Pin-checked additive GUI-only observation; no replay/readiness protocol."""
import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path
import subprocess

PINS = {
    'module-language.rkt': 'e76f13b6700df1ce1096f978353c938ef7816672efe9532483ffd38b710ffd53',
    'expanding-place.rkt': 'f6daeb1c8ca26d6f5a3c4c6920cc484f43d5bcd4116aa8d592334f037005a383',
    'syncheck/online-comp.rkt': '1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5',
    'syncheck/gui.rkt': '5aadb13833ad2e4a658c8b5d6a54d08831488a7f05ab84120252f9184667d13e',
}
FLAG = '(equal? (getenv "OPENRACKET_GUI_OBSERVER") "1")'
PHASE_FLAG = '(equal? (getenv "OPENRACKET_GUI_PHASE_POINTS") "1")'


def block(name, body):
    return f'\n;; GUI-OBSERVE-BEGIN {name}\n{body}\n;; GUI-OBSERVE-END {name}\n'


def insert(text, anchor, body, *, after=False):
    if text.count(anchor) != 1:
        raise ValueError(f'Missing or nonunique source anchor: {anchor[:100]}')
    at = text.index(anchor) + (len(anchor) if after else 0)
    return text[:at] + body + text[at:]


def wrap(text, original, before, after, name):
    return insert(insert(text, original, block(name+'-open', before)), original,
                  block(name+'-close', after), after=True)


GUI_PREFIX = block('gui-closure', f'''(define openracket-gui-hook
  (and {FLAG}
       (dynamic-require (string->path (getenv "OPENRACKET_GUI_OBSERVER_SUPPORT")) 'gui-hook)))
(define openracket-current-gui-request-id
  (if openracket-gui-hook
      (dynamic-require (string->path (getenv "OPENRACKET_GUI_OBSERVER_SUPPORT")) 'current-gui-request-id)
      (make-parameter #f)))''')
PHASE_PREFIX = block('phase-closure', f'''(define openracket-phase-hook
  (and {FLAG}
       (dynamic-require (string->path (getenv "OPENRACKET_GUI_PHASE_SUPPORT")) 'phase-hook)))''')


def phase_point(label):
    return block(label, f"(when openracket-phase-hook (openracket-phase-hook '{label}))")


def gui_point(label, current=None):
    arg = '' if current is None else ' ' + current
    return block(label, "(when (and openracket-gui-hook openracket-gui-request-id)\n"
                 f"  (openracket-gui-hook 'point openracket-gui-request-id '{label}{arg}))")


def transform_worker(text):
    text = insert(text, '(provide start)', PHASE_PREFIX)
    # Common identity observation immediately after real registry imports. No wait.
    text = insert(text, '  (let loop ([current-job #f]\n', block('worker-init', f'''(when {FLAG}
  ((dynamic-require (string->path (getenv "OPENRACKET_GUI_OBSERVER_SUPPORT")) 'worker-init!)
   (for/list ([h (in-list handlers)]) (list (handler-key h) (and (handler-monitor-pc h) #t)))
   (preferences:get 'drracket:child-only-memory-limit)))'''))
    text = insert(text, '(define (new-job program-as-string the-source response-pc settings pc-status-expanding-place)',
                  block('job-metadata', "(when openracket-phase-hook\n  (openracket-phase-hook 'begin program-as-string the-source settings\n                         (preferences:get 'drracket:child-only-memory-limit)))"), after=True)
    for number, label in [(9,'09 starting expansion'),(10,'10 finished expansion'),(11,'11 getting handler results'),(12,'12 handlers finished'),(13,'13 compile finished')]:
        text = insert(text, f'         (ep-log-info "expanding-place.rkt: {label}")', phase_point(f'worker-phase-{number:02}'))
    original = """(place-channel-put response-pc (vector 'handler-results
                                                  (vector-ref val+loaded-paths+compiled-bytes 0)
                                                  (vector-ref val+loaded-paths+compiled-bytes 1)
                                                  (vector-ref val+loaded-paths+compiled-bytes 2)))"""
    return wrap(text, original, '(begin0', "(when openracket-phase-hook (openracket-phase-hook 'emit)))", 'terminal-emission')


def transform_monitor(text):
    text = insert(text, '(provide go monitor)', PHASE_PREFIX)
    text = insert(text, '               (define trace (build-trace obj the-source orig-cust path))', phase_point('monitor-build-start'))
    # Exactly one original send-back invocation; preserve its original result.
    text = insert(text, '               (send-back trace))]', phase_point('monitor-built-send-start'))
    text = wrap(text, '(send-back trace)', '(begin0', "(when openracket-phase-hook (openracket-phase-hook 'monitor-send-return)))", 'monitor-send')
    return insert(text, '                (channel-put val (void))', phase_point('monitor-ack'))


REGISTRY = '''       (for/list ([o-e-h (in-list (drracket:module-language-tools:get-online-expansion-handlers))])
         (list (drracket:module-language-tools:online-expansion-handler-mod-path o-e-h)
               (drracket:module-language-tools:online-expansion-handler-id o-e-h)
               (drracket:module-language-tools:online-expansion-handler-monitor? o-e-h)))'''


def transform_language(text):
    # Module-level closure, before original unit instantiation and request callbacks.
    text = insert(text, '#lang racket/base', GUI_PREFIX, after=True)
    text = wrap(text, REGISTRY, '(let ([openracket-actual-registry',
                "])(when openracket-gui-hook (openracket-gui-hook 'registry openracket-actual-registry))\nopenracket-actual-registry)", 'registry')
    text = insert(text, '               (place-channel-put expanding-place to-send)',
                  block('request', "(define openracket-gui-request-id\n  (and openracket-gui-hook (openracket-gui-hook 'request to-send\n                                                (preferences:get 'drracket:child-only-memory-limit))))"))
    text = insert(text, '                 (define res (place-channel-get pc-out))',
                  block('response', "(when (and openracket-gui-hook openracket-gui-request-id)\n  (openracket-gui-hook 'response openracket-gui-request-id res))"), after=True)
    text = insert(text, "                   [(equal? (vector-ref res 0) 'monitor-message)", gui_point('monitor-callback-queue-attempt'), after=True)
    text = insert(text, '''                       (when (getenv "PLTDRPLACEPRINT")
                         (printf "PLTDRPLACEPRINT: got monitor result back from the place\\n"))''', gui_point('monitor-callback-enter'))
    call = '(monitor-status (vector-ref res 1) (vector-ref res 2))'
    text = wrap(text, call, '(parameterize ([openracket-current-gui-request-id openracket-gui-request-id])\n(begin0',
                "(when (and openracket-gui-hook openracket-gui-request-id)\n  (openracket-gui-hook 'point openracket-gui-request-id 'monitor-callback-return))))", 'monitor-callback-scope')
    # Insert after the else token using its full unique suffix to avoid other branches.
    anchor = '''                   [else
                    (queue-callback
                     (λ ()
                       (when (eq? us pending-thread)'''
    at = text.index(anchor) + len('                   [else\n')
    text = text[:at] + gui_point('terminal-callback-queue-attempt') + text[at:]
    text = insert(text, '''                       (when (eq? us pending-thread)
                         (set-pending-thread #f #f))''', gui_point('terminal-callback-enter', '(eq? us pending-thread)'))
    return wrap(text, '(show-results res)', '(begin0',
                "(when (and openracket-gui-hook openracket-gui-request-id)\n  (openracket-gui-hook 'point openracket-gui-request-id 'terminal-callback-return)))", 'terminal-callback-return')


def transform_gui(text):
    text = insert(text, '#lang racket/base', GUI_PREFIX, after=True)
    text = insert(text, '        (define/public (replay-compile-comp-trace defs-text val bx)',
                  block('application-token', "(define openracket-application-token\n  (and openracket-gui-hook (openracket-gui-hook 'application-enter)))"), after=True)
    original = '''               (send defs-text syncheck:update-blue-boxes (send (send defs-text get-tab) get-ints))
               (send defs-text syncheck:update-drawn-arrows)
               (send (send defs-text get-tab) remove-bkg-running-color 'syncheck)
               (set-syncheck-running-mode #f)'''
    # Check live token immediately before stock clears running state, after updates.
    final = '(set-syncheck-running-mode #f)'
    index = text.index(original) + len(original) - len(final)
    opening = block('application-complete-open', "(let ([openracket-live-before-reset?\n       (and openracket-gui-hook openracket-application-token\n            (openracket-gui-hook 'application-live? openracket-application-token (and (unbox bx) #t)))])\n(begin0")
    closing = block('application-complete-close', "(when (and openracket-gui-hook openracket-application-token)\n  (openracket-gui-hook 'application-complete openracket-application-token openracket-live-before-reset?))))")
    text = text[:index]+opening+text[index:index+len(final)]+closing+text[index+len(final):]
    cancelled = '''              [(not (unbox bx))
               ;; if we've been asked to stop (because some new results are ready
               ;; and another trace is running).
               (void)]'''
    text = insert(text, cancelled, '', after=False)  # uniqueness proof
    index = text.index(cancelled) + len(cancelled) - len('(void)]')
    text = text[:index]+block('application-cancel', "(when (and openracket-gui-hook openracket-application-token)\n  (openracket-gui-hook 'application-cancel openracket-application-token #f))")+text[index:]
    return text


TRANSFORMS = {'module-language.rkt': transform_language, 'expanding-place.rkt': transform_worker,
              'syncheck/online-comp.rkt': transform_monitor, 'syncheck/gui.rkt': transform_gui}


def arm_pins(arm):
    if arm not in ('stock', 'candidate'):
        raise ValueError('Unknown source arm')
    # The style candidate never changes any of these four GUI input modules.
    return dict(PINS)


def style_pins():
    metadata = json.loads(Path(__file__).with_name('candidate-source-pins.json').read_bytes())
    if (metadata.get('module') != 'racket/snip/private/style' or
            metadata.get('stock_sha256') != '2e06742f956c3de50847bbb429c400af78303c68e0deba1ebc865a619534bde0' or
            not re.fullmatch(r'[0-9a-f]{64}', str(metadata.get('candidate_sha256', ''))) or
            metadata['candidate_sha256'] == metadata['stock_sha256']):
        raise ValueError('Final owner-approved named-style source pin is pending or invalid')
    return {key: metadata[key] for key in ('stock_sha256', 'candidate_sha256')}


def verify_style_source(path, root, arm):
    path, root = Path(path), Path(root).resolve()
    if (path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or
            path.stat().st_size > 1024 * 1024 or root not in path.resolve().parents or
            hashlib.sha256(path.read_bytes()).hexdigest() != style_pins()[arm + '_sha256']):
        raise ValueError('Actual named-style source is not the pinned independent clone source')
    return {'module': 'racket/snip/private/style', 'source': str(path.resolve()),
            'sha256': style_pins()[arm + '_sha256']}


def undo_transform(text):
    return re.sub(r'\n;; GUI-OBSERVE-BEGIN ([^\n]+)\n.*?\n;; GUI-OBSERVE-END \1\n', '', text, flags=re.S)


def verify_sources(source, root=None, arm='stock'):
    source = source.resolve()
    root = (root or source).resolve()
    original = {}
    for name, pin in arm_pins(arm).items():
        path = source/name
        if path.is_symlink() or path.stat().st_nlink != 1 or root not in path.resolve().parents:
            raise ValueError('Source must be independently cloned within the supplied root')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pin:
            raise ValueError('Unexpected pinned source: '+name)
        original[name] = data.decode()
    return original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm', choices=('stock', 'candidate'), required=True)
    parser.add_argument('--diagnostic-root', type=Path, required=True)
    parser.add_argument('--racket', type=Path, required=True)
    args = parser.parse_args()
    root, racket = args.diagnostic_root.resolve(), args.racket.resolve()
    if root not in racket.parents:
        parser.error('Executable must be inside the independent diagnostic clone')
    expr = '(path->string (collection-file-path "module-language.rkt" "drracket" "private"))'
    found = subprocess.run([str(racket), '-e', expr], capture_output=True, text=True, check=True, timeout=15)
    source = Path(json.loads(found.stdout)).resolve().parent
    original = verify_sources(source, root, args.arm)
    style_expr = '(path->string (collection-file-path "style.rkt" "racket" "snip" "private"))'
    found_style = subprocess.run([str(racket), '-e', style_expr], capture_output=True, text=True, check=True, timeout=15)
    style_source = verify_style_source(Path(json.loads(found_style.stdout)), root, args.arm)
    changed = {name: TRANSFORMS[name](text) for name,text in original.items()}
    for name, text in changed.items():
        if undo_transform(text).encode() != original[name].encode():
            raise ValueError('Additive transform does not undo byte-for-byte: ' + name)
    # Build every transformation successfully before changing any source.
    diffs=[]
    for name,text in changed.items():
        path=source/name
        cache=path.parent/'compiled'
        if cache.is_symlink() or (cache.exists() and root not in cache.resolve().parents):
            raise ValueError('Compiled cache escapes diagnostic clone')
    for name,text in changed.items():
        path=source/name
        path.write_text(text)
        for suffix in ('.zo','.dep'):
            cached=path.parent/'compiled'/(path.name.replace('.','_')+suffix)
            if cached.exists(): cached.unlink()
        diffs.extend(difflib.unified_diff(original[name].splitlines(True),text.splitlines(True),fromfile=args.arm+'/'+name,tofile='gui-observer/'+name))
    (root/'openracket-gui-phase-source.diff').write_text(''.join(diffs))
    here=Path(__file__).resolve().parent
    helpers=[here/name for name in ('gui-observer.rkt','gui-phase.rkt','capture-host.rkt','memory-profile.rkt','activation.rkt','heartbeat.rkt','binding-export.rkt','style-witness.rkt')]
    command=[str(racket),'-l','raco','make']+[str(source/name) for name in changed]+[str(path) for path in helpers]
    manifest={'schema_version':1,'diagnostic_root':str(root),'racket':str(racket),'source_root':str(source),'arm':args.arm,'stock_pins':PINS,'original_pins':arm_pins(args.arm),'diagnostic_sources':{name:hashlib.sha256(text.encode()).hexdigest() for name,text in changed.items()},
              'helpers':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in helpers},'helper_paths':{p.name:str(p) for p in helpers},'style_source':style_source,'compile_command':command,'compiled':False}
    target=root/'openracket-gui-phase-manifest.json'
    target.write_text(json.dumps(manifest,indent=2)+'\n')
    result=subprocess.run(command,capture_output=True,text=True,timeout=240)
    (root/'openracket-gui-phase-compile.log').write_text(result.stdout+result.stderr)
    manifest.update(compiled=result.returncode==0,compile_exit_code=result.returncode)
    target.write_text(json.dumps(manifest,indent=2)+'\n')
    if result.returncode: raise RuntimeError('Native compilation failed')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__': main()
