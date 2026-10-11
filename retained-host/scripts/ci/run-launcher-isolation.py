#!/usr/bin/env python3
"""CI-only fixed-exclusion construction and two-location frozen native probe."""
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class Runner:
    def __init__(self, operation):
        if sys.flags.optimize:
            raise RuntimeError('Optimized Python disables required source gates')
        sys.dont_write_bytecode = True
        self.ci = Path(__file__).resolve().parent
        self.root = self.ci.parents[1]
        self.c = module('isolation_contract', self.ci / 'launcher-isolation-contract.py')
        self.c.guard(os.environ, platform.system(), platform.machine())
        self.exp = self.root / 'experiments/relative-launcher-isolation-probe'
        if operation == 'run':
            self.c.frozen_sources(self.exp)
        self.temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
        stock = Path(os.environ['OPENRACKET_CI_STOCK_RACKET'])
        self.runtime = self.c.selected_runtime(stock, self.temp, operation == 'run')
        self.proof = self.temp / "OpenRacket Isolation Proof λ's"
        self.work = self.proof / "Build Unicode λ's Probe"
        self.original_app = self.work / 'Path Probe.app'
        self.relocated_app = self.proof / "Relocated Unicode λ's Path Probe.app"
        self.reports = self.root / 'reports/launcher-isolation-ci'
        self.state_file = self.reports / 'state.json'
        if operation == 'run':
            self.c.require(not self.proof.exists() and not self.proof.is_symlink()
                           and not self.reports.exists() and not self.reports.is_symlink(), 'Fresh proof/report paths required')
            self.proof.mkdir(mode=0o700)
            self.reports.mkdir(parents=True, mode=0o700)
            self.state = {'schema': 1, 'source_manifest_sha256': self.c.FREEZE_PIN,
                          'original_runtime': str(self.runtime), 'native_state': 'not-started',
                          'assembled': False, 'observed': False, 'run_attempted': False,
                          'declarations_block_launch': None, 'loader_context_blocks_launch': None, 'errors': [],
                          'installer_boundary': 'Baseline starts after unchanged verified installer; installer version/VM/setup/dirs queries precede it.',
                          'native_timeout_seconds': 120, 'cleanup_wait_seconds': 5,
                          'native_combined_profile_log_limit': 1048576,
                          'original_preferences_file_separately_observed': False,
                          'screenshot': 'Not attempted; no diagnostic subprocess is added after failed or uncertain native state.'}
            self.save()
        else:
            self.c.require(self.state_file.is_file() and not self.state_file.is_symlink(), 'Missing run state; no later native queries')
            self.state = json.loads(self.state_file.read_text())
            self.c.require(self.state['source_manifest_sha256'] == self.c.FREEZE_PIN
                           and self.state['original_runtime'] == str(self.runtime), 'State/input mismatch')
        self.source = None

    def save(self):
        # Durable pre-spawn lease: a crash/interruption cannot leave the previous
        # safe state on disk once a native operation might have been created.
        pending = self.state_file.with_suffix('.pending')
        self.c.require(not pending.exists() and not pending.is_symlink(), 'Unresolved state write blocks execution')
        with pending.open('x') as stream:
            json.dump(self.state, stream, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, self.state_file)
        directory = os.open(self.state_file.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def save_evidence_state(self):
        # Final reporting must survive a failed durability write, while native
        # admission always uses the strict save() above and therefore stays closed.
        try:
            self.save()
        except Exception as error:
            self.state['errors'].append('Evidence-state persistence: ' + str(error))

    def write(self, path, value):
        with path.open('x') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')

    def read(self, path):
        self.c.require(path.is_file() and not path.is_symlink(), 'Missing or unsafe evidence: ' + str(path))
        return json.loads(path.read_text())

    def source_module(self):
        if self.source is None:
            self.c.frozen_sources(self.exp)
            self.source = module('frozen_isolation_supervisor', self.exp / 'supervise.py')
            self.c.require((self.source.TIMEOUT, self.source.STOP_TIMEOUT, self.source.MAX_OUTPUT)
                           == (120, 5, 1048576), 'Frozen native limits changed')
        return self.source

    def handler(self, label):
        self.c.require(self.state['native_state'] in ('not-started', 'safe'), 'Unresolved native state blocks every later query')
        self.state['native_state'] = 'pending-' + label
        self.save()
        try:
            self.c.require(self.c.inventory(self.runtime) == self.read(self.proof / 'original-before.json')
                           and self.c.inventory(self.exp) == self.read(self.proof / 'source-before.json'),
                           'Changed original inputs block every later handler query')
            source = self.source_module()
            profile = source.new_profile(self.proof, label)
            value = source.handler(self.runtime, profile, label)
            self.c.require(type(value.get('schema')) is int and value['schema'] == 1
                           and value.get('extension') == 'rkt' and value.get('status') == 'observed'
                           and value.get('defaults_changed') is False, 'Invalid read-only handler witness')
            self.write(self.proof / (label + '.json'), value)
        except BaseException:
            self.state['native_state'] = 'unresolved-' + label
            self.save()
            raise
        self.state['native_state'] = 'safe'
        self.save()
        return value

    def command(self, label, argv, native=False):
        if native:
            self.c.require(self.state['native_state'] == 'safe', 'No native command after failed/unresolved native work')
            self.state['native_state'] = 'pending-' + label
            self.save()
        folder = self.proof / label
        folder.mkdir(mode=0o700)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONOPTIMIZE='')
        evidence = {'argv': list(map(str, argv)), 'native': native, 'exit_code': None,
                    'supervisor_native_wall_seconds': 120 if native else None,
                    'supervisor_cleanup_wait_seconds': 5 if native else None,
                    'application_launch_authorized': label == 'native-probe'}
        try:
            # The frozen supervisor owns and bounds its native process groups.
            # No shorter wrapper timer kills it before it can prove their death.
            # Workflow emergency ceilings leave pending/unresolved durable state;
            # the separate always-run verifier then performs filesystem work only.
            with (folder / 'stdout.txt').open('xb') as out, (folder / 'stderr.txt').open('xb') as err:
                result = subprocess.run(evidence['argv'], cwd=self.exp, env=env, stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=err, check=False)
            evidence['exit_code'] = result.returncode
        finally:
            self.write(folder / 'command.json', evidence)
            if native:
                # Only strict CLI+receipt+protected-input validation grants safe.
                # Every nonzero exit stays closed even if cleanup might be known.
                self.state['native_state'] = 'unresolved-' + label
                self.save()
        self.c.require(evidence['exit_code'] == 0, label + ' failed; complete raw outputs retained')
        return evidence

    def run(self):
        # Before any probe import or native query, independently preserve both
        # original inputs. Earlier official installer queries are disclosed.
        original = self.c.inventory(self.runtime)
        source_before = self.c.inventory(self.exp)
        self.write(self.proof / 'original-before.json', original)
        self.write(self.proof / 'source-before.json', source_before)
        baseline = self.handler('handler-before-probe')
        self.command('portable-source-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        audit_path = self.proof / 'runtime-audit.json'
        self.command('audit-runtime', [sys.executable, self.exp / 'supervise.py', 'audit-runtime', self.runtime,
                                      '--output', audit_path])
        exact_digest = self.c.validate_audit(self.read(audit_path), original)
        self.state['audit_inventory_digest'] = exact_digest
        self.save()
        self.command('build', [sys.executable, self.exp / 'supervise.py', 'build', '--runtime', self.runtime,
                               '--work', self.work, '--expected-runtime-digest', exact_digest], native=True)
        build = self.read(self.work / 'build.json')
        blocked = self.c.validate_build(build, self.runtime, exact_digest, baseline)
        self.c.require(build.get('bundle') == str(self.original_app), 'Unexpected generated bundle path')
        self.c.protected_witness(self.read(self.work / 'protected-input-witness.json'), original, source_before)
        self.c.require(self.read(self.work / 'original-runtime.json') == original
                       and self.read(self.work / 'source-before.json') == source_before, 'Build original/source witness mismatch')
        retained = self.c.validate_copy_plan(self.read(self.work / 'runtime-copy-plan.json'), original, build)
        actual_retained = self.c.inventory(self.original_app / 'Contents/Resources/runtime')
        self.write(self.proof / 'retained-before.json', actual_retained)
        self.c.require(actual_retained == retained, 'Retained copy differs from exact fixed exclusion')
        self.state.update(assembled=True, declarations_block_launch=blocked,
                          loader_context_blocks_launch=bool(build['static_loader_context_pending']))
        self.save()
        # Set safe only after proving the build receipts, before the independent
        # launch gate. A rejected assembled app is never launched by any route.
        self.state['native_state'] = 'safe'
        self.save()
        self.c.launch_gate(build)
        source = self.source_module()
        source.refuse_claims(source.nested_claims(self.original_app))
        self.c.require(source.check_dependency_paths(self.original_app, source.macho_inventory(self.original_app)) == [],
                       'Live assembled loader audit blocks launch')
        self.c.require(self.c.sha(self.original_app / 'Contents/MacOS/ProbeNative') == build['native_sha256'],
                       'Generated native binary differs from build receipt')
        self.state['run_attempted'] = True
        self.save()
        # This is the only app launch route. Frozen run owns both locations and
        # refuses relocation after any failed or uncertain first observation.
        self.command('native-probe', [sys.executable, self.exp / 'supervise.py', 'run',
                                     '--build-record', self.work / 'build.json', '--renamed', self.relocated_app], native=True)
        summary = self.read(self.work / 'native-summary.json')
        self.c.validate_summary(summary, self.original_app, self.relocated_app, self.work, baseline)
        self.c.protected_witness(self.read(self.work / 'launch-protected-input-witness.json'), original, source_before)
        self.c.require(not self.original_app.exists() and self.relocated_app.is_dir(), 'Relocation did not complete exactly once')
        self.c.require(self.c.inventory(self.relocated_app / 'Contents/Resources/runtime') == retained,
                       'Relocated retained tree changed')
        self.state.update(observed=True, native_state='safe')
        self.save()

    def tree_summary(self, path, entries):
        return {'local_witness': str(path), 'bytes': path.stat().st_size, 'sha256': self.c.sha(path),
                'entry_count': len(entries), 'inventory_digest': self.c.tree_digest(entries),
                'complete_witness_retained_runner_local': True}

    def filesystem_witness(self):
        outcomes = []
        # Independent attempts: a broken source witness never prevents runtime
        # collection and neither starts a process, imports source, or follows links.
        for label, root in (('original', self.runtime), ('source', self.exp)):
            report = {'unchanged': False, 'all_changed_entries': None}
            try:
                after = self.c.inventory(root)
                after_path = self.proof / (label + '-after.json')
                self.write(after_path, after)
                before_path = self.proof / (label + '-before.json')
                before = self.read(before_path)
                rows = self.c.changes(before, after)
                report.update(before=self.tree_summary(before_path, before), after=self.tree_summary(after_path, after),
                              unchanged=rows == [], changed_count=len(rows), all_changed_entries=rows)
            except Exception as error:
                report['error'] = str(error)
                self.state['errors'].append(label + ' final filesystem witness: ' + str(error))
            self.write(self.reports / (label + '-witness.json'), report)
            outcomes.append(report['unchanged'])
        # Retained tree changes are also fully reported, including on native failure.
        report = {'unchanged': False, 'all_changed_entries': None, 'status': 'not-assembled'}
        try:
            before_path = self.proof / 'retained-before.json'
            if before_path.is_file():
                candidates = [p for p in (self.original_app, self.relocated_app) if p.exists()]
                self.c.require(len(candidates) == 1, 'Cannot identify exactly one retained bundle')
                after = self.c.inventory(candidates[0] / 'Contents/Resources/runtime')
                after_path = self.proof / 'retained-after.json'
                self.write(after_path, after)
                before = self.read(before_path)
                rows = self.c.changes(before, after)
                report.update(status='observed', before=self.tree_summary(before_path, before),
                              after=self.tree_summary(after_path, after), unchanged=rows == [],
                              changed_count=len(rows), all_changed_entries=rows)
        except Exception as error:
            report.update(status='failed', error=str(error))
            self.state['errors'].append('Retained final filesystem witness: ' + str(error))
        self.write(self.reports / 'retained-witness.json', report)
        outcomes.append(report['unchanged'])
        try:
            self.c.frozen_sources(self.exp)
        except Exception as error:
            self.state['errors'].append('Final source freeze: ' + str(error))
            outcomes.append(False)
        return all(outcomes)

    def evidence_paths(self):
        paths = []
        def add(path, required=False):
            paths.append((path, required))
        for name in ('state.json', 'verification-state.json', 'original-witness.json', 'source-witness.json', 'retained-witness.json', 'handler-witness.json'):
            add(self.reports / name, True)
        for name in ('source-before.json', 'source-after.json'):
            add(self.proof / name, True)
        for label in ('handler-before-probe', 'handler-after-probe'):
            add(self.proof / (label + '.json'), self.state['observed'])
            for suffix in ('.stdout', '.stderr'):
                add(self.proof / label / (label + suffix), self.state['observed'])
        for label in ('portable-source-tests', 'audit-runtime', 'build', 'native-probe'):
            for leaf in ('command.json', 'stdout.txt', 'stderr.txt'):
                add(self.proof / label / leaf, self.state['observed'])
        for name in ('build.json', 'protected-input-witness.json', 'source-before.json', 'runtime-copy-plan.json',
                     'handler-before-generation.json', 'handler-after-generation.json'):
            add(self.work / name, self.state['assembled'])
        for name in ('native-summary.json', 'launch-protected-input-witness.json'):
            add(self.work / name, self.state['observed'])
        for label in ('handler-before-generation', 'native-compile', 'generate', 'handler-after-generation'):
            for suffix in ('.stdout', '.stderr'):
                add(self.work / 'build-profile' / (label + suffix), self.state['assembled'])
        for index in range(2):
            profile = self.work / ('run-profile-%d' % index)
            for name in ('startup-minimal.rktd', 'startup.json', 'result.json', 'post-launch-witness.json',
                         'child.stdout', 'child.stderr', 'probe.stdout', 'probe.stderr',
                         'handler-before-launch.stdout', 'handler-before-launch.stderr',
                         'handler-after-launch.stdout', 'handler-after-launch.stderr'):
                add(profile / name, self.state['observed'])
        return paths

    def wrap(self, path):
        for label, root in (('proof', self.proof), ('reports', self.reports)):
            if path.is_relative_to(root):
                return self.c.wrap_bytes(path, label + '/' + path.relative_to(root).as_posix())
        raise ValueError('Evidence is outside explicit proof/report roots')

    def collect_evidence(self):
        # Explicit paths only: never emit app binaries, arbitrary profiles, user
        # files or a broad recursive glob. Full runtime inventories stay local;
        # their hashes/counts and every delta remain in the transported witnesses.
        paths = self.evidence_paths()
        audit = self.proof / 'runtime-audit.json'
        if audit.is_file():
            try:
                value = self.read(audit)
                entries = value.pop('inventory')
                value['raw_full_report'] = self.tree_summary(audit, entries)
                transformed = self.reports / 'runtime-audit-metadata.json'
                self.write(transformed, value)
                paths.append((transformed, True))
            except Exception as error:
                self.state['errors'].append('Malformed audit retained as complete raw bytes: ' + str(error))
                paths.append((audit, True))
        elif self.state['assembled']:
            paths.append((audit, True))
        original = self.work / 'original-runtime.json'
        if original.is_file():
            try:
                summary = self.reports / 'build-original-runtime-summary.json'
                self.write(summary, self.tree_summary(original, self.read(original)))
                paths.append((summary, True))
            except Exception as error:
                self.state['errors'].append('Malformed original inventory retained raw: ' + str(error))
                paths.append((original, True))
        elif self.state['assembled']:
            paths.append((original, True))
        self.save_evidence_state()
        emitter = module('isolation_existing_emitter', self.ci / 'emit-replay-evidence.py')
        index, errors = [], []
        for number, (path, required) in enumerate(paths):
            row = {'path': str(path), 'present': path.exists(), 'required': required, 'transported': False}
            if path.exists() or path.is_symlink():
                try:
                    self.c.require(path.is_file() and not path.is_symlink(), 'Unsafe diagnostic file')
                    folder = self.reports / ('evidence-%04d' % number)
                    folder.mkdir()
                    wrapped = folder / 'supervisor.json'
                    value = self.wrap(path)
                    self.write(wrapped, value)
                    emitter.emit(wrapped)
                    row.update(transported=True, bytes=value['bytes'], sha256=value['sha256'])
                except Exception as error:
                    row['error'] = str(error)
                    errors.append(str(path) + ': ' + str(error))
            elif required:
                row['error'] = 'Mandatory diagnostic missing'
                errors.append(str(path) + ': ' + row['error'])
            index.append(row)
        # Independent tail attempts: index failure must not suppress the error
        # receipt or the final verdict. Raw wrappers are self-identifying even
        # when the separate index cannot be recovered from partial CI output.
        for name, value in (('index', index), ('errors', errors)):
            try:
                source = self.reports / ('evidence-' + name + '.json')
                self.write(source, value)
                folder = self.reports / ('evidence-' + name)
                folder.mkdir()
                path = folder / 'supervisor.json'
                self.write(path, self.wrap(source))
                emitter.emit(path)
            except Exception as error:
                errors.append('Evidence ' + name + ' transport: ' + str(error))
        self.state['errors'].extend(errors)
        return not errors

    def verify(self):
        if self.state_file.with_suffix('.pending').exists() or self.state_file.with_suffix('.pending').is_symlink():
            self.state['native_state'] = 'unresolved-state-write'
            self.state['errors'].append('Interrupted durable state write; all later native queries blocked')
        handler_unchanged = None
        report = {'status': 'unobserved', 'reason': 'Prior failed or unresolved native state blocks every later native query',
                  'native_state': self.state['native_state'], 'unchanged': None}
        try:
            if self.state['native_state'] == 'safe' and (self.proof / 'handler-before-probe.json').is_file():
                after = self.handler('handler-after-probe')
                before = self.read(self.proof / 'handler-before-probe.json')
                handler_unchanged = before == after
                report.update(status='observed', reason=None, before=before, after=after, unchanged=handler_unchanged)
        except Exception as error:
            report.update(status='failed', reason=str(error))
            self.state['errors'].append('Final handler witness: ' + str(error))
        self.write(self.reports / 'handler-witness.json', report)
        try:
            inputs_unchanged = self.filesystem_witness()
        except Exception as error:
            inputs_unchanged = False
            self.state['errors'].append('Independent filesystem collection: ' + str(error))
        self.save_evidence_state()
        self.write(self.reports / 'verification-state.json', self.state)
        try:
            transport = self.collect_evidence()
        except Exception as error:
            transport = False
            self.state['errors'].append('Evidence collection: ' + str(error))
        result = self.c.verdict(self.state['assembled'], self.state['observed'], inputs_unchanged, handler_unchanged,
                                transport, self.state['errors'])
        result.update(declarations_block_launch=self.state['declarations_block_launch'],
                      loader_context_blocks_launch=self.state['loader_context_blocks_launch'],
                      native_state=self.state['native_state'], run_attempted=self.state['run_attempted'],
                      validated_native_observations=2 if self.state['observed'] else 0)
        self.write(self.reports / 'result.json', result)
        try:
            folder = self.reports / 'evidence-result'
            folder.mkdir()
            self.write(folder / 'supervisor.json', self.wrap(self.reports / 'result.json'))
            module('isolation_result_emitter', self.ci / 'emit-replay-evidence.py').emit(folder / 'supervisor.json')
        except Exception as error:
            transport = False
            result.update(probe_complete=False, two_location_path_identity_acceptance=False,
                          complete_evidence_transport=False, status='isolation-probe-failed-or-incomplete')
            result['errors'].append('Final result transport: ' + str(error))
            # The direct compact receipt and durable local result remain red;
            # never retry an uncertain partially emitted transport document.
            (self.reports / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
        print('OPENRACKET_LAUNCHER_ISOLATION_RESULT ' + json.dumps(result, sort_keys=True), flush=True)
        lines = ['# Mac launcher-isolation bounded path probe', '', 'Status: ' + result['status'], '',
                 '- Validated native location observations: ' + str(result['validated_native_observations']),
                 '- Declaration launch block: ' + str(result['declarations_block_launch']),
                 '- Static loader launch block: ' + str(result['loader_context_blocks_launch']),
                 '- Original source/runtime and retained copy unchanged: ' + str(inputs_unchanged),
                 '- Default handler unchanged: ' + str(handler_unchanged),
                 '- Complete lossless diagnostic transport: ' + str(transport),
                 '- Full runtime inventories remain runner-local with exact digests/counts; every excluded entry and changed path is transported.',
                 '- Baseline starts after official installer verification queries. Original preference file is not separately observed.',
                 '- Clean destination, actual DrRacket startup, signing/notarization, Gatekeeper and distribution remain untested.']
        (self.reports / 'summary.md').write_text('\n'.join(lines) + '\n')
        self.c.require(result['probe_complete'], 'Launcher-isolation probe failed or remains incomplete')


def main():
    if sys.argv[1:] not in (['run'], ['verify']):
        raise SystemExit('Expected run or verify')
    runner = Runner(sys.argv[1])
    try:
        getattr(runner, sys.argv[1])()
    except Exception as error:
        runner.state['errors'].append(sys.argv[1] + ': ' + str(error))
        runner.save()
        raise


if __name__ == '__main__':
    main()
