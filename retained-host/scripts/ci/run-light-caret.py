#!/usr/bin/env python3
"""Focused original/patched collapsed-caret gate; native execution is CI-only."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
import importlib.util
_spec = importlib.util.spec_from_file_location('caret_contract', Path(__file__).with_name('caret-ci-contract.py'))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

class Runner:
    def __init__(self, verification_only=False):
        C.require(not sys.flags.optimize, 'Optimized Python is refused')
        C.require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REPOSITORY') == 'alikatgh/openracket' and os.environ.get('GITHUB_REF') == 'refs/heads/prototype/retained-drracket' and platform.system() == 'Darwin', 'Exact public native CI context required')
        self.ci = Path(__file__).resolve().parent
        self.root = self.ci.parents[1]
        self.support = self.ci / 'light-caret-support'
        self.exp = self.root / 'experiments/light-caret-contrast'
        self.source = self.root / 'experiments/light-caret-accepted-source'
        if not verification_only:
            C.verify_inputs(self.exp, self.source, self.support)
        self.app = C.load('caret_app', self.support / 'app-ci-contract.py')
        self.light = C.load('caret_light', self.support / 'light-ci-contract.py')
        if not verification_only:
            self.v = C.load('caret_verifier', self.exp / 'scripts/validate-caret-result.py')
            self.pair = C.load('caret_pair', self.exp / 'scripts/validate-caret-pair.py')
            self.composer = C.load('caret_composer', self.exp / 'scripts/compose-candidate.py')
        self.emitter = C.load('caret_emitter', self.support / 'emit-replay-evidence.py')
        sys.path.insert(0, str(self.source / 'performance'))
        if not verification_only:
            process = C.load('caret_owned_process', self.source / 'performance/run.py')
            self.terminate_group, self.live_group_members = process.terminate_group, process.live_group_members
        self.temp = Path(os.environ['RUNNER_TEMP']).resolve()
        selected = Path(os.environ['OPENRACKET_CI_STOCK_RACKET'])
        self.stock = selected.parents[1] if verification_only else selected.resolve().parents[1]
        if not verification_only:
            C.require(self.stock.is_relative_to(self.temp) and self.stock != self.temp, 'Runtime must be a disposable official install')
        self.work = self.temp / 'openracket-light-caret'
        self.reports = self.root / 'reports/light-caret-ci'
        self.reports.mkdir(parents=True, exist_ok=True)
        self.work.mkdir(exist_ok=True)
        self.safety = C.Safety(self.reports / 'safety.json')
        self.state_file = self.reports / 'state.json'
        self.state = json.loads(self.state_file.read_text()) if self.state_file.exists() else {'schema': 1, 'rows': [], 'prepared': {}, 'matrix': [], 'witnesses': {}}
        self.command_index = len(list((self.reports / 'commands').glob('*'))) if (self.reports / 'commands').exists() else 0

    def save(self):
        C.write(self.state_file, self.state)

    def record(self, name, ok, detail=''):
        # Public summary uses non-path labels; raw bytes remain separate evidence.
        detail = str(detail)
        for value in (str(self.root), str(self.temp), str(Path.home())):
            detail = detail.replace(value, '<runner>')
        row = {'name': name, 'passed': ok is True, 'detail': detail}
        self.state['rows'].append(row)
        self.save()
        print('OPENRACKET_CARET_CI_RESULT ' + json.dumps(row), flush=True)

    def arm_paths(self, arm):
        C.require(arm in C.ARMS, 'Explicit arm required')
        return self.work / ('source-' + arm), self.work / ('runtime-' + arm), self.reports / arm

    def env(self, arm, label):
        proof, runtime, folder = self.arm_paths(arm)
        home = proof / 'profile' if label == 'setup' else self.work / ('profile-' + arm + '-' + label)
        addon = home / '.local/share/racket' if label == 'setup' else home / 'addon'
        cache = home / 'compiled-cache' if label == 'setup' else home / 'compiled'
        return self.app.environment(os.environ, runtime / 'bin/racket', home, addon, cache)

    def prefix(self, e):
        return [e['RACKET'], '-A', e['PLTADDONDIR'], '-R', e['PLTCOMPILEDROOTS']]

    def emit_file(self, path, label):
        wrapped = self.reports / 'transport' / ('evidence-caret-' + label) / 'supervisor.json'
        wrapped.parent.mkdir(parents=True, exist_ok=True)
        C.require(not wrapped.exists(), 'Never repeat an evidence transport label')
        wrapped.write_text(json.dumps(self.light.wrap_bytes(path)) + '\n')
        self.emitter.emit(wrapped)

    def cleanup(self, p):
        forced = False
        if p.poll() is None or self.live_group_members(p.pid):
            forced = True
            self.terminate_group(p)
        C.require(p.poll() is not None and not self.live_group_members(p.pid), 'Owned process cleanup is uncertain')
        return forced

    def execute(self, name, argv, e, timeout, required=True, child_of=None):
        self.command_index += 1
        folder = self.reports / 'commands' / ('command-%04d' % self.command_index)
        folder.mkdir(parents=True)
        token = 'command-' + uuid.uuid4().hex
        row = {'name': name, 'argv': [str(a) for a in argv], 'timeout_seconds': timeout, 'timed_out': False, 'exit_code': None,
               'stdout': '', 'stderr': '', 'cleanup_verified': False, 'forced_cleanup': False, 'launch_id': token}
        p = None
        started = time.monotonic()
        row.update(started_monotonic=started, deadline_monotonic=started + timeout)
        with (folder / 'stdout.txt').open('wb') as out, (folder / 'stderr.txt').open('wb') as err:
            try:
                self.safety.begin(token, 'capture' if child_of else 'command', child_of)
                p = subprocess.Popen([str(a) for a in argv], env=e, stdout=out, stderr=err, start_new_session=True)
                self.safety.spawned(token, p.pid)
                row['process_id'] = p.pid
                try:
                    p.wait(timeout=max(.001, started + timeout - time.monotonic()))
                    row['exited_monotonic'] = time.monotonic()
                    row['timed_out'] = row['exited_monotonic'] > started + timeout
                except subprocess.TimeoutExpired:
                    row['timed_out'] = True
                finally:
                    row['forced_cleanup'] = self.cleanup(p)
                    row['cleanup_verified'] = True
                    row['exit_code'] = p.returncode
                    self.safety.finish(token, True)
            except Exception as error:
                row['error'] = type(error).__name__ + ': ' + str(error)
                try:
                    # Owned cleanup never depends on readable durable state.
                    if p is not None and not row['cleanup_verified']:
                        row['forced_cleanup'] = self.cleanup(p)
                        row['cleanup_verified'] = True
                        row['exit_code'] = p.poll()
                    if token in self.safety.read()['active']:
                        self.safety.finish(token, row['cleanup_verified'])
                except Exception as cleanup_error:
                    row['cleanup_error'] = type(cleanup_error).__name__ + ': ' + str(cleanup_error)
        for stream in ('stdout', 'stderr'):
            path = folder / (stream + '.txt')
            row[stream + '_sha256'] = C.sha(path)
            if path.stat().st_size > 16 * 1024 * 1024:
                row['error'] = 'Untruncated raw output exceeds16MiB transport bound'
                continue
            raw = path.read_bytes()
            try:
                row[stream] = raw.decode('utf-8')
            except UnicodeDecodeError:
                row[stream] = raw.decode('utf-8', errors='replace')
                row['error'] = 'Native output is not UTF-8; original bytes retained'
        C.write(folder / 'supervisor.json', row)
        ok = row['exit_code'] == 0 and not row['timed_out'] and row['cleanup_verified'] and not row['forced_cleanup'] and 'error' not in row
        if required:
            self.record(name, ok, 'exit=' + str(row['exit_code']) + '; timed_out=' + str(row['timed_out']))
            C.require(ok, name + ' failed; raw independent command evidence preserved')
        return row

    def witness(self, name, path, final=False):
        before = self.reports / (name + '-before.json')
        after = self.reports / (name + '-after.json')
        if not final:
            self.state['witnesses'][name] = str(path)
            self.save()
        entries = C.inventory(path)
        value = {'entries': entries, 'tree_sha256': C.tree_sha(entries)}
        if not final:
            C.require(not before.exists(), 'Never overwrite an original witness')
            C.write(before, value)
            return value['tree_sha256']
        C.write(after, value)
        old = json.loads(before.read_text())['entries']
        changes = [{'path': n, 'before': old.get(n), 'after': entries.get(n)} for n in sorted(set(old) | set(entries)) if old.get(n) != entries.get(n)]
        summary = {'before_sha256': C.sha(before), 'after_sha256': C.sha(after), 'before_tree_sha256': C.tree_sha(old),
                   'after_tree_sha256': value['tree_sha256'], 'entry_count': len(entries), 'unchanged': not changes, 'changes': changes,
                   'complete_raw_witness_retained_runner_local': True}
        target = self.reports / (name + '-witness.json')
        C.write(target, summary)
        self.record(name + ' complete final witness', not changes, 'All entries compared; every delta preserved')
        return not changes

    def fresh_addon(self, arm, label, e):
        proof, runtime, folder = self.arm_paths(arm)
        home, addon = Path(e['PLTUSERHOME']), Path(e['PLTADDONDIR'])
        C.require(not home.exists() and not home.is_symlink() and not addon.exists(), 'Private compile/native profile must initially be absent')
        home.mkdir()
        prepared = self.env(arm, 'setup')
        query = '(require pkg/lib)(define p (pkg-directory "openracket-gui-lib"))(unless p (error "Prepared GUI package missing"))(display p)'
        result = self.execute(arm + ' prepared GUI source query', self.prefix(prepared) + ['-e', query], prepared, 30)
        source = Path(result['stdout']).resolve()
        C.require(source.is_dir() and source.is_relative_to(Path(prepared['PLTADDONDIR']).resolve()), 'Prepared package escaped its setup-only addon')
        patch = json.loads((proof / 'reports/patch-manifest.json').read_text())
        for relative, pin in [('mrlib/switchable-button.rkt', patch['patched_sha256']), ('mrlib/private/openracket-paint.rkt', patch['painter_sha256']), ('framework/private/text-misc.rkt', '00d1ac5b184b494939a98057ea4b2584c3cda31378dcb32a7685f370ed60475d')]:
            C.require(C.sha(source / relative) == pin, 'Prepared GUI source mismatch')
        prefix = self.prefix(e) + ['-l', 'raco', '--']
        self.execute(arm + ' ' + label + ' fresh GUI copy registration', prefix + ['pkg', 'install', '--scope', 'user', '--batch', '--no-setup', '--deps', 'fail', '--copy', '--force', '--name', 'openracket-gui-lib', source], e, 180)
        self.execute(arm + ' ' + label + ' exact appearance link registration', prefix + ['pkg', 'install', '--scope', 'user', '--batch', '--no-setup', '--deps', 'fail', '--link', '--name', 'openracket-appearance', proof / 'tool'], e, 90)
        self.execute(arm + ' ' + label + ' official tool info-domain setup', prefix + ['setup', '--avoid-main', '--no-docs', '--no-launcher', '--no-foreign-libs', '--no-install', '--no-post-install', '--pkgs', 'openracket-appearance'], e, 240)
        discovery = self.execute(arm + ' ' + label + ' actual collection/discovery proof', self.prefix(e) + [self.support / 'verify-modern-tool-registration.rkt', proof], e, 30)
        C.write(folder / (label + '-registration.json'), discovery)
        # A read-only headless proof of absent native memory override and default128.
        memory = '(require racket/file)(define p (find-system-path \'pref-file))(when (file-exists? p) (define s (file->string p))(when (regexp-match? #rx"child-only-memory-limit" s) (error "Fresh measured profile contains a memory override")))(displayln "OPENRACKET_CARET_FRESH_MEMORY no-private-override stock-default128")'
        self.execute(arm + ' ' + label + ' fresh memory-default witness', self.prefix(e) + ['-e', memory], e, 30)

    def prepare_arm(self, arm):
        proof, runtime, folder = self.arm_paths(arm)
        self.state['witnesses']['runtime-' + arm] = str(runtime)
        self.save()
        C.independent_copy(self.stock, runtime)
        digest = self.witness('runtime-' + arm, runtime)
        C.require(digest == self.state['official_runtime_sha256'], 'Clone does not match official runtime content')
        inventory_env = self.env(arm, 'inventory')
        inventory_query = '(require pkg/lib racket/path)(define root (path->directory-path (simplify-path (vector-ref (current-command-line-arguments) 0) #t)))(for ([name (in-list (list "drracket" "htdp-lib" "gui-lib"))]) (define p (pkg-directory name))(unless (and p (directory-exists? p) (let ([rel (find-relative-path root (simplify-path p #t))]) (and (relative-path? rel) (not (member (quote up) (explode-path rel)))))) (error "Full official installed dependency missing" name)))(displayln "OPENRACKET_CARET_OFFICIAL_DEPENDENCIES local-only")'
        self.execute(arm + ' official local dependency prerequisite', self.prefix(inventory_env) + ['-U', '-e', inventory_query, '--', runtime], inventory_env, 30)
        e = self.env(arm, 'setup')
        # Accepted setup alone initializes its own preparation-only profile.
        # It is never reused as a compile/control/native profile.
        self.execute(arm + ' unchanged setup-only preparation', ['/bin/sh', proof / 'scripts/setup-openracket.sh', '--install'], e, 720)
        C.check_members(proof, json.loads((folder / 'composition.json').read_text())['files'])
        e = self.env(arm, 'compile')
        self.fresh_addon(arm, 'compile', e)
        modules = self.v.required_racket_modules()
        C.require(len(modules) == 22, 'Exact22 reader/compiler modules required')
        sha = C.sha(folder / 'composition.json')
        reader = '(parameterize ([read-accept-reader #t]) (for ([f (in-vector (current-command-line-arguments))]) (call-with-input-file f (lambda (in) (read-syntax f in) (unless (eof-object? (read-syntax f in)) (error "Extra form after module" f))))))'
        build = []
        for stage, timeout, args in [('reader', 30, ['-e', reader, '--']), ('compile', 180, ['-l', 'raco', '--', 'make'])]:
            result = self.execute(arm + ' all22 ' + stage, self.prefix(e) + args + [proof / n for n in modules], e, timeout, required=False)
            result.update(stage=stage, modules=modules, composition_sha256=sha)
            build.append(result)
            C.write(folder / 'build.json', build)
            C.require(result['exit_code'] == 0 and not result['timed_out'] and result['cleanup_verified'] and not result['forced_cleanup'] and 'error' not in result, 'Reader/compiler failed; do not continue')
        self.v.validate_build(build, sha)
        controls = []
        for spec in self.v.PREFLIGHTS:
            name, args, marker, injection, forbidden = spec
            result = self.execute(arm + ' direct ' + name + ' ' + ' '.join(args), self.prefix(e) + [proof / 'tests' / name, *args], e, 30, required=False)
            result.update(entrypoint=name, arguments=list(args))
            controls.append(result)
            C.write(folder / 'preflights.json', controls)
            try:
                C.require(result['cleanup_verified'] and not result['forced_cleanup'] and 'error' not in result, 'Standalone supervisor failed')
                C.validate_preflight_record(result, spec)
                self.record(arm + ' control ' + str(len(controls)), True, 'Exact typed standalone receipt')
            except Exception as error:
                self.record(arm + ' control ' + str(len(controls)), False, str(error))
        C.validate_preflights(controls, self.v)
        self.state['prepared'][arm] = True
        self.save()

    def prepare(self):
        C.require(not self.state.get('started'), 'Never reuse a partially prepared batch')
        self.safety.initialize()
        self.safety.safe()
        self.state['started'] = True
        self.save()
        # Original/shared witnesses precede every source copy, setup and native command.
        originals = [('runtime-original-official', self.stock), ('accepted-source', self.source),
                     ('frozen-package', self.exp), ('shared-stock-addon', Path(os.environ['OPENRACKET_CI_STOCK_ADDON']))]
        baseline_errors = []
        for name, path in originals:
            try:
                digest = self.witness(name, path)
                if name == 'runtime-original-official':
                    self.state['official_runtime_sha256'] = digest
                self.record(name + ' original witness', True)
            except Exception as error:
                baseline_errors.append(name)
                self.record(name + ' original witness', False, str(error))
        self.save()
        C.require(not baseline_errors, 'Original witnesses incomplete; no native preparation may start')
        compositions = []
        for arm in C.ARMS:
            proof, runtime, folder = self.arm_paths(arm)
            folder.mkdir()
            composition = self.composer.compose(self.source, proof, arm)
            self.v.validate_composition(composition, arm)
            C.write(folder / 'composition.json', composition)
            # Metadata sidecar for unchanged discovery helper. Not a composed source member.
            C.write(proof / 'CONTENTS-SHA256.json', composition['files'])
            compositions.append(composition)
        C.validate_compositions(*compositions, self.v)
        for arm in C.ARMS:
            try:
                self.prepare_arm(arm)
            except Exception as error:
                self.state['prepared'][arm] = False
                self.record(arm + ' preparation', False, str(error))
        C.require(all(self.state['prepared'].get(a) is True for a in C.ARMS), 'Both independent preparations required')

    def capture(self, path, deadline, token, e):
        remaining = deadline - time.monotonic()
        C.require(remaining > 0, 'No capture time left within original deadline')
        row = self.execute('Actual macOS capture', ['/usr/sbin/screencapture', '-x', path], e, min(15, remaining), required=False, child_of=token)
        C.require(row['exit_code'] == 0 and not row['timed_out'] and row['cleanup_verified'] and not row['forced_cleanup'] and 'error' not in row, 'OS capture failed')
        raw = path.read_bytes()
        C.require(0 < len(raw) <= 16 * 1024 * 1024, 'Bounded original capture required')
        self.v.png_size(raw)
        return time.monotonic()

    def native_arm(self, arm):
        self.safety.safe()
        proof, runtime, folder = self.arm_paths(arm)
        C.require(self.state['prepared'].get(arm) is True, 'Exact arm preparation did not pass')
        C.check_members(proof, json.loads((folder / 'composition.json').read_text())['files'])
        self.v.validate_build(json.loads((folder / 'build.json').read_text()), C.sha(folder / 'composition.json'))
        C.validate_preflights(json.loads((folder / 'preflights.json').read_text()), self.v)
        e = self.env(arm, 'native')
        self.fresh_addon(arm, 'native', e)
        e.update(OPENRACKET_UI='modern', OPENRACKET_HOST_THEME='1', OPENRACKET_NATIVE_APPEARANCE='1', OPENRACKET_THEME='light', OPENRACKET_NATIVE_CASE='macro-stepper', OPENRACKET_CARET_ARM=arm)
        C.require('OPENRACKET_NATIVE_APPEARANCE_CHECK' not in e and not any(k.startswith('OPENRACKET_EXPERIMENTAL_') or 'MEMORY_LIMIT' in k for k in e), 'Unexpected native setting')
        ready, ack, png = folder / 'ready.json', folder / 'capture-ack', folder / 'capture.png'
        C.require(all(not p.exists() and not p.is_symlink() for p in (ready, ack, png)), 'Initially absent capture coordination required')
        e.update(OPENRACKET_READY_FILE=str(ready), OPENRACKET_CAPTURE_DONE=str(ack))
        token = 'launch-' + uuid.uuid4().hex
        profile_id = 'native-' + arm + '-' + uuid.uuid4().hex
        C.write(Path(e['PLTUSERHOME']) / '.caret-profile-id.json', {'profile_id': profile_id})
        context = {'profile_id': profile_id, 'launch_id': token, 'profile': e['PLTUSERHOME'], 'addon': e['PLTADDONDIR'], 'compiled_roots': e['PLTCOMPILEDROOTS'], 'racket': e['RACKET'], 'host': str(proof / 'tests/independent-native-light-caret-host.rkt')}
        C.write(folder / 'launch-context.json', context)
        s = {'arm': arm, 'composition_sha256': C.sha(folder / 'composition.json'), 'timeout_seconds': 60, 'timed_out': False,
             'exit_code': None, 'process_group_alive_after_cleanup': None, 'fresh_process': False, 'fresh_profile': True,
             'initial_ready_absent': True, 'initial_ack_absent': True, 'profile_id': profile_id, 'private_launch_context_sha256': C.sha(folder / 'launch-context.json'),
             'launch_id': token, 'official_runtime_sha256': self.state['official_runtime_sha256'], 'capture_tool': 'screencapture',
             'capture_after_ready': False, 'ready_sha256': None, 'png_sha256': None, 'forced_cleanup': False,
             'ready_monotonic': None, 'capture_completed_monotonic': None, 'ack_monotonic': None, 'exited_monotonic': None}
        p = None
        with (folder / 'stdout.txt').open('w') as out, (folder / 'stderr.txt').open('w') as err:
            try:
                self.safety.begin(token, 'gui')
                s['started_monotonic'] = time.monotonic()
                s['deadline_monotonic'] = s['started_monotonic'] + 60
                p = subprocess.Popen([str(a) for a in self.prefix(e) + [proof / 'tests/independent-native-light-caret-host.rkt']], env=e, stdout=out, stderr=err, start_new_session=True)
                s.update(process_id=p.pid, fresh_process=True)
                self.safety.spawned(token, p.pid)
                deadline = s['deadline_monotonic']
                while p.poll() is None and time.monotonic() < deadline:
                    if ready.exists():
                        s['ready_monotonic'] = time.monotonic()
                        raw = ready.read_bytes()
                        C.require(len(raw) < 2 * 1024 * 1024, 'READY exceeds evidence bound')
                        report = json.loads(raw)
                        C.require(type(report) is dict and report.get('status') == 'passed', 'Successful READY required before capture')
                        s['ready_sha256'] = hashlib.sha256(raw).hexdigest()
                        s['capture_completed_monotonic'] = self.capture(png, min(deadline, s['ready_monotonic'] + 20), token, e)
                        s['png_sha256'] = C.sha(png)
                        s['capture_after_ready'] = True
                        C.require(time.monotonic() < min(deadline, s['ready_monotonic'] + 20), 'ACK would miss unchanged deadline')
                        with ack.open('x') as done:
                            done.write('OS capture completed\n')
                        s['ack_monotonic'] = time.monotonic()
                        break
                    time.sleep(.025)
                try:
                    s['exit_code'] = p.wait(timeout=max(.001, deadline - time.monotonic()))
                    s['exited_monotonic'] = time.monotonic()
                    s['timed_out'] = s['exited_monotonic'] > deadline
                except subprocess.TimeoutExpired:
                    s['timed_out'] = True
            except Exception as error:
                s['error'] = type(error).__name__ + ': ' + str(error)
                s['timed_out'] = s['timed_out'] or time.monotonic() > s.get('deadline_monotonic', float('inf'))
            finally:
                try:
                    C.require(p is not None, 'Spawn uncertain; no process identity to verify')
                    s['forced_cleanup'] = self.cleanup(p)
                    s['exit_code'] = p.poll()
                    s['process_group_alive_after_cleanup'] = False
                    self.safety.finish(token, True)
                except Exception as error:
                    s['cleanup_error'] = type(error).__name__ + ': ' + str(error)
                    try:
                        if token in self.safety.read()['active']:
                            self.safety.finish(token, False)
                    except Exception:
                        pass # The unresolved durable prelaunch/active record already blocks.
        C.write(folder / 'supervisor.json', s)
        C.require(not s['forced_cleanup'] and 'error' not in s and 'cleanup_error' not in s, 'Native supervision did not complete normally')
        self.v.validate_supervision(s, ready.read_bytes(), png.read_bytes(), C.sha(folder / 'composition.json'), arm)
        self.v.validate_result(arm, json.loads(ready.read_text()), (folder / 'stdout.txt').read_text(), (folder / 'stderr.txt').read_text(), s)
        return True

    def cases(self):
        rows = []
        for arm in C.ARMS:
            row = {'arm': arm, 'attempted': False, 'passed': False}
            try:
                if self.state['prepared'].get(arm) is True:
                    row['attempted'] = True
                    row['passed'] = self.native_arm(arm)
                else:
                    row['reason'] = 'Required independent preparation failed'
            except Exception as error:
                row['reason'] = type(error).__name__ + ': ' + str(error)
            rows.append(row)
            self.state['matrix'] = rows
            self.record(arm + ' actual native arm', row['passed'], row.get('reason', 'Programmatic evidence accepted; visual review remains pending'))
        C.validate_matrix(rows)
        result = self.pair.validate_pair(self.reports / 'original', self.reports / 'patched')
        result.update(rendered_state_acceptance='pending-independent-visual-review', visual_review_performed=False)
        C.write(self.reports / 'pair-programmatic.json', result)

    def verify(self):
        # Pure filesystem verification is unconditional even after uncertain native cleanup.
        for name, path in self.state['witnesses'].items():
            try:
                self.witness(name, Path(path), final=True)
            except Exception as error:
                self.record(name + ' final witness', False, str(error))
        try:
            C.verify_inputs(self.exp, self.source, self.support)
            self.record('Exact frozen and accepted inputs remain verified', True)
        except Exception as error:
            self.record('Exact frozen and accepted inputs remain verified', False, str(error))
        for arm in C.ARMS:
            try:
                proof, runtime, folder = self.arm_paths(arm)
                C.check_members(proof, json.loads((folder / 'composition.json').read_text())['files'])
                self.record(arm + ' all175 final source bytes', True)
            except Exception as error:
                self.record(arm + ' all175 final source bytes', False, str(error))
        try:
            self.safety.safe()
            C.validate_matrix(self.state['matrix'])
            pair = C.load('caret_final_pair', self.exp / 'scripts/validate-caret-pair.py')
            pair.validate_pair(self.reports / 'original', self.reports / 'patched')
            self.record('Full pair programmatic acceptance', True, 'Independent real pixels still require reviewer inspection')
        except Exception as error:
            self.record('Full pair programmatic acceptance', False, str(error))
        # Failures never suppress other arms, later streams, or independent witnesses.
        targets = []
        for arm in C.ARMS:
            folder = self.reports / arm
            targets += [(folder / n, arm + '-' + n.replace('.', '-')) for n in C.FILES + ('compile-registration.json', 'native-registration.json')]
        for command in sorted((self.reports / 'commands').glob('command-*')):
            targets += [(command / n, command.name + '-' + n.replace('.', '-')) for n in ('supervisor.json', 'stdout.txt', 'stderr.txt')]
        targets += [(p, p.stem) for p in sorted(self.reports.glob('*-witness.json'))]
        targets += [(self.reports / n, n.replace('.', '-')) for n in ('safety.json', 'pair-programmatic.json')]
        errors = []
        for path, label in targets:
            if path.is_file():
                try:
                    self.emit_file(path, label)
                except Exception as error:
                    errors.append(label + ': ' + type(error).__name__)
            else:
                errors.append(label + ': missing/incomplete')
        self.record('Complete independent evidence transport', not errors, '; '.join(errors))
        public = self.reports / 'public-results.json'
        C.write(public, {'rows': self.state['rows'], 'visual_review': 'pending', 'native_scope': 'original/patched modern-light Macro Stepper collapsed caret', 'source_patch': 'tool/info.rkt only'})
        self.emit_file(public, 'public-results')
        lines = ['# Light collapsed-caret pair', '', 'Only original/patched modern-light Macro Stepper is run. Both use independent official runtime clones and fresh private profiles.', '']
        lines += ['- ' + ('PASS: ' if r['passed'] else 'FAIL / incomplete: ') + r['name'] + (': ' + r['detail'] if r['detail'] else '') for r in self.state['rows']]
        lines += ['', 'Programmatic success is conditional. An independent reviewer must inspect each original PNG for the fully visible, unobscured line3 marker before rendered-state acceptance. PNG validation checks structure/CRCs, not pixels. Intended sRGB ratios do not establish anti-aliased pixel contrast or full accessibility. Setup-only profiles are not measured profiles. No memory-limit setting, security bypass, cache upload, artifact upload, or deployment is performed by this adapter.']
        (self.reports / 'summary.md').write_text('\n'.join(lines) + '\n')
        C.require(all(r['passed'] is True for r in self.state['rows']), 'One or more required gates failed or remain incomplete')


def main():
    C.require(sys.argv[1:] in (['prepare'], ['cases'], ['verify']), 'Expected prepare, cases, or verify')
    runner = Runner(verification_only=sys.argv[1] == 'verify')
    try:
        getattr(runner, sys.argv[1])()
    except Exception as error:
        runner.record(sys.argv[1] + ' orchestration', False, str(error))
        raise

if __name__ == '__main__':
    main()
