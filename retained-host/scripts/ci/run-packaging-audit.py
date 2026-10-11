#!/usr/bin/env python3
"""CI-only compile/build/audit. There is deliberately no application-launch phase."""
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
        self.c = module('packaging_contract', self.ci / 'packaging-audit-contract.py')
        self.c.guard(os.environ, platform.system(), platform.machine())
        self.exp = self.root / 'experiments/relative-launcher-probe'
        if operation == 'run':
            self.c.frozen_sources(self.exp)
        self.temp = Path(os.environ['RUNNER_TEMP']).resolve(strict=True)
        stock = Path(os.environ['OPENRACKET_CI_STOCK_RACKET'])
        self.c.require(stock.name == 'racket' and stock.parent.name == 'bin', 'Expected selected console executable')
        self.runtime = stock.parent.parent
        self.c.require(not self.runtime.is_symlink() and self.runtime.resolve().is_relative_to(self.temp)
                       and self.runtime.resolve() != self.temp, 'Original runtime must be inside runner temporary root')
        self.runtime = self.runtime.resolve(strict=True)
        self.proof = self.temp / 'openracket-packaging-audit'
        self.reports = self.root / 'reports/packaging-audit-ci'
        self.state_file = self.reports / 'state.json'
        if operation == 'run':
            self.c.require(not self.proof.exists() and not self.proof.is_symlink()
                           and not self.reports.exists() and not self.reports.is_symlink(), 'Fresh proof/report paths required')
            self.proof.mkdir(mode=0o700)
            self.reports.mkdir(parents=True, mode=0o700)
            self.state = {'schema': 1, 'source_manifest_sha256': self.c.FREEZE_PIN,
                          'original_runtime': str(self.runtime), 'native_state': 'not-started',
                          'assembled': False, 'declarations_block_launch': None, 'errors': [],
                          'installer_boundary': 'Baseline starts after unchanged verified installer; installer version/VM/setup/dirs queries precede it.',
                          'native_timeout_seconds': 120, 'cleanup_wait_seconds': 5,
                          'native_combined_profile_log_limit': 1048576, 'native_app_launches': 0}
            self.save()
        else:
            self.c.require(self.state_file.is_file() and not self.state_file.is_symlink(), 'Missing run state; no later native queries')
            self.state = json.loads(self.state_file.read_text())
            self.c.require(self.state['source_manifest_sha256'] == self.c.FREEZE_PIN
                           and self.state['original_runtime'] == str(self.runtime), 'State/input mismatch')
        self.source = None

    def save(self):
        self.state_file.write_text(json.dumps(self.state, indent=2, sort_keys=True) + '\n')

    def write(self, path, value):
        with path.open('x') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')

    def source_module(self):
        if self.source is None:
            self.c.frozen_sources(self.exp)
            self.source = module('frozen_packaging_supervisor', self.exp / 'supervise.py')
            self.c.require((self.source.TIMEOUT, self.source.STOP_TIMEOUT, self.source.MAX_OUTPUT)
                           == (120, 5, 1048576), 'Frozen native limits changed')
        return self.source

    def handler(self, label):
        self.c.require(self.state['native_state'] in ('not-started', 'safe'), 'Unresolved native state blocks every later query')
        self.state['native_state'] = 'pending-' + label
        self.save()
        source = self.source_module()
        profile = source.new_profile(self.proof, label)
        try:
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
                    'application_launch_authorized': False}
        try:
            # Native subprocesses are bounded and reaped by the unchanged frozen
            # supervisor itself. No shorter wrapper deadline kills that supervisor
            # before its independent owned native groups are resolved. The workflow
            # has an emergency whole-step limit; a missing success state then blocks
            # all later native queries, but filesystem witnesses can still run.
            with (folder / 'stdout.txt').open('xb') as out, (folder / 'stderr.txt').open('xb') as err:
                result = subprocess.run(evidence['argv'], cwd=self.exp, env=env, stdin=subprocess.DEVNULL,
                                        stdout=out, stderr=err, check=False)
            evidence['exit_code'] = result.returncode
        finally:
            self.write(folder / 'command.json', evidence)
            if native:
                # Success is not made safe until both CLI exit and build receipt
                # have passed strict validation by run(). Every failure stays closed.
                self.state['native_state'] = 'unresolved-' + label
                self.save()
        self.c.require(evidence['exit_code'] == 0, label + ' failed; complete raw outputs retained')
        return evidence

    def run(self):
        # Independent complete witness before loading probe code or any probe
        # Racket imports. Official installer queries precede this documented boundary.
        self.write(self.proof / 'original-before.json', self.c.inventory(self.runtime))
        baseline = self.handler('handler-before-probe')
        self.command('portable-source-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        audit_path = self.proof / 'runtime-audit.json'
        self.command('audit-runtime', [sys.executable, self.exp / 'supervise.py', 'audit-runtime', self.runtime,
                                      '--output', audit_path])
        before = json.loads((self.proof / 'original-before.json').read_text())
        audit = json.loads(audit_path.read_text())
        exact_digest = self.c.validate_audit(audit, before)
        self.state['declarations_block_launch'] = self.c.claims_present(audit['nested_apps'])
        self.state['audit_inventory_digest'] = exact_digest
        self.save()
        work = self.proof / 'build-work'
        self.command('build', [sys.executable, self.exp / 'supervise.py', 'build', '--runtime', self.runtime,
                               '--work', work, '--expected-runtime-digest', exact_digest], native=True)
        build = json.loads((work / 'build.json').read_text())
        blocked = self.c.validate_build(build, self.runtime, exact_digest, baseline)
        protected = json.loads((work / 'protected-input-witness.json').read_text())
        self.c.require(protected.get('original_runtime_unchanged') is True and protected.get('source_unchanged') is True,
                       'Protected input witness failed')
        self.state.update(assembled=True, declarations_block_launch=blocked, native_state='safe')
        self.save()
        # Never call the source run subcommand, ProbeNative or ProbeBootstrap,
        # even when no declaration keys were found. Audit-only is unconditional.

    def tree_summary(self, path, entries):
        return {'local_witness': str(path), 'bytes': path.stat().st_size, 'sha256': self.c.sha(path),
                'entry_count': len(entries), 'inventory_digest': self.c.tree_digest(entries),
                'complete_witness_retained_runner_local': True}

    def filesystem_witness(self):
        after = self.c.inventory(self.runtime)
        self.write(self.proof / 'original-after.json', after)
        before_path = self.proof / 'original-before.json'
        before = json.loads(before_path.read_text()) if before_path.is_file() else None
        rows = self.c.changes(before, after) if before is not None else None
        report = {'before': self.tree_summary(before_path, before) if before is not None else None,
                  'after': self.tree_summary(self.proof / 'original-after.json', after),
                  'original_runtime_unchanged': before is not None and rows == [],
                  'changed_count': len(rows) if rows is not None else None, 'all_changed_entries': rows}
        self.write(self.reports / 'runtime-witness.json', report)
        self.c.frozen_sources(self.exp)
        return report['original_runtime_unchanged']

    def collect_evidence(self):
        # Explicit allowlist: no bundle contents, binary, broad recursive glob,
        # profile contents or raw full-runtime inventory is logged or uploaded.
        paths = [self.state_file, self.reports / 'runtime-witness.json', self.reports / 'handler-witness.json',
                 self.proof / 'handler-before-probe.json', self.proof / 'handler-after-probe.json']
        for label in ('handler-before-probe', 'handler-after-probe'):
            paths += [self.proof / label / (label + suffix) for suffix in ('.stdout', '.stderr')]
        for label in ('portable-source-tests', 'audit-runtime', 'build'):
            paths += [self.proof / label / leaf for leaf in ('command.json', 'stdout.txt', 'stderr.txt')]
        work = self.proof / 'build-work'
        paths += [work / name for name in ('build.json', 'protected-input-witness.json', 'source-before.json',
                                          'handler-before-generation.json', 'handler-after-generation.json')]
        for label in ('handler-before-generation', 'native-compile', 'generate', 'handler-after-generation'):
            paths += [work / 'build-profile' / (label + suffix) for suffix in ('.stdout', '.stderr')]
        # Preserve all non-inventory audit content byte-exactly as JSON values,
        # including every plist/declaration/Mach-O/static-loader diagnostic row.
        audit = self.proof / 'runtime-audit.json'
        if audit.is_file():
            try:
                value = json.loads(audit.read_text())
                entries = value.pop('inventory')
                value['raw_full_report'] = self.tree_summary(audit, entries)
                transformed = self.reports / 'runtime-audit-metadata.json'
                self.write(transformed, value)
                paths.append(transformed)
            except Exception as error:
                self.state['errors'].append('Malformed audit retained as complete raw bytes: ' + str(error))
                paths.append(audit)
        original = work / 'original-runtime.json'
        if original.is_file():
            try:
                entries = json.loads(original.read_text())
                summary = self.reports / 'build-original-runtime-summary.json'
                self.write(summary, self.tree_summary(original, entries))
                paths.append(summary)
            except Exception as error:
                self.state['errors'].append('Malformed original inventory retained raw: ' + str(error))
                paths.append(original)
        self.save()
        emitter = module('packaging_existing_emitter', self.ci / 'emit-replay-evidence.py')
        index, errors = [], []
        for number, path in enumerate(paths):
            row = {'path': str(path), 'present': path.exists(), 'transported': False}
            if path.exists():
                try:
                    self.c.require(path.is_file() and not path.is_symlink(), 'Unsafe diagnostic file')
                    folder = self.reports / ('evidence-%04d' % number)
                    folder.mkdir()
                    wrapped = folder / 'supervisor.json'
                    value = self.c.wrap_bytes(path)
                    self.write(wrapped, value)
                    emitter.emit(wrapped)
                    row.update(transported=True, bytes=value['bytes'], sha256=value['sha256'])
                except Exception as error:
                    row['error'] = str(error)
                    errors.append(str(path) + ': ' + str(error))
            elif self.state['assembled'] is True:
                row['error'] = 'Mandatory successful-build diagnostic missing'
                errors.append(str(path) + ': ' + row['error'])
            index.append(row)
        self.write(self.reports / 'evidence-index.json', index)
        for name, value in (('index', index), ('errors', errors)):
            folder = self.reports / ('evidence-' + name)
            folder.mkdir()
            path = folder / 'supervisor.json'
            source = self.reports / ('evidence-' + name + '.json')
            if name == 'errors':
                self.write(source, value)
            self.write(path, self.c.wrap_bytes(source))
            emitter.emit(path)
        return not errors

    def verify(self):
        handler_unchanged = None
        report = {'status': 'unobserved', 'reason': 'Prior failed or unresolved native state blocks every later native query',
                  'native_state': self.state['native_state'], 'unchanged': None}
        try:
            if self.state['native_state'] == 'safe' and (self.proof / 'handler-before-probe.json').is_file():
                after = self.handler('handler-after-probe')
                before = json.loads((self.proof / 'handler-before-probe.json').read_text())
                handler_unchanged = before == after
                report.update(status='observed', reason=None, before=before, after=after, unchanged=handler_unchanged)
        except Exception as error:
            report.update(status='failed', reason=str(error))
            self.state['errors'].append('Final handler witness: ' + str(error))
        self.write(self.reports / 'handler-witness.json', report)
        original_unchanged = False
        try:
            # Always attempted independently, including after unresolved native state.
            original_unchanged = self.filesystem_witness()
        except Exception as error:
            self.state['errors'].append('Final read-only filesystem witness: ' + str(error))
        self.save()
        transport = self.collect_evidence()
        result = self.c.verdict(self.state['assembled'] and not self.state['errors'],
                                self.state['declarations_block_launch'], original_unchanged, handler_unchanged, transport)
        result['errors'] = self.state['errors']
        self.write(self.reports / 'result.json', result)
        # Tiny direct summary is supplementary; full result uses the same byte-exact transport.
        folder = self.reports / 'evidence-result'
        folder.mkdir()
        self.write(folder / 'supervisor.json', self.c.wrap_bytes(self.reports / 'result.json'))
        module('packaging_result_emitter', self.ci / 'emit-replay-evidence.py').emit(folder / 'supervisor.json')
        print('OPENRACKET_PACKAGING_AUDIT_RESULT ' + json.dumps(result, sort_keys=True), flush=True)
        lines = ['# Mac packaging audit only', '', 'Status: ' + result['status'], '',
                 '- Native app launches: 0. Construction/audit is not native app acceptance.',
                 '- Declaration launch block: ' + str(result['declarations_block_launch']),
                 '- Original runtime unchanged: ' + str(original_unchanged),
                 '- Default handler unchanged: ' + str(handler_unchanged),
                 '- Complete lossless evidence transport: ' + str(transport),
                 '- Baseline starts after official installer verification queries.',
                 '- Clean destination, real application launch, signing/notarization and distribution remain untested.']
        (self.reports / 'summary.md').write_text('\n'.join(lines) + '\n')
        self.c.require(result['audit_complete'], 'Packaging audit failed or remains incomplete')


def main():
    if sys.argv[1:] not in (['run'], ['verify']):
        raise SystemExit('Expected run or verify; application launch is unavailable')
    runner = Runner(sys.argv[1])
    try:
        getattr(runner, sys.argv[1])()
    except Exception as error:
        runner.state['errors'].append(sys.argv[1] + ': ' + str(error))
        runner.save()
        raise


if __name__ == '__main__':
    main()
