#!/usr/bin/env python3
"""Run explicitly authorized native 9.3 parity gates; never invoked by source tests.
Fresh processes cover unset/0/unexpected/1; failures retain bounded diagnostics
while other independent arms continue. No installation, download or publication.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import tempfile
import overlay
import prepare_native

MODES = [('unset', None), ('zero', '0'), ('unexpected', 'yes'), ('on', '1')]
NEGATIVE_FLAG = 'OPENRACKET_NAMED_STYLE_TEST_WRONG_IDENTITY'
NEGATIVE_INJECTION = 'OPENRACKET_NAMED_STYLE_NEGATIVE_CONTROL_INJECTED_V1'
NEGATIVE_ERROR_STEM = 'named-style-differential: negative-control-wrong-object-identity:'
NEGATIVE_ERROR = NEGATIVE_ERROR_STEM + ' #f != #t'

def output_text(value):
    if value is None:
        return ''
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value

def command_result(cmd, env, timeout):
    result = {'command': cmd, 'timeout_seconds': timeout, 'timed_out': False,
              'returncode': None, 'stdout': '', 'stderr': '', 'launched': False}
    try:
        p = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
        result.update(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr, launched=True)
    except subprocess.TimeoutExpired as e:
        result.update(timed_out=True, launched=True, stdout=output_text(e.stdout), stderr=output_text(e.stderr),
                      error='native command exceeded its existing time bound')
    except OSError as e:
        result['error'] = str(e)
    return result

def exact_nonnegative_int(value):
    return type(value) is int and value >= 0

def last_json(result):
    if result['returncode'] != 0 or result.get('timed_out') or result.get('error'):
        raise ValueError('native process did not complete successfully')
    lines = [line for line in result['stdout'].splitlines() if line.startswith('{')]
    if len(lines) != 1:
        raise ValueError('expected one native JSON result, got ' + str(len(lines)))
    value = json.loads(lines[0])
    if not isinstance(value, dict) or value.get('passed') is not True or not exact_nonnegative_int(value.get('checks')) or value['checks'] < 1:
        raise ValueError('no affirmative native checks')
    return value

def validate_modes(results):
    if set(results) != {x[0] for x in MODES}:
        raise ValueError('all exact unset/0/unexpected/1 activation modes are required')
    expected_observations = None
    for mode, value in MODES:
        r = results[mode]
        if r.get('schema') != 'openracket-named-style-native-v1' or r.get('mode') != mode:
            raise ValueError('wrong schema/mode')
        if (r.get('passed') is not True or not exact_nonnegative_int(r.get('checks')) or r['checks'] < 100
                or not exact_nonnegative_int(r.get('scenario-count')) or r['scenario-count'] < 10):
            raise ValueError('native correctness evidence incomplete')
        state = r.get('diagnostics')
        if not isinstance(state, dict):
            raise ValueError('missing diagnostic state')
        for key in ['lookups', 'hits', 'rebuilds', 'members-traversed', 'named-entries', 'member-count']:
            if not exact_nonnegative_int(state.get(key)):
                raise ValueError('diagnostic count is not an exact nonnegative integer: ' + key)
        expected_enabled = value == '1'
        if state.get('enabled') is not expected_enabled or type(state.get('cache-valid')) is not bool:
            raise ValueError('activation/cache validity type mismatch')
        if state['member-count'] != 2:
            raise ValueError('unexpected final stock member count')
        if expected_enabled:
            if state['lookups'] != 4 or state['hits'] != 2 or state['rebuilds'] != 2 or state['members-traversed'] != 3:
                raise ValueError('actual-use/cold-rebuild evidence mismatch')
            if state['cache-valid'] is not True or state['named-entries'] != 2:
                raise ValueError('final current cache is not genuine')
        elif (state['cache-valid'] is not False
              or any(state[k] != 0 for k in ['lookups', 'hits', 'rebuilds', 'members-traversed', 'named-entries'])):
            raise ValueError('disabled path performed index work')
        if not isinstance(r.get('observations'), list) or not r['observations']:
            raise ValueError('no observable trace')
        if expected_observations is None:
            expected_observations = r['observations']
        elif r['observations'] != expected_observations:
            raise ValueError('cross-mode trace mismatch')
    return True

def has_json_record(text):
    # No successful or partial JSON record may contaminate the negative arm,
    # even if prefixed by ordinary output or placed on stderr.
    if any(line.lstrip().startswith('{') for line in text.splitlines()):
        return True
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char == '{':
            try:
                value, _ = decoder.raw_decode(text[index:])
                if isinstance(value, dict):
                    return True
            except ValueError:
                pass
    return False


def negative_control_passed(result):
    stdout = result.get('stdout', '')
    stderr = result.get('stderr', '')
    combined = stdout + '\n' + stderr
    lines = stderr.splitlines()
    return (type(result.get('returncode')) is int and result['returncode'] > 0
            and result.get('launched') is True and not result.get('timed_out')
            and not result.get('error')
            and lines.count(NEGATIVE_INJECTION) == 1
            and combined.count(NEGATIVE_INJECTION) == 1
            and lines.count(NEGATIVE_ERROR) == 1
            and combined.count(NEGATIVE_ERROR_STEM) == 1
            and lines.index(NEGATIVE_INJECTION) < lines.index(NEGATIVE_ERROR)
            and not has_json_record(combined))


def collect_run(report, label, command, env, timeout, *, negative=False):
    result = command_result(command, env, timeout)
    report['runs'][label] = result
    report['native_executed'] = report.get('native_executed', False) or result.get('launched', False)
    if negative:
        good = negative_control_passed(result)
        result['expected_failure_observed'] = good
        if not good:
            report['errors'].append(label + ': expected positive-exit exact identity failure with unique injection marker was not established')
        return None
    try:
        evidence = last_json(result)
        result['evidence'] = evidence
        return evidence
    except (ValueError, TypeError, KeyError) as e:
        result['validation_error'] = str(e)
        report['errors'].append(label + ': ' + str(e))
        return None

def execute_prepared(report, racket, root):
    evidence = {}
    for mode, flag in MODES:
        env = os.environ.copy()
        env.pop(overlay.FLAG, None)
        env.pop(NEGATIVE_FLAG, None)
        if flag is not None:
            env[overlay.FLAG] = flag
        cmd = [racket, str(overlay.ROOT / 'tests/native/differential.rkt'),
               str(root / 'stock/style.rkt'), str(root / 'candidate/style.rkt'), mode]
        observed = collect_run(report, mode, cmd, env, 120)
        if observed is not None:
            evidence[mode] = observed
    try:
        validate_modes(evidence)
    except (ValueError, TypeError, KeyError) as e:
        report['errors'].append('mode-validation: ' + str(e))
    env = os.environ.copy()
    env[overlay.FLAG] = '1'
    env.pop(NEGATIVE_FLAG, None)
    publication = collect_run(report, 'publication',
                              [racket, str(overlay.ROOT / 'tests/native/publication.rkt'),
                               str(root / 'candidate-hook/style.rkt')], env, 60)
    if publication is not None:
        if (publication.get('schema') != 'openracket-named-style-publication-v1'
                or not exact_nonnegative_int(publication.get('checks')) or publication['checks'] < 20):
            report['errors'].append('publication: publication evidence incomplete')
    env[NEGATIVE_FLAG] = '1'
    collect_run(report, 'negative-control',
                [racket, str(overlay.ROOT / 'tests/native/differential.rkt'),
                 str(root / 'stock/style.rkt'), str(root / 'candidate/style.rkt'), 'on'],
                env, 120, negative=True)
    report['passed'] = not report['errors']
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--racket', required=True, help='explicit native Racket 9.3 executable')
    p.add_argument('--prefs', required=True, type=Path, help='official installed 9.3 sibling prefs.rkt')
    p.add_argument('--official-style-source', required=True, type=Path, help='resolved official source to pin before staging')
    p.add_argument('--report', required=True, type=Path)
    a = p.parse_args()
    report = {'schema': 'openracket-named-style-run-v1', 'passed': False, 'errors': [],
              'stock_sha256': overlay.STOCK_SHA256, 'candidate_sha256': overlay.sha256(overlay.candidate_bytes()),
              'native_executed': False, 'runs': {}}
    try:
        if a.official_style_source.read_bytes() != overlay.stock_bytes():
            raise ValueError('resolved installed source does not match official 9.3 pin')
        if a.prefs.resolve().parent != a.official_style_source.resolve().parent:
            raise ValueError('prefs dependency must come from the same official source directory')
        with tempfile.TemporaryDirectory(prefix='openracket-named-style-') as temp:
            root = Path(temp).resolve() / 'modules'
            report['preparation'] = prepare_native.stage(root, a.prefs)
            execute_prepared(report, a.racket, root)
    except (ValueError, OSError) as e:
        report['errors'].append('preparation: ' + str(e))
    finally:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'native_executed': report['native_executed'],
                      'report': str(a.report), 'errors': report['errors']}))
    raise SystemExit(0 if report['passed'] else 1)

if __name__ == '__main__':
    main()
