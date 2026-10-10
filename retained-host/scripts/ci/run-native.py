#!/usr/bin/env python3
"""Bounded native evidence on disposable standard public GitHub runners.

No external credentials, AI services, Actions artifacts, or caches. Screenshot
bytes are bounded test evidence in normal job logs, never a published release.
"""
import base64, hashlib, json, os, pathlib, platform, signal, struct, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.chdir(ROOT)
assert os.environ.get('GITHUB_ACTIONS') == 'true', 'CI only'
assert os.environ.get('GITHUB_REPOSITORY') == 'alikatgh/openracket'
assert os.environ.get('GITHUB_REF') == 'refs/heads/prototype/retained-drracket'
TEMP = pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
RACKET, RACO = os.environ['RACKET'], os.environ['RACO']
REPORT = ROOT/'reports/ci-summary.md'
REPORT.parent.mkdir(exist_ok=True)
STATE = ROOT/'reports/ci-results.json'
ROWS = json.loads(STATE.read_text()) if STATE.exists() else []
PHASE_ROW_START = len(ROWS)
PHASE = sys.argv[1] if len(sys.argv) == 2 else ''
assert PHASE in ('prepare', 'stock', 'overlay', 'modern', 'followon', 'performance', 'profile'), 'Explicit phase required'
START = time.monotonic()


def record(name, ok, detail=''):
    ROWS.append((name, bool(ok), detail))
    STATE.write_text(json.dumps(ROWS, indent=2)+'\n')
    print(f'OPENRACKET_RESULT {name}: {"PASS" if ok else "FAIL"} {detail}', flush=True)
    summary = ['# Retained DrRacket native validation', '',
               f'Commit: {os.environ.get("GITHUB_SHA", "unknown")}',
               f'Runner: {platform.system()} {platform.machine()}, full official Racket 9.3 CS.', '',
               '| Check | Actual outcome | Detail |', '|---|---|---|']
    for n, passed, d in ROWS:
        summary.append(f'| {n} | {"PASS" if passed else "FAIL / unavailable"} | {d.replace(chr(10), " ").replace("|", ";")} |')
    summary += ['', 'These are scoped regressions and launch/render checks. They do not establish complete DrRacket feature parity, input-to-photon latency, accessibility, packaging, or hardware performance.',
                'All default stock tools and editor/evaluator behavior remain enabled. Screenshots contain only the synthetic test document.',
                'PNG evidence, when captured, is encoded losslessly in bounded job-log blocks. No artifact/cache/release upload is performed.',
                f'Elapsed so far: {time.monotonic()-START:.1f} seconds.', '']
    REPORT.write_text('\n'.join(summary))


def environment(mode, purpose):
    env = os.environ.copy()
    env['PLTUSERHOME'] = str(TEMP/f'openracket-{mode}-{purpose}')
    if mode == 'pristine-stock':
        env['PLTADDONDIR'] = os.environ['OPENRACKET_CI_STOCK_ADDON']
        env['RACKET'] = os.environ['OPENRACKET_CI_STOCK_RACKET']
        env['RACO'] = str(pathlib.Path(env['RACKET']).with_name('raco'))
    pathlib.Path(env['PLTUSERHOME']).mkdir(exist_ok=True)
    env['OPENRACKET_UI'] = 'stock' if mode in ('pristine-stock', 'stock-fallback') else 'modern'
    env['OPENRACKET_HOST_THEME'] = '0' if mode in ('pristine-stock', 'stock-fallback') else '1'
    env['OPENRACKET_THEME'] = 'light' if mode == 'modern-light' else 'dark'
    print(f'PROFILE mode={mode} purpose={purpose} preference-home={env["PLTUSERHOME"]} shared-addon={env.get("PLTADDONDIR")}', flush=True)
    return env


def command(name, args, env=None, timeout=120):
    print('\n::group::' + name, flush=True)
    try:
        proc = subprocess.Popen(args, env=env, start_new_session=True)
        result = proc.wait(timeout=timeout)
        ok = result == 0
        record(name, ok, f'exit={result}')
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        ok = False
        record(name, False, f'timeout after {timeout}s')
    finally:
        print('::endgroup::', flush=True)
    return ok


def capture(path, ready):
    report = json.loads(ready.read_text())
    geometry = report.get('geometry', {})
    x, y, w, h = (geometry.get(k) for k in ('x', 'y', 'width', 'height'))
    rectangle = None
    if all(isinstance(v, int) for v in (x, y, w, h)) and x >= 0 and y >= 0 and 640 <= w <= 1600 and 400 <= h <= 1000:
        rectangle = (x, y, w, h)
    if platform.system() == 'Linux':
        args = ['import', '-window', 'root']
        if rectangle:
            args += ['-crop', f'{w}x{h}+{x}+{y}', '+repage']
        args += [str(path)]
    else:
        # Racket/macOS frame coordinates omit native menu/title insets. Capture
        # the full disposable desktop so those coordinate systems cannot clip
        # the retained Stop button or status area. The harness sizes to fit.
        args = ['/usr/sbin/screencapture', '-x']
        args += [str(path)]
    result = subprocess.run(args, timeout=15, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return False, result.stderr.strip()[:300]
    if not path.exists():
        return False, 'OS capture produced no file'
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n' or not 1024 <= len(data) <= 300*1024:
        return False, f'Capture is invalid or outside 1KiB–300KiB evidence bound ({len(data)} bytes)'
    w, h = struct.unpack('>II', data[16:24])
    if w < 640 or h < 400:
        return False, f'Unexpected capture dimensions {w}x{h}'
    return True, f'{w}x{h}, {len(data)} bytes, SHA256 {hashlib.sha256(data).hexdigest()}'


def emit_image(mode, path):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    print(f'OPENRACKET_SCREENSHOT_BEGIN {mode} {len(data)} {digest}', flush=True)
    encoded = base64.b64encode(data).decode('ascii')
    for i in range(0, len(encoded), 3072):
        print(f'OPENRACKET_SCREENSHOT_DATA {mode} {i//3072:04d} {encoded[i:i+3072]}', flush=True)
    print(f'OPENRACKET_SCREENSHOT_END {mode}', flush=True)


def native_host(mode, case=None):
    label = mode if case is None else mode+'-'+case
    env = environment(mode, 'host' if case is None else 'followon-'+case)
    if case is not None:
        assert case in ('stop', 'input-eof', 'wxme', 'check-syntax')
        env['OPENRACKET_NATIVE_CASE'] = case
    ready, done = TEMP/f'{label}-ready.json', TEMP/f'{label}-capture-done'
    env['OPENRACKET_READY_FILE'], env['OPENRACKET_CAPTURE_DONE'] = str(ready), str(done)
    logfile = TEMP/f'{label}-native-host.log'
    screenshot = TEMP/f'{label}-native-host.png'
    print('\n::group::' + label + ' genuine DrRacket host', flush=True)
    captured, capture_detail = False, 'Native host never became ready'
    with logfile.open('w') as log:
        proc = subprocess.Popen([env['RACKET'], 'tests/independent-native-host.rkt'], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + (60 if case else 100)
        while proc.poll() is None and time.monotonic() < deadline:
            if ready.exists():
                try:
                    captured, capture_detail = capture(screenshot, ready)
                except (OSError, subprocess.TimeoutExpired) as error:
                    capture_detail = str(error)
                done.write_text('capture attempted\n')
                break
            time.sleep(.2)
        try:
            result = proc.wait(timeout=max(1, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            if not ready.exists():
                ready.write_text(json.dumps({'status': 'timeout-diagnostic', 'reported_by': 'CI watchdog', 'geometry': {}}))
                try:
                    captured, capture_detail = capture(screenshot, ready)
                except (OSError, subprocess.TimeoutExpired) as error:
                    capture_detail = str(error)
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            result = 124
    print(logfile.read_text(), flush=True)
    passed = result == 0 and ready.exists() and json.loads(ready.read_text()).get('status') == 'passed'
    record(label + ' genuine host/editor assertions', passed, f'exit={result}; report-status={json.loads(ready.read_text()).get("status") if ready.exists() else "absent"}')
    if ready.exists() and captured:
        label = label if passed else label+('-timeout-diagnostic' if result == 124 else '-failure-diagnostic')
        emit_image(label, screenshot)
        record(label + ' OS screenshot capture', True, capture_detail)
    else:
        record(label + ' OS screenshot capture', False, capture_detail)
    print('::endgroup::', flush=True)
    return passed


def widgets(mode):
    env = environment(mode, 'widgets')
    code = '''(require racket/string)
(define pref (path->string (find-system-path 'pref-file)))
(define addon (path->string (find-system-path 'addon-dir)))
(printf "ACTUAL_PROFILE pref-file=~a addon-dir=~a\\n" pref addon)
(unless (and (string-prefix? pref (string-append (getenv "PLTUSERHOME") "/"))
             (equal? (string-trim addon "/" #:left? #f) (getenv "PLTADDONDIR")))
  (error 'profile "Fresh preference isolation/shared addon registry mismatch"))'''
    if not command(mode + ' actual profile separation', [RACKET, '-e', code], env):
        raise RuntimeError('Preference profile isolation failed')
    command(mode + ' native toolbar behavior', [RACO, 'test', 'tests/native-toolbar-test.rkt', 'tests/independent-native-toolbar.rkt'], env, 90)
    if mode in ('modern-light', 'modern-dark'):
        command(mode + ' native canvas and status preservation', [RACO, 'test', 'design/native-chrome-test.rkt'], env, 90)


def performance(mode):
    # Populated with the frozen independent performance runner before publication.
    script = ROOT/'performance/run.py'
    if script.exists():
        command(mode + ' paired native performance', [sys.executable, str(script), '--mode', mode, '--racket', os.environ['OPENRACKET_CI_STOCK_RACKET'] if mode == 'pristine-stock' else RACKET, '--output', str(ROOT/'reports'/('performance-'+mode)), '--repetitions', '3', '--timeout', '60'], environment(mode, 'performance'), 420)


def prepare():
    record('CI guard and runtime paths', True, 'Exact public prototype branch; ephemeral full distribution')
    if not command('Record pristine runtime source hashes', [sys.executable, 'scripts/ci/verify-runtime-isolation.py', 'baseline']):
        raise RuntimeError('Pristine runtime baseline failed')
    if not command('Generate exact-version source overlay', [sys.executable, 'scripts/prepare-overlay.py']):
        raise RuntimeError('Overlay generation failed')
    command('Python patch integrity', [sys.executable, 'tests/patcher-test.py'])
    command('Independent patch integrity', [sys.executable, 'tests/independent-patcher-test.py'])
    headless = ['tests/source-preservation.rkt', 'tests/paint-test.rkt', 'tool/tests.rkt', 'performance/lifecycle-test.rkt']
    headless += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'tool').glob('*-tests.rkt'))]
    headless += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'tests').glob('independent-*.rkt')) if 'native' not in p.name]
    command('Headless preservation and renderer', [RACO, 'test'] + headless, environment('pristine-stock', 'headless'))
    command('Performance harness and fixture unit tests', [sys.executable, 'performance/test_harness.py'])


def overlay():
    global RACKET, RACO
    if not command('Copy pristine runtime for presentation overlay', [sys.executable, 'scripts/ci/copy-pristine-runtime.py'], timeout=180):
        raise RuntimeError('Disposable runtime copy failed')
    pristine = pathlib.Path(os.environ['OPENRACKET_CI_INSTALL'])
    modern = pristine.with_name(pristine.name+'-modern')
    RACKET, RACO = str(modern/'bin/racket'), str(modern/'bin/raco')
    os.environ.update(RACKET=RACKET, RACO=RACO, OPENRACKET_CI_INSTALL=str(modern))
    if not command('Apply exact-SHA disposable overlay', [sys.executable, 'scripts/ci/apply-disposable-overlay.py']):
        raise RuntimeError('Overlay apply failed')
    if not command('Register appearance tool locally', [RACO, 'pkg', 'install', '--scope', 'user', '--deps', 'fail', '--no-setup', '--link', '--name', 'openracket-appearance', str(ROOT/'tool')], environment('modern-dark', 'setup')):
        raise RuntimeError('Appearance registration failed')
    if not command('Compile real GUI and register appearance metadata', [RACO, 'setup', '--no-docs', '--pkgs', 'gui-lib', 'openracket-appearance'], environment('modern-dark', 'setup'), 360):
        raise RuntimeError('Real GUI compilation failed')
    if not command('Compile actual theme tool and DrRacket host', [RACO, 'make', 'tool/tool.rkt', 'tests/independent-native-host.rkt', 'tests/independent-native-toolbar.rkt', 'tests/independent-native-workflows.rkt'], environment('modern-dark', 'setup'), 180):
        raise RuntimeError('Actual theme/tool compilation failed')
    if not command('Compile retained DrRacket entrypoint', [RACO, 'make', '-l', 'drracket/drracket'], environment('modern-dark', 'setup'), 180):
        raise RuntimeError('Retained DrRacket compilation failed')
    if not command('Verify actual runtime isolation and unchanged pristine hashes', [sys.executable, 'scripts/ci/verify-runtime-isolation.py', 'compare']):
        raise RuntimeError('Runtime copies are not isolated')


try:
    if PHASE == 'prepare':
        prepare()
    elif PHASE == 'stock':
        command('Prepare synthetic legacy startup diagnostic fixture', [sys.executable, 'performance/fixtures.py', 'reports/startup-diagnostic-fixtures'])
        command('Record legacy startup dialog (observation only)', [RACKET, 'performance/diagnose-startup.rkt', str(ROOT/'reports/startup-diagnostic-fixtures/mixed-100k.rkt'), str(ROOT/'reports/legacy-startup-diagnostic.json'), 'pristine-stock', '49938', '100000'], environment('pristine-stock', 'legacy-diagnostic'), 20)
        widgets('pristine-stock')
        native_host('pristine-stock')
    elif PHASE == 'overlay':
        overlay()
    elif PHASE == 'modern':
        for mode in ('stock-fallback', 'modern-light', 'modern-dark'):
            widgets(mode)
            native_host(mode)
        command('Verify pristine source unchanged after overlay tests', [sys.executable, 'scripts/ci/verify-runtime-isolation.py', 'compare'])
    elif PHASE == 'followon':
        cases = ('stop', 'input-eof', 'wxme', 'check-syntax')
        baselines = {case: native_host('pristine-stock', case) for case in cases}
        for case in cases:
            if baselines[case]:
                native_host('modern-dark', case)
            else:
                record('modern-dark-'+case+' comparative preservation', False,
                       'Not run: corresponding pristine-stock case failed; no overlay attribution')
        command('Verify pristine source unchanged after preservation workflows', [sys.executable, 'scripts/ci/verify-runtime-isolation.py', 'compare'])
    elif PHASE == 'performance':
        performance('pristine-stock')
        performance('modern-dark')
        command('Verify pristine source unchanged after measurements', [sys.executable, 'scripts/ci/verify-runtime-isolation.py', 'compare'])
    elif PHASE == 'profile':
        command('Pristine stock attribution diagnostic (instrumented, not acceptance timing)',
                [sys.executable, 'performance/run.py', '--mode', 'pristine-stock',
                 '--racket', os.environ['OPENRACKET_CI_STOCK_RACKET'],
                 '--output', str(ROOT/'reports/stock-attribution'), '--fixture', 'mixed-1mib',
                 '--repetitions', '1', '--timeout', '90', '--profile'],
                environment('pristine-stock', 'attribution'), 120)
        command('Verify pristine source unchanged after attribution', [sys.executable, 'scripts/ci/verify-runtime-isolation.py', 'compare'])
except Exception as error:
    record(PHASE + ' validation orchestration', False, str(error))
    raise
finally:
    print('Results: ' + str(REPORT), flush=True)

# A denied/unavailable OS capture is disclosed and does not mask test failures.
failures = [n for n, ok, _ in ROWS[PHASE_ROW_START:] if not ok and not n.endswith('OS screenshot capture')]
sys.exit(1 if failures else 0)
