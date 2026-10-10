#!/usr/bin/env python3
"""Compare two complete native lexer records from equal appearance/settings."""
import argparse
import json

REQUIRED = {'definitions-initial', 'definitions-insert', 'definitions-delete',
            'definitions-undo', 'definitions-redo', 'definitions-string-invalidated',
            'definitions-string-restored', 'framework-stateful-dont-stop'}
APPEARANCE = ('OPENRACKET_UI', 'OPENRACKET_HOST_THEME', 'OPENRACKET_THEME')


def compare(stock, candidate):
    for record in (stock, candidate):
        if record.get('status') != 'complete':
            raise ValueError('Incomplete native record cannot establish equivalence')
        if set(record.get('cases', {})) != REQUIRED:
            raise ValueError('Missing or unexpected native case')
        if record.get('dont_stop_violations') != 0:
            raise ValueError('Native dont-stop scheduling violation')
    for key in ('racket_version', 'preserved_preferences'):
        if stock[key] != candidate[key]:
            raise ValueError(f'Unequal comparison precondition: {key}')
    for key in APPEARANCE:
        if stock['activation_environment'][key] != candidate['activation_environment'][key]:
            raise ValueError(f'Unequal appearance precondition: {key}')
    for name in sorted(REQUIRED):
        if stock['cases'][name] != candidate['cases'][name]:
            for field in ('text', 'characters', 'lexer_valid', 'tokens_by_position',
                          'parenthesis_graph', 'normalized_style_spans'):
                if stock['cases'][name].get(field) != candidate['cases'][name].get(field):
                    raise ValueError(f'Native case {name!r} differs in {field}')
            raise ValueError(f'Native case {name!r} has another difference')
    return {'status': 'equivalent', 'cases': sorted(REQUIRED),
            'scope': 'native fixture token/paren/style outcomes and dont-stop continuity; no speed claim',
            'activation_evidence': 'caller must independently verify candidate source hashes and intended flag'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock')
    parser.add_argument('candidate')
    args = parser.parse_args()
    print(json.dumps(compare(json.load(open(args.stock)), json.load(open(args.candidate))), sort_keys=True))
