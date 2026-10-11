#!/usr/bin/env python3
"""Portable synthetic contracts; historical evidence is never a new control run."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import validator as v

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'fixtures' / 'run-38110770395'


def historical():
    return [json.loads((FIXTURES / name).read_text()) for name in (
        'capture-capture-summary.json', 'capture-capture-host.json',
        'capture-capture-supervisor.json', 'replay-replay.json', 'replay-supervisor.json')]


def evidence():
    """EXPLICIT TEST ADAPTATION: historic two-on run -> synthetic independent off/on.

    Discarding trial 2, changing flags, dates, PIDs, bounds and paths below are ONLY
    for unit tests. These values must never be presented as real off/on evidence.
    """
    capture, host, cs, prior, supervisor = historical()
    prior['trials'] = [prior['trials'][0]]
    supervisor['intervals'] = [supervisor['intervals'][0]]
    supervisor['config']['trials'] = 1
    supervisor['hard_wall_budget_seconds'] = 97
    off, on = copy.deepcopy(prior), copy.deepcopy(prior)
    os, ns = copy.deepcopy(supervisor), copy.deepcopy(supervisor)
    off['phase_probe_enabled'] = False
    del off['phase_probe_sha256']
    del off['last_observed_terminal_before_probe_queries']
    off['trials'][0]['phase_probe'] = None
    os['config'].pop('phase_probe')
    os['config']['output'] = '/explicit-test-fixture/off'
    ns['config']['output'] = '/explicit-test-fixture/on'
    os.update(pid=100, pgid=100, started_monotonic_ms=1000, elapsed_seconds=33,
              started_utc='2026-10-11T04:00:00+00:00', finished_utc='2026-10-11T04:00:33+00:00')
    ns.update(pid=101, pgid=101, started_monotonic_ms=61000, elapsed_seconds=33,
              started_utc='2026-10-11T04:01:00+00:00', finished_utc='2026-10-11T04:01:33+00:00')
    return [capture, host, cs, off, os, on, ns]


def outcome(data, arm, kind):
    """Create synthetic success/timeout/other terminal variants, preserving schemas."""
    replay, supervisor = data[(3 if arm == 'off' else 5):(5 if arm == 'off' else 7)]
    row = replay['trials'][0]
    if kind == 'success':
        row.update(outcome='handler-results', terminal=copy.deepcopy(data[0]['terminal']),
                   terminal_summary_matches_integrated_capture=True,
                   monitor_evidence=copy.deepcopy(data[0]['monitor_evidence']), retained_place_channels=1,
                   retained_capabilities=1, statuses=['finished-expansion'])
        replay.update(last_place_channels_retained_until_cleanup=1, last_capabilities_retained_until_cleanup=1)
        if arm == 'on':
            phase = row['phase_probe']
            phase['phase_points'] = [dict(phase=label,trial=1,job_generation=1,source_metrics={'monotonic_ms':1})
                                     for label in sorted(v.REQUIRED_PHASES)]
            replay['last_observed_terminal_before_probe_queries'] = copy.deepcopy(row['terminal'])
    elif kind == 'timeout':
        row.update(outcome='supervisor_interval_timeout', terminal=None,
                   terminal_summary_matches_integrated_capture=False, phase_probe=None)
        replay.update(status='incomplete_terminal_protocol', last_terminal_retained_until_cleanup=False)
        supervisor.update(status='driver_failed')
        supervisor['death'].update(returncode=1,unexpected=True)
    elif kind == 'failure':
        row.update(outcome='exn', terminal=dict(tag='exn',exception_details='synthetic',exception_details_truncated=False))
    else:
        raise ValueError(kind)
    supervisor['intervals'][0]['outcome'] = row['outcome']
    return data


class OutcomeContracts(unittest.TestCase):
    def test_two_oom_valid_observation_not_success(self):
        result = v.assess(*evidence())
        self.assertTrue(result['observation_valid'], result['observation_failures'])
        self.assertFalse(result['both_successful'])
        self.assertFalse(result['both_terminal_summary_parity'])
        self.assertFalse(result['on_phase_complete'])
        self.assertEqual(result['classification'],'phase_off_insufficient_to_restore_gui_outcome')
        self.assertFalse(result['prior_completed_phase_acceptance']['accepted'])
        for arm in ('off','on'):
            self.assertEqual(result['observations'][arm]['observed_outcome'],'oom')
            self.assertIn('tag',result['observations'][arm]['terminal_summary_differences'])

    def test_off_success_on_oom_conditional_only(self):
        r = v.assess(*outcome(evidence(),'off','success'))
        self.assertTrue(r['observation_valid'], r['observation_failures'])
        self.assertEqual(r['classification'],'conditional_single_observation_instrumentation_sensitivity')
        self.assertFalse(r['both_successful'])
        self.assertIn('single-observation',r['conclusion'])

    def test_off_success_unequal_summary_or_trace_on_oom_is_inconclusive(self):
        for difference in ('summary','trace'):
            data=outcome(evidence(),'off','success')
            row=data[3]['trials'][0]
            if difference=='summary':
                row['terminal']['compiled_sha256']='a'*64
                row['terminal_summary_matches_integrated_capture']=False
            else:
                row['monitor_evidence']['trace_entries']-=1
            r=v.assess(*data)
            self.assertTrue(r['observation_valid'],r['observation_failures'])
            self.assertTrue(r['observations']['off']['successful_replay'])
            self.assertEqual(r['classification'],'other_observed_outcomes_inconclusive')

    def test_both_success_has_separate_parity_and_phase(self):
        data = outcome(outcome(evidence(),'off','success'),'on','success')
        r = v.assess(*data)
        self.assertTrue(r['observation_valid'],r['observation_failures'])
        self.assertTrue(r['both_successful'])
        self.assertTrue(r['both_terminal_summary_parity'])
        self.assertTrue(r['on_phase_complete'])
        self.assertFalse(r['prior_completed_phase_acceptance']['accepted'])
        data[5]['trials'][0]['terminal']['compiled_sha256'] = 'a'*64
        data[5]['trials'][0]['terminal_summary_matches_integrated_capture'] = False
        r = v.assess(*data)
        self.assertTrue(r['observation_valid'],r['observation_failures'])
        self.assertTrue(r['both_successful'])
        self.assertFalse(r['both_terminal_summary_parity'])
        self.assertIn('compiled_sha256',r['observations']['on']['terminal_summary_differences'])

    def test_timeout_valid_observation_incomplete_phases(self):
        for arm in ('off','on'):
            with self.subTest(arm=arm):
                r = v.assess(*outcome(evidence(),arm,'timeout'))
                self.assertTrue(r['observation_valid'],r['observation_failures'])
                self.assertFalse(r['both_successful'])
                self.assertEqual(r['observations'][arm]['observed_outcome'],'timeout')
                self.assertFalse(r['on_phase_complete'])

    def test_other_terminal_failure_is_preserved(self):
        r = v.assess(*outcome(evidence(),'on','failure'))
        self.assertTrue(r['observation_valid'],r['observation_failures'])
        self.assertEqual(r['observations']['on']['terminal']['exception_details'],'synthetic')
        self.assertEqual(r['classification'],'other_observed_outcomes_inconclusive')

    def test_outer_timeout_preserved_but_readiness_and_trial_unproven(self):
        data=evidence(); data[5]={}
        data[6].update(status='timeout', timeout={'triggered':True,'kind':'hard_wall_budget'})
        r=v.assess(*data)
        self.assertFalse(r['observation_valid'])
        self.assertTrue(r['observations']['on']['supervisor_timeout']['triggered'])

    def test_original_failed_two_trial_run_refused_as_new_control(self):
        capture,host,cs,replay,sup=historical()
        r=v.assess(capture,host,cs,replay,sup,copy.deepcopy(replay),copy.deepcopy(sup))
        self.assertFalse(r['observation_valid'])
        self.assertEqual(len(r['observations']['on']['all_recorded_outcomes']),2)
        self.assertEqual(r['observations']['on']['all_recorded_outcomes'][1]['outcome'],'abnormal-termination')
        self.assertTrue(any('one configured trial' in x for x in r['observation_failures']))
        original_acceptance=v.read(FIXTURES/'replay-acceptance.json')
        self.assertFalse(original_acceptance['accepted'])

    def test_pid_reuse_allowed_with_new_start_and_nonoverlap(self):
        data=evidence();data[6]['pid']=data[6]['pgid']=data[4]['pid']
        self.assertTrue(v.assess(*data)['observation_valid'])

    def test_incomplete_phase_separate_from_observed_success(self):
        data=outcome(outcome(evidence(),'off','success'),'on','success')
        data[5]['trials'][0]['phase_probe']['phase_points'].pop()
        r=v.assess(*data)
        self.assertTrue(r['observation_valid'])
        self.assertTrue(r['both_successful'])
        self.assertFalse(r['on_phase_complete'])

    def test_errors_empty_trace_or_missing_capability_not_success(self):
        for change in ('errors','empty','capabilities','scalars'):
            with self.subTest(change=change):
                data=outcome(outcome(evidence(),'off','success'),'on','success')
                row=data[5]['trials'][0]
                if change=='errors': row['monitor_evidence']['error_messages']=1
                if change=='empty': row['monitor_evidence']['trace_entries']=0
                if change=='capabilities': row['retained_place_channels']=0
                if change=='scalars': row['monitor_evidence']['trace_entries']+=1
                r=v.assess(*data)
                self.assertTrue(r['observation_valid'])
                self.assertEqual(r['both_successful'],change=='scalars')
                if change=='scalars': self.assertFalse(r['both_monitor_scalar_parity'])


class RefusalContracts(unittest.TestCase):
    def test_malformed_and_mismatched_fields(self):
        cases=[
            (0,'settings','prefab'), (0,'snapshot_sha256','a'*64), (0,'actual_child_limit_bytes',128*1024*1024),
            (3,'actual_worker_child_limit_bytes',128*1024*1024), (3,'actual_worker_memory_accounting_available',False),
            (3,'prefab_settings',None), (3,'registry',[]), (3,'source','other'), (3,'snapshot_bytes',0),
            (3,'phase_probe_enabled',True), (5,'phase_probe_enabled',False), (5,'phase_probe_sha256','a'*64),
            (3,'trials',None), (3,'trials',[]), (5,'cleanup',None), (4,'cleanup',None),
            (4,'pid',None), (4,'pid',True), (4,'started_utc',None), (4,'started_utc','2026-10-11T04:00:00'),
            (6,'started_monotonic_ms',1000), (6,'started_utc','2026-10-11T04:00:01+00:00'),
            (4,'hard_wall_budget_seconds',157), (4,'sample_period_seconds',1), (4,'errors',['error']),
            (6,'command',None), (6,'launch_context',{}), (4,'stdout_unparsed_bytes',1),
            (0,'monitor_evidence',None), (2,'memory_profile_setup',None), (3,'capture_terminal',None),
        ]
        for index,key,value in cases:
            with self.subTest(index=index,key=key,value=value):
                data=evidence();data[index][key]=value
                self.assertFalse(v.assess(*data)['observation_valid'])

    def test_null_top_level_documents_fail_closed(self):
        for i in range(7):
            data=evidence();data[i]=None
            self.assertFalse(v.assess(*data)['observation_valid'])

    def test_trial_schema_refusals(self):
        cases=[('terminal',None),('terminal',{'tag':'abnormal-termination','message':'not OOM','explicit_out_of_memory':True}),
               ('outcome','invented'),('phase_probe',[]),('monitor_evidence',None),
               ('trial',True),('prior_terminal_retained_before_request',True),
               ('terminal_summary_matches_integrated_capture',True),('retained_place_channels',None)]
        for key,value in cases:
            with self.subTest(key=key):
                data=evidence();data[5]['trials'][0][key]=value
                self.assertFalse(v.assess(*data)['observation_valid'])

    def test_changed_timeout_trials_and_capture_refusals(self):
        for key,value in [('trials',2),('init_timeout_seconds',31),('terminal_timeout_seconds',61),
                          ('cleanup_timeout_seconds',3),('phase_probe',True),('capture','different')]:
            data=evidence();data[4]['config'][key]=value
            self.assertFalse(v.assess(*data)['observation_valid'])

    def test_json_null_duplicate_and_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x.json'
            for text in ('null','[]','{"x":1,"x":2}','{"x":NaN}','{'):
                p.write_text(text)
                with self.assertRaises(ValueError):v.read(p)

    def test_phase_boolean_generation_cannot_masquerade_as_one(self):
        for point in (False,True):
            for key in ('trial','job_generation'):
                data=outcome(evidence(),'on','success')
                phase=data[5]['trials'][0]['phase_probe']
                (phase['phase_points'][0] if point else phase)[key]=True
                self.assertFalse(v.phase_assessment(phase)['complete'])

    def test_phase_null_malformed_and_missing_points_do_not_crash(self):
        for phase in (None,[],{}, {'phase_points':[None]}, {'phase_points':[{'phase':[]}]}):
            self.assertFalse(v.phase_assessment(phase)['complete'])

    def test_cli_missing_inputs_emits_failed_json_without_writing(self):
        with tempfile.TemporaryDirectory() as t:
            before=list(Path(t).rglob('*'));output=io.StringIO()
            with contextlib.redirect_stdout(output):
                code=v.main(['--probe',t,'--capture',t,'--off',t,'--on',t])
            self.assertEqual(code,1)
            self.assertFalse(json.loads(output.getvalue())['observation_valid'])
            self.assertEqual(before,list(Path(t).rglob('*')))

    def test_cli_retains_each_readable_outcome_on_source_failure(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);data=evidence()
            for dirname,index,names in [('capture',0,('capture-summary.json','capture-host.json','capture-supervisor.json')),
                                      ('off',3,('replay.json','supervisor.json')),('on',5,('replay.json','supervisor.json'))]:
                (base/dirname).mkdir()
                for offset,name in enumerate(names):
                    (base/dirname/name).write_text(json.dumps(data[index+offset]))
            before={str(p):v.sha(p) for p in base.rglob('*') if p.is_file()}
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                code=v.main(['--probe',str(base/'missing-probe'),'--capture',str(base/'capture'),
                             '--off',str(base/'off'),'--on',str(base/'on')])
            r=json.loads(output.getvalue())
            self.assertEqual(code,1)
            self.assertEqual(r['observations']['off']['observed_outcome'],'oom')
            self.assertEqual(r['observations']['on']['observed_outcome'],'oom')
            self.assertEqual(before,{str(p):v.sha(p) for p in base.rglob('*') if p.is_file()})

    def test_actual_source_hash_mismatch_refused(self):
        # Synthetic source tree and manifest pins only for this unit-level refusal.
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); probe=root/'probe';probe.mkdir()
            (probe/'marker').write_text('marker')
            (probe/'SHA256SUMS').write_text(v.sha(probe/'marker')+'  marker\n')
            changed=root/'worker.rkt';changed.write_text('tampered source')
            manifest=dict(compiled=True,compile_exit_code=0,expected_child_limit_bytes=v.CAP,
                          diagnostic_runtime=str(root),racket='/test/racket',
                          files={'worker':{'path':str(changed),'stock_sha256':'a'*64,'diagnostic_sha256':'b'*64}},
                          unmodified_context_sources={},observer_files={})
            (root/'openracket-replay-manifest.json').write_text(json.dumps(manifest))
            cs={'command':['/test/racket',str(probe/'capture-host.rkt')],
                'memory_profile_setup':{'configuration':{'runtime_root':str(root)}}}
            with mock.patch.object(v,'MANIFEST_PIN',v.sha(probe/'SHA256SUMS')), \
                 mock.patch.object(v,'SOURCES',{'worker':('a'*64,'b'*64)}), mock.patch.object(v,'CONTEXT',{}):
                failures,hashes=v.file_evidence(probe,root,root,root,{}, {},cs,{}, {})
            self.assertIn('actual source bytes mismatch: worker',failures)
            self.assertIn(str(changed),hashes)

    def test_historical_fixture_bytes_are_unchanged(self):
        expected=json.loads((FIXTURES/'provenance.json').read_text())
        for name,digest in expected['original_file_sha256'].items():
            self.assertEqual(v.sha(FIXTURES/name),digest)


if __name__=='__main__':
    unittest.main()
