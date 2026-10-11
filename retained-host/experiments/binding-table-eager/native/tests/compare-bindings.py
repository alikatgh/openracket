#!/usr/bin/env python3
"""Exact full native fixture graph/navigation comparison; only verified arm metadata varies."""
import argparse
import copy
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
PINS = json.loads((ROOT / 'binding-native-pins.json').read_text())
SOURCE = '#lang racket/base\n(define (bump x) (+ x 1))\n(bump 41)\n'
EDGES = [[6, 17, 19, 25], [6, 17, 35, 35], [6, 17, 36, 37],
         [6, 17, 40, 40], [6, 17, 44, 44], [6, 17, 50, 50],
         [27, 31, 45, 49], [32, 33, 38, 39]]
NAVIGATION = [['bump-to-binding', [45, 45], [27, 31]],
              ['bump-next', [27, 31], [45, 49]],
              ['bump-previous', [45, 49], [27, 31]],
              ['parameter-to-binding', [38, 38], [32, 33]],
              ['parameter-next', [32, 33], [38, 39]]]
FIXED_PINS = {
    'blueboxes-gui': 'c81a8df93f0012b0ab564009bb4a9ad34d9ce1cde3795e180bfbe33a1008e721',
    'xref': 'acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7',
    'traversals': 'bfac72f72b6858d809c840a0aa47bdae2652ae084d86ae961b744d683e06da00',
    'online-comp': '1d78a9aecd0c8c50229083c4c653d58927f43ab1165fef0710e098bbf07240b5'}
CHECKS = {'handler_thread', 'fatal_assertions', 'table_identity', 'immutable_equal_sets',
          'editor_identity', 'canvas_identity', 'tab_identity', 'source_unchanged',
          'selection_restored', 'filename_unchanged', 'modified_unchanged', 'sources_unchanged'}
FIELDS = {'schema', 'completed', 'mode', 'activation', 'flag', 'runtime_root', 'version', 'sources',
          'host_sha256', 'workflow_sha256', 'source', 'selection', 'graph', 'edges',
          'navigation', 'eager_witness', 'checks'}
COUNTERS = {'generation', 'accepted', 'duplicates', 'eager_writes', 'stock_calls',
            'pending', 'materializations', 'public_keys', 'indexed_edges', 'cached_starts',
            'unsupported_fallbacks', 'failure_fallbacks'}

class Refused(ValueError):
    pass

def need(condition, message):
    if not condition:
        raise Refused(message)

def exact_fields(value, fields, where):
    need(type(value) is dict and set(value) == fields, f'{where}: exact fields required')

def numeric_lists(value):
    if type(value) is list:
        return all(numeric_lists(item) for item in value)
    return type(value) is int

def validate(row, mode):
    exact_fields(row, FIELDS, mode)
    need(row['schema'] == 'openracket-native-binding-eager-graph/v1' and row['completed'] is True, 'incomplete/schema')
    need(row['mode'] == mode and row['version'] == '9.3', 'mode/version')
    candidate = mode != 'stock'
    enabled = mode == 'candidate-on'
    if candidate:
        need(type(row['activation']) is bool and row['activation'] is enabled, 'loaded activation')
    else:
        need(row['activation'] == 'unexported', 'stock export must be absent')
    need(row['flag'] == ('1' if enabled else '0') if candidate else row['flag'] is None, 'environment activation')
    root = row['runtime_root']
    need(type(root) is str and root.startswith('/') and root != '/' and not root.endswith('/')
         and '..' not in PurePosixPath(root).parts and str(PurePosixPath(root)) == root, 'canonical root')
    expected = dict(FIXED_PINS, gui=PINS['candidate_gui' if candidate else 'stock_gui'])
    exact_fields(row['sources'], set(expected), 'sources')
    for name, digest in expected.items():
        record = row['sources'][name]
        exact_fields(record, {'relative', 'sha256'}, name)
        relative = record['relative']
        need(type(relative) is str and not relative.startswith('/') and '..' not in PurePosixPath(relative).parts
             and str(PurePosixPath(relative)) == relative and relative.endswith('/drracket/private/syncheck/'+name+'.rkt'), 'source path')
        need(record['sha256'] == digest, 'exact source pin: '+name)
    need(row['host_sha256'] == PINS['host'] and row['workflow_sha256'] == PINS['workflow'], 'fixture code pins')
    need(row['source'] == SOURCE and row['selection'] == [1, 6] and numeric_lists(row['selection']), 'exact editor fixture')
    exact_fields(row['checks'], CHECKS, 'checks')
    need(all(value is True for value in row['checks'].values()), 'native preservation assertion')
    graph = row['graph']
    need(type(graph) is list and len(graph) == 3 and numeric_lists(graph), 'complete typed graph')
    reconstructed = []
    prior = None
    for entry in graph:
        need(type(entry) is list and len(entry) >= 2 and type(entry[0]) is list and len(entry[0]) == 2, 'graph row')
        start, *ends = entry
        need(prior is None or prior < start, 'unique ordered starts')
        prior = start
        need(all(type(end) is list and len(end) == 2 for end in ends) and ends == sorted(ends)
             and len(ends) == len(set(map(tuple, ends))), 'unique ordered set endpoints')
        for end in ends:
            need(0 <= start[0] <= start[1] <= 54 and 0 <= end[0] <= end[1] <= 54, 'range bounds')
            reconstructed.append(start + end)
    need(reconstructed == EDGES and row['edges'] == EDGES and numeric_lists(row['edges']), 'all exact binding edges including zero spans')
    need(row['navigation'] == NAVIGATION, 'registered stock keymap navigation')
    for command in row['navigation']:
        need(numeric_lists(command[1:]), 'exact navigation integer types')
    state = row['eager_witness']
    if not candidate:
        need(state is None, 'stock witness must be absent')
    else:
        exact_fields(state, COUNTERS | {'enabled', 'active', 'in_flight', 'exposed', 'fallback_reason'}, 'witness')
        need(type(state['enabled']) is bool and state['enabled'] is enabled and state['active'] is False
             and state['in_flight'] is False and state['exposed'] is enabled, 'witness mode/exposure')
        need(all(type(state[k]) is int and state[k] >= 0 for k in COUNTERS), 'exact bounded counters')
        need(state['pending'] == state['materializations'] == state['indexed_edges'] == state['cached_starts'] == 0
             and state['generation'] > 0 and state['public_keys'] == len(graph)
             and state['failure_fallbacks'] == state['unsupported_fallbacks'] == 0,
             'immediate public table, zero deferred work, cleared auxiliary state')
        if enabled:
            need(state['accepted'] == state['eager_writes'] == len(EDGES) and state['stock_calls'] == 0
                 and state['fallback_reason'] == 'public-exposure', 'genuine eager writes then public exposure')
        else:
            need(state['accepted'] == state['eager_writes'] == 0 and state['stock_calls'] == len(EDGES)
                 and state['fallback_reason'] is None, 'off path must stay original')
    normalized = copy.deepcopy(row)
    for key in ['mode', 'activation', 'flag', 'runtime_root', 'eager_witness']:
        normalized.pop(key)
    normalized['sources']['gui']['sha256'] = '<verified permitted gui delta>'
    return normalized

def compare(rows):
    need(set(rows) == {'stock', 'candidate-off', 'candidate-on'}, 'three distinct modes required')
    projected = {mode: validate(row, mode) for mode, row in rows.items()}
    need(projected['stock'] == projected['candidate-off'] == projected['candidate-on'], 'full native graph/navigation metadata differs')
    return {'accepted': True, 'modes': ['stock', 'candidate-off', 'candidate-on'], 'edges_per_mode': len(EDGES),
            'navigation_per_mode': len(NAVIGATION), 'scope': 'Complete fixed native fixture graph and actual keymap navigation; arbitrary extensions not covered'}

def main():
    parser = argparse.ArgumentParser()
    for mode in ['stock', 'candidate-off', 'candidate-on']:
        parser.add_argument('--'+mode, type=Path, required=True)
    args = vars(parser.parse_args())
    try:
        result = compare({mode: json.loads(args[mode.replace('-', '_')].read_text())
                          for mode in ['stock', 'candidate-off', 'candidate-on']})
    except (Refused, ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({'accepted': False, 'error': str(error)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
