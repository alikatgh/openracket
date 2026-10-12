#!/usr/bin/env python3
"""Read-only acceptance verifier. Synthetic tests are not native evidence.

Accept only completed six-case-run evidence after all mandatory supervised
headless positives and intentional failures. This script launches nothing.
"""
import argparse
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXPECTED = json.loads((ROOT/'tests/native-light-state-expected.json').read_text())
CASES = ('debugger', 'macro-stepper', 'teaching-tests')
# Preserve every original direct headless positive and negative. Add the new
# light-state contract and its uncaught intentional wrong-painter failure.
PREFLIGHTS = [
    ('native-tool-coordinator-standalone.rkt', [], 'OPENRACKET_NATIVE_TOOL_COORDINATOR_OK strict-failures cleanup-complete', None, None),
    ('native-tool-coordinator-standalone.rkt', ['--inject-outer-failure'], 'OPENRACKET_NATIVE_TOOL_COORDINATOR_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong', 'OPENRACKET_NATIVE_TOOL_COORDINATOR_INJECTING_FAILURE', 'OPENRACKET_NATIVE_TOOL_COORDINATOR_OK'),
    ('native-tool-dispatch-standalone.rkt', [], 'OPENRACKET_NATIVE_TOOL_DISPATCH_OK distinct-thread strict-failures cleanup-complete', None, None),
    ('native-tool-dispatch-standalone.rkt', ['--inject-wrong-result'], 'OPENRACKET_NATIVE_TOOL_DISPATCH_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong', 'OPENRACKET_NATIVE_TOOL_DISPATCH_INJECTING_FAILURE', 'OPENRACKET_NATIVE_TOOL_DISPATCH_OK'),
    ('native-tool-failure-diagnostics-standalone.rkt', [], 'OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_OK typed-payload-preserved output-failures-contained', None, None),
    ('native-tool-failure-diagnostics-standalone.rkt', ['--inject-failure'], 'OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_FAILURE exception=exn:test:check check=check-equal? actual=actual expected=deliberately-wrong', 'OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_INJECTING_FAILURE', 'OPENRACKET_NATIVE_TOOL_FAILURE_DIAGNOSTICS_OK'),
    ('native-tool-source-contract-standalone.rkt', [], 'OPENRACKET_NATIVE_TOOL_SOURCE_CONTRACT_OK source-range-progress-budget-refusals', None, None),
    ('native-light-state-standalone.rkt', [], 'OPENRACKET_NATIVE_LIGHT_STATE_OK exact-palette-painter-cocoa-refusals', None, None),
    ('native-light-state-standalone.rkt', ['--inject-wrong-painter'], 'OPENRACKET_NATIVE_LIGHT_STATE_FAILURE exception=exn:test:check check=check-equal? actual=dark expected=light', 'OPENRACKET_NATIVE_LIGHT_STATE_INJECTING_FAILURE', 'OPENRACKET_NATIVE_LIGHT_STATE_OK'),
]

def require(value, message):
    if not value:
        raise ValueError(message)

def exact(actual, expected):
    """JSON structural equality with booleans distinct from numeric 0/1."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(exact(actual[k], v) for k,v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(exact(a,b) for a,b in zip(actual,expected))
    return actual == expected

def validate_preflights(records):
    require(isinstance(records,list) and len(records)==len(PREFLIGHTS), 'All nine mandatory preflight records required')
    for name,args,marker,injection,forbidden in PREFLIGHTS:
        matches=[r for r in records if isinstance(r,dict) and (r.get('entrypoint'),r.get('arguments'))==(name,args)]
        require(len(matches)==1, 'Unique preflight required: '+name+' '+str(args))
        r=matches[0]
        require(r.get('timed_out') is False and type(r.get('timeout_seconds')) is int and r['timeout_seconds']==30, 'Unchanged completed 30-second preflight required')
        code=r.get('exit_code')
        require(type(code) is int and ((0<code<128 and code not in (124,125,126,127)) if injection else (code==0)), 'Incorrect preflight exit')
        require(isinstance(r.get('stdout'),str) and isinstance(r.get('stderr'),str), 'Complete preflight streams required')
        lines=(r['stdout']+'\n'+r['stderr']).splitlines()
        require(lines.count(marker)==1, 'Exact unique preflight marker required: '+marker)
        if injection:
            require(lines.count(injection)==1 and not any(forbidden in line for line in lines), 'Injected failure did not prove fail-closed execution')
        else:
            require(not any('_INJECTING_FAILURE' in line or 'exception=exn:test:check' in line for line in lines), 'Unexpected failure in positive preflight')
    return True

def validate_result(arm, case, report, stdout, stderr, exit_code, timed_out=False):
    require(arm in ('stock','modern-light') and case in CASES, 'Explicit supported arm and case required')
    require(type(exit_code) is int and exit_code==0 and timed_out is False, 'Successful untimed-out process exit required')
    require(isinstance(report,dict) and report.get('status')=='passed', 'Passed host report required')
    require(report.get('racket')=='9.3' and report.get('genuine_host') is True and report.get('repeated_real_run') is True, 'Official genuine host with repeated Run required')
    require(report.get('complete_stock_parity') is False and report.get('physical_input_to_photon_measured') is False, 'Do not overclaim scope')
    require(report.get('ui')==('stock' if arm=='stock' else 'modern') and report.get('theme')=='light', 'Actual report arm does not match invocation')
    require(report.get('follow_on_case')==case, 'Selected follow-on case mismatch')
    follow=report.get('follow_on_result')
    require(isinstance(follow,dict) and follow.get('case')==case and follow.get('status')=='passed', 'Passed exact real tool case required')
    require(report.get('native_appearance_lifecycle') is None, 'Separate appearance workflow must not be combined')
    require(isinstance(stdout,str) and isinstance(stderr,str), 'Complete native streams required')
    lines=stdout.splitlines()
    require(lines.count('OPENRACKET_NATIVE_READY')==1, 'Exact unique success READY required')
    require('OPENRACKET_NATIVE_FAILURE' not in stdout+stderr and 'OPENRACKET_DIAGNOSTIC_FAILURE' not in stdout+stderr, 'Failure diagnostics forbid success')
    results=[json.loads(line.split(' ',1)[1]) for line in lines if line.startswith('OPENRACKET_NATIVE_RESULT ')]
    require(len(results)==1 and exact(results[0],report), 'Unique stdout result must equal READY JSON')
    states=[json.loads(line.split(' ',1)[1]) for line in lines if line.startswith('OPENRACKET_NATIVE_LIGHT_STATE ')]
    if arm=='modern-light':
        expected=[{'stage':stage,'observed':EXPECTED} for stage in ('before-tool','after-tool')]
        require(exact(report.get('light_tool_states'),expected) and exact(states,expected), 'Two exact actual palette/painter/Cocoa light snapshots required')
        before=next(i for i,line in enumerate(lines) if line.startswith('OPENRACKET_NATIVE_LIGHT_STATE '))
        after=max(i for i,line in enumerate(lines) if line.startswith('OPENRACKET_NATIVE_LIGHT_STATE '))
        launches=[i for i,line in enumerate(lines) if line=='OPENRACKET_NATIVE_STAGE follow-on='+case]
        result_index=next(i for i,line in enumerate(lines) if line.startswith('OPENRACKET_NATIVE_RESULT '))
        require(len(launches)==1 and before<launches[0]<after<result_index, 'Light evidence must bracket the real tool workflow')
    else:
        require('light_tool_states' not in report and not states, 'Stock must use the unchanged accepted host')
    return True

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arm',choices=['stock','modern-light'],required=True)
    p.add_argument('--case',choices=CASES,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--stdout',type=Path,required=True)
    p.add_argument('--stderr',type=Path,required=True)
    p.add_argument('--exit-code',type=int,required=True)
    p.add_argument('--timed-out',action='store_true')
    p.add_argument('--preflights',type=Path,required=True)
    a=p.parse_args()
    validate_preflights(json.loads(a.preflights.read_text()))
    validate_result(a.arm,a.case,json.loads(a.report.read_text()),a.stdout.read_text(),a.stderr.read_text(),a.exit_code,a.timed_out)
    print('OPENRACKET_LIGHT_TOOL_RESULT_ACCEPTED '+a.arm+' '+a.case)
if __name__=='__main__':
    main()
