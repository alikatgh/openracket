#!/usr/bin/env python3
"""Six isolated stock/modern-light tool gates. Native execution is CI-only."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import time


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Runner:
    def __init__(self):
        if sys.flags.optimize:
            raise RuntimeError('Optimized Python disables required gates')
        assert os.environ.get('GITHUB_ACTIONS') == 'true'
        assert os.environ.get('GITHUB_REPOSITORY') == 'alikatgh/openracket'
        assert os.environ.get('GITHUB_REF') == 'refs/heads/prototype/retained-drracket'
        assert platform.system() == 'Darwin'
        self.root = Path(__file__).resolve().parents[2]
        os.chdir(self.root)
        self.ci = self.root / 'scripts/ci'
        self.temp = Path(os.environ['RUNNER_TEMP']).resolve()
        self.stock = Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
        assert self.stock.is_relative_to(self.temp) and self.stock != self.temp
        self.modern = self.stock.with_name(self.stock.name + '-native-light-tools')
        self.exp = self.root / 'experiments/native-light-tool-gates'
        self.proof = self.temp / 'OpenRacket Native Light Tool Proof'
        self.profile = self.proof / 'profile'
        self.addon = self.profile / '.local/share/racket'
        self.cache = self.profile / 'compiled-cache'
        self.reports = self.root / 'reports/light-tools-ci'
        self.reports.mkdir(parents=True, exist_ok=True)
        self.state = self.reports / 'results.json'
        self.rows = json.loads(self.state.read_text()) if self.state.exists() else []
        self.start = len(self.rows)
        self.app = module('app_contract', self.ci / 'app-ci-contract.py')
        self.contract = module('light_contract', self.ci / 'light-ci-contract.py')
        self.contract.frozen_sources(self.exp)
        self.verifier = module('light_verifier', self.exp / 'scripts/validate-light-tool-result.py')
        sys.path.insert(0, str(self.root / 'performance'))
        from run import terminate_group, live_group_members
        self.terminate_group = terminate_group
        self.live_group_members = live_group_members
        self.launches_blocked = False
        self.command_index = len(list(self.reports.glob('command-*')))

    def record(self, name, ok, detail=''):
        row = {'name': name, 'passed': bool(ok), 'detail': str(detail)}
        self.rows.append(row)
        self.state.write_text(json.dumps(self.rows, indent=2) + '\n')
        print('OPENRACKET_LIGHT_TOOLS_RESULT ' + json.dumps(row), flush=True)
        lines = ['# Actual stock and modern-light native tools', '',
                 'Six stock-first isolated cases with fresh stock-default128 profiles, separate official addon registration, all15 native reader/compile checks and nine direct headless controls per runtime.', '',
                 '| Gate | Outcome | Detail |', '|---|---|---|']
        lines += ['| ' + r['name'] + ' | ' + ('PASS' if r['passed'] else 'FAIL / incomplete') + ' | ' + r['detail'].replace('|', ';').replace('\n', ' ') + ' |' for r in self.rows]
        lines += ['', 'Native acceptance ends at the unchanged60-second observed-completion deadline. Diagnostics never turn a timeout into success. Stock failure blocks only its corresponding modern case; later independent cases continue.',
                  'No performance claim, memory increase, normal-Quit claim, or dark-mode claim is made. Synthetic adapter tests are not native evidence.']
        (self.reports / 'summary.md').write_text('\n'.join(lines) + '\n')

    def env(self, label, modern=False, setup=False):
        home = self.profile if setup else self.temp / ('light-tools-' + label)
        addon = self.addon if setup else home / 'addon'
        cache = self.cache if setup else home / 'compiled'
        return self.app.environment(os.environ, (self.modern if modern else self.stock) / 'bin/racket', home, addon, cache)

    def emit_file(self, path, label):
        folder = self.reports / ('evidence-' + label)
        folder.mkdir(exist_ok=True)
        wrapped = folder / 'supervisor.json'
        wrapped.write_text(json.dumps(self.contract.wrap_bytes(path)) + '\n')
        subprocess.run([sys.executable, str(self.ci / 'emit-replay-evidence.py'), str(wrapped)], check=True, timeout=30)

    def command(self, name, args, environment=None, timeout=120, required=True):
        self.command_index += 1
        folder = self.reports / ('command-%03d' % self.command_index)
        folder.mkdir()
        argv = [str(x) for x in args]
        print('::group::' + name, flush=True)
        timed_out = False
        p = subprocess.Popen(argv, env=environment or self.env('checks'), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self.terminate_group(p)
            stdout, stderr = p.communicate(timeout=5)
        evidence = {'name': name, 'argv': argv, 'exit_code': p.returncode, 'timed_out': timed_out,
                    'timeout_seconds': timeout, 'stdout': stdout, 'stderr': stderr}
        for stream in ('stdout', 'stderr'):
            (folder / (stream + '.txt')).write_text(evidence[stream])
        (folder / 'supervisor.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(stdout, end='', flush=True)
        print(stderr, end='', file=sys.stderr, flush=True)
        self.emit_file(folder / 'supervisor.json', folder.name)
        ok = p.returncode == 0 and not timed_out
        self.record(name, ok, 'exit=' + str(p.returncode) + '; timed_out=' + str(timed_out))
        print('::endgroup::', flush=True)
        if not ok and required:
            raise RuntimeError(name + ' failed')
        return evidence

    def tree(self, operation, root, label, required=True):
        witness = self.temp / ('light-tools-' + label + '-tree.json')
        evidence = self.command(label + ' entire runtime ' + operation,
                                [sys.executable, self.ci / 'runtime-tree-check.py', operation, root, witness],
                                timeout=180, required=required)
        ok = evidence['exit_code'] == 0 and not evidence['timed_out']
        if witness.exists() and operation == 'baseline':
            destination = self.reports / (label + '-baseline-tree.json')
            shutil.copy2(witness, destination)
            self.emit_tree_summary(destination, label + '-baseline')
        elif operation == 'compare' and not ok and witness.exists():
            # Preserve a complete final local witness and every changed path;
            # the original comparator's first30 lines are only its quick summary.
            final = self.temp / ('light-tools-' + label + '-final-tree.json')
            after = self.command(label + ' full failed-comparison witness',
                                 [sys.executable, self.ci / 'runtime-tree-check.py', 'baseline', root, final],
                                 timeout=180, required=False)
            if after['exit_code'] == 0 and not after['timed_out']:
                destination = self.reports / (label + '-final-tree.json')
                shutil.copy2(final, destination)
                self.emit_tree_summary(destination, label + '-final')
                before_entries = json.loads(witness.read_text())['entries']
                after_entries = json.loads(final.read_text())['entries']
                changes = [{'path': name, 'before': before_entries.get(name), 'after': after_entries.get(name)}
                           for name in sorted(set(before_entries) | set(after_entries))
                           if before_entries.get(name) != after_entries.get(name)]
                changed = self.reports / (label + '-all-runtime-changes.json')
                changed.write_text(json.dumps({'changed_count': len(changes), 'changes': changes}, indent=2) + '\n')
                self.emit_file(changed, label + '-all-runtime-changes')
        return ok

    def emit_tree_summary(self, path, label):
        # Complete26838-entry snapshots remain local on the runner. Logging both
        # adds substantial evidence cost without a new acceptance gate.
        raw = path.read_bytes()
        witness = json.loads(raw)
        summary = self.reports / (label + '-tree-summary.json')
        summary.write_text(json.dumps({'local_witness': str(path), 'bytes': len(raw),
                                       'sha256': hashlib.sha256(raw).hexdigest(),
                                       'root': witness['root'], 'entries': len(witness['entries']),
                                       'tree_sha256': witness['tree_sha256'],
                                       'complete_witness_retained_locally': True}, indent=2) + '\n')
        self.emit_file(summary, label + '-tree-summary')

    def fresh_modern_addon(self, label, e):
        home = Path(e['PLTUSERHOME'])
        addon = Path(e['PLTADDONDIR'])
        assert not addon.exists() and not addon.is_symlink(), 'Only an absent fresh addon may be registered'
        home.mkdir(exist_ok=True)
        prepared = self.env('prepared-source-query', True, True)
        query = '(require pkg/lib)(define p (pkg-directory "openracket-gui-lib"))(unless p (error "Prepared GUI package missing"))(display p)'
        source = Path(subprocess.check_output([prepared['RACKET'], '-A', prepared['PLTADDONDIR'], '-R', prepared['PLTCOMPILEDROOTS'], '-e', query], env=prepared, text=True, timeout=30)).resolve()
        assert source.is_dir() and not source.is_symlink() and source.is_relative_to(self.addon.resolve())
        patch = json.loads((self.proof / 'reports/patch-manifest.json').read_text())
        for relative, pin in (('mrlib/switchable-button.rkt', patch['patched_sha256']), ('mrlib/private/openracket-paint.rkt', patch['painter_sha256']), ('framework/private/text-misc.rkt', '00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d')):
            assert hashlib.sha256((source / relative).read_bytes()).hexdigest() == pin
        # Official fresh private-scope registration; never relocate a prepared registry.
        # No -U: it would hide the new private user packages.
        prefix = [e['RACKET'], '-A', e['PLTADDONDIR'], '-R', e['PLTCOMPILEDROOTS'], '-l', 'raco', '--']
        self.command(label + ' fresh addon copies exact prepared GUI package', prefix + ['pkg', 'install', '--scope', 'user', '--batch', '--no-setup', '--deps', 'fail', '--copy', '--force', '--name', 'openracket-gui-lib', source], e, 180)
        self.command(label + ' fresh addon links exact proof appearance tool', prefix + ['pkg', 'install', '--scope', 'user', '--batch', '--no-setup', '--deps', 'fail', '--link', '--name', 'openracket-appearance', self.proof / 'tool'], e, 90)
        self.command(label + ' private tool info-domain registration', prefix + ['setup', '--avoid-main', '--no-docs', '--no-launcher', '--no-foreign-libs', '--no-install', '--no-post-install', '--pkgs', 'openracket-appearance'], e, 240)
        self.command(label + ' actual collection and DrRacket discovery proof', [e['RACKET'], '-A', e['PLTADDONDIR'], '-R', e['PLTCOMPILEDROOTS'], self.ci / 'verify-modern-tool-registration.rkt', self.proof], e, 30)

    def preflights(self, arm, e):
        records = []
        for spec in self.verifier.PREFLIGHTS:
            name, arguments, marker, injection, forbidden = spec
            args = [e['RACKET'], '-A', e['PLTADDONDIR'], '-R', e['PLTCOMPILEDROOTS'], self.proof / 'tests' / name, *arguments]
            # Expected nonzero controls must not be passed to command(), whose ordinary
            # success gate is exit0. Retain their actual exit and both streams unchanged.
            p = subprocess.Popen([str(a) for a in args], env=e, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            timed_out = False
            try:
                stdout, stderr = p.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                timed_out = True
                self.terminate_group(p)
                stdout, stderr = p.communicate(timeout=5)
            evidence = {'entrypoint': name, 'arguments': list(arguments), 'exit_code': p.returncode,
                        'timed_out': timed_out, 'timeout_seconds': 30, 'stdout': stdout, 'stderr': stderr}
            records.append(evidence)
            target = self.reports / (arm + '-preflights.json')
            target.write_text(json.dumps(records, indent=2) + '\n')
            try:
                self.contract.validate_preflight_record(evidence, spec)
                ok, detail = True, 'Exact direct invocation and typed marker pair accepted'
            except Exception as error:
                ok, detail = False, str(error)
            self.record(arm + ' direct ' + name + ' ' + ' '.join(arguments), ok, detail)
        self.emit_file(target, arm + '-preflights')
        self.contract.validate_preflights(records, self.verifier)
        return True

    def prepare_runtime(self, arm, native):
        modern = arm == 'modern-light'
        if modern:
            self.command('Independent modern-light runtime', [sys.executable, self.ci / 'copy-independent-runtime.py', 'native-light-tools'], os.environ.copy(), 180)
            self.tree('baseline', self.modern, 'selected-modern')
            self.command('Actual unchanged setup for modern registration', ['/bin/sh', self.proof / 'scripts/setup-openracket.sh', '--install'], self.env('setup', True, True), 720)
        e = self.env('compile-' + arm, modern)
        home = Path(e['PLTUSERHOME'])
        assert not home.exists() and not home.is_symlink()
        home.mkdir()
        if modern:
            self.fresh_modern_addon('compile-modern-light', e)
        prefix = [e['RACKET'], '-A', e['PLTADDONDIR'], '-R', e['PLTCOMPILEDROOTS']]
        self.command(arm + ' official version', prefix + ['-e', '(unless (equal? (version) "9.3") (error "Expected official Racket 9.3"))'], e, 30)
        modules = [self.proof / n for n in native if n.endswith('.rkt')]
        assert len(modules) == 15
        reader = '(parameterize ([read-accept-reader #t]) (for ([f (in-vector (current-command-line-arguments))]) (call-with-input-file f (lambda (in) (read-syntax f in) (unless (eof-object? (read-syntax f in)) (error "Extra form after module" f))))))'
        self.command(arm + ' reader all15 native Racket modules', prefix + ['-e', reader, '--', *modules], e, 30)
        # Keep the accepted host runtime-path dependencies explicit as well.
        dependencies = [self.proof / 'tests' / n for n in ('independent-native-workflows.rkt', 'independent-native-appearance-workflows.rkt', 'independent-native-stop-returning.rkt')]
        self.command(arm + ' compile all15 and accepted runtime-path dependencies', prefix + ['-l', 'raco', '--', 'make', *modules, *dependencies, self.ci / 'verify-modern-tool-registration.rkt'], e, 180)
        self.preflights(arm, e)
        return {'ready': True, 'native_modules': [str(p.relative_to(self.proof)) for p in modules],
                'reader_passed': True, 'compile_passed': True, 'direct_preflight_count': 9,
                'profile': str(home), 'addon': e['PLTADDONDIR'], 'compiled_roots': e['PLTCOMPILEDROOTS']}

    def prepare(self):
        self.tree('baseline', self.stock, 'pristine')
        for name, relative in [('Frozen source checks', 'scripts/check-light-bundle.py'),
                               ('Exact light host derivation', 'scripts/prepare-light-tool-host.py'),
                               ('Light source and receipt refusal checks', 'tests/light-tool-source-test.py'),
                               ('Stock source preservation', 'tests/stock-tool-source-test.py'),
                               ('Coordinator source preservation', 'tests/coordinator-standalone-source-test.py'),
                               ('Dispatch source preservation', 'tests/tool-dispatch-source-test.py')]:
            args = [sys.executable, self.exp / relative]
            if relative.startswith('scripts/prepare-'):
                args.append('--check')
            self.command(name, args)
        self.command('Light adapter focused contract checks', [sys.executable, self.ci / 'test-light-tools-adapter.py'])
        native = self.contract.assemble_proof(self.root, self.proof, self.exp, self.app)
        for source, label in [(self.proof / 'BASE-0520-CONTENTS.json', 'accepted-source-manifest'),
                              (self.proof / 'CONTENTS-SHA256.json', 'assembled-source-manifest'),
                              (self.exp / 'FROZEN-NATIVE-ALLOWLIST.json', 'native-allowlist'),
                              (self.exp / 'DELIVERABLE-SHA256.json', 'frozen-source-manifest')]:
            self.emit_file(source, label)
        preparation = {'freeze_sha256': self.contract.FREEZE_PIN, 'allowlist_sha256': self.contract.ALLOWLIST_PIN,
                       'accepted_sha256': self.contract.ACCEPTED_PIN, 'proof': str(self.proof), 'runtimes': {}}
        for arm in self.contract.ARMS:
            try:
                preparation['runtimes'][arm] = self.prepare_runtime(arm, native)
            except Exception as error:
                preparation['runtimes'][arm] = {'ready': False, 'error': str(error)}
                self.record(arm + ' preparation', False, str(error))
            (self.reports / 'preparation.json').write_text(json.dumps(preparation, indent=2) + '\n')
        self.emit_file(self.reports / 'preparation.json', 'preparation')

    def screenshot(self, path, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False, 'No capture time remains within unchanged60s process bound'
        try:
            p = subprocess.run(['/usr/sbin/screencapture', '-x', str(path)], timeout=min(15, remaining), capture_output=True, text=True)
            if p.returncode:
                raise RuntimeError(p.stderr)
            raw = path.read_bytes()
            assert raw[:8] == b'\x89PNG\r\n\x1a\n' and 1024 <= len(raw) <= 300 * 1024
            return True, str(struct.unpack('>II', raw[16:24])) + ' ' + hashlib.sha256(raw).hexdigest()
        except Exception as error:
            return False, str(error)

    def emit_image(self, label, path):
        raw = path.read_bytes()
        encoded = base64.b64encode(raw).decode()
        print(f'OPENRACKET_SCREENSHOT_BEGIN {label} {len(raw)} {hashlib.sha256(raw).hexdigest()}', flush=True)
        for i in range(0, len(encoded), 3072):
            print(f'OPENRACKET_SCREENSHOT_DATA {label} {i//3072:04d} {encoded[i:i+3072]}', flush=True)
        print(f'OPENRACKET_SCREENSHOT_END {label}', flush=True)

    def native_case(self, case, modern=False):
        if self.launches_blocked:
            raise RuntimeError('No later GUI launch is safe: prior owned-process cleanup was not verified')
        arm = 'modern-light' if modern else 'stock'
        label = 'tools-' + arm + '-' + case
        e = self.env(label, modern)
        home = Path(e['PLTUSERHOME'])
        assert not home.exists() and not home.is_symlink()
        home.mkdir()
        if modern:
            self.fresh_modern_addon(label, e)
        e.update(OPENRACKET_UI='modern' if modern else 'stock', OPENRACKET_HOST_THEME='1' if modern else '0',
                 OPENRACKET_NATIVE_APPEARANCE='1' if modern else '0', OPENRACKET_THEME='light', OPENRACKET_NATIVE_CASE=case)
        assert 'OPENRACKET_NATIVE_APPEARANCE_CHECK' not in e
        assert not any(k.startswith('OPENRACKET_EXPERIMENTAL_') for k in e)
        folder = self.reports / label
        folder.mkdir()
        ready, done, image = folder / 'ready.json', folder / 'capture-done', folder / 'capture.png'
        stdout_file, stderr_file = folder / 'stdout.txt', folder / 'stderr.txt'
        assert not ready.exists() and not done.exists() and ready != done
        e.update(OPENRACKET_READY_FILE=str(ready), OPENRACKET_CAPTURE_DONE=str(done))
        host = 'independent-native-light-tools-host.rkt' if modern else 'independent-native-host.rkt'
        argv = [e['RACKET'], '-A', e['PLTADDONDIR'], '-R', e['PLTCOMPILEDROOTS'], str(self.proof / 'tests' / host)]
        captured, capture_detail, acknowledged, timed_out, result = False, 'Host never became ready', False, False, None
        print('::group::' + label, flush=True)
        started = time.monotonic()
        # Start the unchanged60s budget before spawn; no late observed exit can pass.
        deadline = started + 60
        supervisor_error = None
        cleanup_error = None
        cleanup_verified = False
        forced_cleanup = False
        observed_seconds = None
        with stdout_file.open('w') as stdout, stderr_file.open('w') as stderr:
            p = subprocess.Popen(argv, env=e, stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                while p.poll() is None and time.monotonic() < deadline:
                    if ready.exists():
                        captured, capture_detail = self.screenshot(image, deadline)
                        if captured and time.monotonic() < deadline:
                            done.write_text('OS capture completed\n')
                            acknowledged = True
                        break
                    time.sleep(.1)
                try:
                    result = p.wait(timeout=max(.01, deadline - time.monotonic()))
                    timed_out = time.monotonic() > deadline
                except subprocess.TimeoutExpired:
                    timed_out = True
                observed_seconds = time.monotonic() - started
                if timed_out:
                    # Explicit failure-only diagnostic grace; never acknowledge or pass it.
                    if not captured:
                        captured, capture_detail = self.screenshot(image, time.monotonic() + 15)
            except Exception as error:
                supervisor_error = str(error)
                timed_out = timed_out or time.monotonic() > deadline
            finally:
                # A failed ACK/capture/wait must never leave an owned GUI process
                # overlapping the next independent case. Verify the entire group.
                try:
                    if p.poll() is None or self.live_group_members(p.pid):
                        forced_cleanup = True
                        self.terminate_group(p)
                    result = p.poll()
                    if result is None or self.live_group_members(p.pid):
                        raise RuntimeError('Owned process group still has live members')
                    cleanup_verified = True
                except Exception as error:
                    cleanup_error = str(error)
                    self.launches_blocked = True
        self.record(label + ' owned-process cleanup', cleanup_verified, cleanup_error or 'Terminal child and no runnable owned group members')
        print(stdout_file.read_text(errors='replace'), end='', flush=True)
        print(stderr_file.read_text(errors='replace'), end='', file=sys.stderr, flush=True)
        supervisor = {'arm': arm, 'case': case, 'argv': argv, 'exit_code': result, 'timed_out': timed_out,
                      'timeout_seconds': 60, 'observed_completion_seconds': observed_seconds,
                      'supervisor_error': supervisor_error, 'cleanup_error': cleanup_error,
                      'cleanup_verified': cleanup_verified, 'forced_cleanup': forced_cleanup,
                      'capture_succeeded': captured, 'capture_acknowledged_within_deadline': acknowledged,
                      'capture_detail': capture_detail, 'timeout_diagnostic_grace_max_seconds': 15,
                      'capture_sha256': hashlib.sha256(image.read_bytes()).hexdigest() if captured else None,
                      'fresh_profile': str(home), 'addon': e['PLTADDONDIR'], 'compiled_roots': e['PLTCOMPILEDROOTS'],
                      'xdg_cache_home': e['XDG_CACHE_HOME'], 'initially_absent_profile': True,
                      'initially_absent_ready_and_done': True, 'ready_path': str(ready), 'done_path': str(done),
                      'source_freeze_sha256': self.contract.FREEZE_PIN, 'native_allowlist_sha256': self.contract.ALLOWLIST_PIN}
        (folder / 'supervisor.json').write_text(json.dumps(supervisor, indent=2) + '\n')
        passed, detail = False, 'Missing READY receipt'
        if ready.exists():
            try:
                raw = ready.read_bytes()
                assert len(raw) < 2 * 1024 * 1024, 'Native READY exceeds evidence bound'
                report = json.loads(raw)
                assert isinstance(report, dict), 'READY must be an object'
                preflights = self.reports / (arm + '-preflights.json')
                self.contract.validate_preflights(json.loads(preflights.read_text()), self.verifier)
                args = [sys.executable, self.exp / 'scripts/validate-light-tool-result.py', '--arm', arm, '--case', case,
                        '--report', ready, '--stdout', stdout_file, '--stderr', stderr_file,
                        '--exit-code', str(result), '--preflights', preflights]
                if timed_out:
                    args.append('--timed-out')
                evidence = self.command(label + ' frozen exact receipt verifier', args, timeout=30, required=False)
                passed = (evidence['exit_code'] == 0 and not evidence['timed_out'] and captured and acknowledged
                          and not timed_out and cleanup_verified and not forced_cleanup and supervisor_error is None)
                detail = 'Frozen validator completed; capture and strict observed completion required'
            except Exception as error:
                detail = 'Malformed/incomplete receipt or validation failure: ' + str(error)
        self.record(label + ' native real-tool gate', passed, detail + '; exit=' + str(result) + '; timed_out=' + str(timed_out))
        self.record(label + ' native OS capture', captured and acknowledged and not timed_out, capture_detail)
        emission_errors = []
        for path in (stdout_file, stderr_file, folder / 'supervisor.json', ready):
            if path.exists():
                try:
                    self.emit_file(path, label + '-' + path.stem)
                except Exception as error:
                    emission_errors.append(path.name + ': ' + str(error))
        if captured:
            try:
                self.emit_image(label if passed else label + ('-timeout-diagnostic' if timed_out else '-failure-diagnostic'), image)
            except Exception as error:
                emission_errors.append(image.name + ': ' + str(error))
        self.record(label + ' complete raw evidence transport', not emission_errors, '; '.join(emission_errors))
        print('::endgroup::', flush=True)
        return passed and not emission_errors

    def cases(self):
        preparation = json.loads((self.reports / 'preparation.json').read_text())
        assert preparation['freeze_sha256'] == self.contract.FREEZE_PIN and preparation['allowlist_sha256'] == self.contract.ALLOWLIST_PIN
        native = self.contract.frozen_sources(self.exp)
        self.contract.check_members(self.proof, native)
        readiness = {arm: preparation['runtimes'].get(arm, {}).get('ready') is True for arm in self.contract.ARMS}
        results = self.contract.run_case_matrix(self.native_case, self.record, readiness)
        (self.reports / 'matrix.json').write_text(json.dumps(results, indent=2) + '\n')
        self.emit_file(self.reports / 'matrix.json', 'native-matrix')
        self.contract.validate_matrix(results)

    def verify(self):
        for root, label in ((self.stock, 'pristine'), (self.modern, 'selected-modern')):
            witness = self.temp / ('light-tools-' + label + '-tree.json')
            try:
                if witness.exists():
                    self.tree('compare', root, label, False)
                else:
                    self.record(label + ' full runtime witness unavailable', False)
            except Exception as error:
                self.record(label + ' runtime verification or witness transport', False, str(error))
        try:
            self.contract.validate_matrix(json.loads((self.reports / 'matrix.json').read_text()))
            self.record('All six unique actual stock/light cases accepted', True)
        except Exception as error:
            self.record('Complete stock/light matrix acceptance', False, str(error))
        self.emit_file(self.state, 'all-results')
        # Verify must fail if any prior phase/case failed, even if a later pair passed.
        if any(r['passed'] is not True for r in self.rows):
            raise RuntimeError('One or more mandatory gates failed or remain incomplete')


def main():
    if sys.argv[1:] not in (['prepare'], ['cases'], ['verify']):
        raise SystemExit('Expected prepare, cases, or verify')
    runner = Runner()
    try:
        getattr(runner, sys.argv[1])()
    except Exception as error:
        runner.record(sys.argv[1] + ' orchestration', False, str(error))
        raise
    finally:
        print('Light tool report: ' + str(runner.reports / 'summary.md'), flush=True)
    return 1 if any(not r['passed'] for r in runner.rows[runner.start:]) else 0


if __name__ == '__main__':
    sys.exit(main())
