"""Portable source contracts only. These tests cannot parse or execute Racket."""
from pathlib import Path
import hashlib
import json
import re
import posixpath
import unittest

HERE = Path(__file__).resolve().parent


def forms(text):
    """Limited delimiter-aware lexer; explicitly not a Racket reader/expander."""
    tokens = []
    i = 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
        elif c == ';':
            i = text.find('\n', i)
            if i < 0:
                break
        elif c == '"':
            j = i + 1
            while j < len(text):
                if text[j] == '\\':
                    j += 2
                elif text[j] == '"':
                    j += 1
                    break
                else:
                    j += 1
            else:
                raise AssertionError('Unclosed string')
            tokens.append(text[i:j]); i = j
        elif c in '()[]{}':
            tokens.append(c); i += 1
        else:
            j = i + 1
            while j < len(text) and not text[j].isspace() and text[j] not in ';"()[]{}':
                j += 1
            tokens.append(text[i:j]); i = j
    stack = [([], None)]
    for token in tokens:
        if token in ('(', '[', '{'):
            stack.append(([], {'(': ')', '[': ']', '{': '}'}[token]))
        elif token in (')', ']', '}'):
            if len(stack) < 2 or stack[-1][1] != token:
                raise AssertionError(f'Mismatched delimiter {token}')
            node, _ = stack.pop()
            stack[-1][0].append(node)
        else:
            stack[-1][0].append(token)
    if len(stack) != 1:
        raise AssertionError('Unclosed delimiter')
    return stack[0][0]


def walk(tree):
    if isinstance(tree, list):
        yield tree
        for x in tree:
            yield from walk(x)


class HelperContracts(unittest.TestCase):
    def source(self, name):
        return (HERE / name).read_text()

    def test_balanced_delimiters_only(self):
        for path in HERE.glob('*.rkt'):
            with self.subTest(path=path.name):
                forms(path.read_text())

    def test_provenance_blob_hashes(self):
        provenance = json.loads(self.source('API-PROVENANCE.json'))
        self.assertFalse(provenance['native_run'])
        for row in provenance['evidence']:
            b = row['content'].encode()
            self.assertEqual(row['byte_length'], len(b))
            self.assertEqual(row['sha256'], hashlib.sha256(b).hexdigest())
            self.assertEqual(row['git_blob'], hashlib.sha1(b'blob ' + str(len(b)).encode() + b'\0' + b).hexdigest())
            self.assertRegex(row['ref'], r'^[0-9a-f]{40}$')
            self.assertIn('/' + row['ref'] + '/', row['url'])

    def test_no_private_api_imports(self):
        for path in HERE.glob('*.rkt'):
            for node in walk(forms(path.read_text())):
                if node and node[0] == 'require':
                    self.assertNotIn('/private/', str(node), path.name)

    def test_core_first_contract(self):
        src = self.source('core-first.rkt')
        for fragment in ['(provide go)', '(make-base-empty-namespace)',
                         '[trust-existing-zos #f]', '[managed-recompile-only #f]',
                         '[managed-recompile-cache-dir #f]',
                         '[manager-skip-file-handler (lambda (p) #f)]',
                         '(managed-compile-zo source)', 'PLTCOMPILEDROOTS', 'PLT_ZO_PATH',
                         'expected-root', 'expected-source', 'expected-sha256',
                         'variable-reference->resolved-module-path', 'call-with-input-file source sha256-bytes']:
            self.assertIn(fragment, src)
        self.assertNotIn('raco', src)

    def test_inventory_is_read_only_and_total(self):
        src = self.source('config-inventory.rkt')
        for fragment in ['(install-read-only-guard!)', '#:source-only? #t',
                         '(links #:file p #:with-path? #t)', '(links #:file p #:root? #t)',
                         'current-library-collection-links', '(hash? v)',
                         'get-pkgs-search-dirs', 'find-user-pkgs-dir',
                         'get-info-domain-root', 'get-lib-search-dirs',
                         "'unclassified_config", 'Unclassified configuration keys require review']:
            self.assertIn(fragment, src)
        for forbidden in ['#:repair?', '#:remove?', 'delete-file', 'make-directory', 'managed-compile']:
            self.assertNotIn(forbidden, src)

    def test_public_directory_apis_have_source_evidence(self):
        evidence = json.loads(self.source('API-PROVENANCE.json'))['evidence']
        official = '\n'.join(row['content'] for row in evidence
                             if row['path'].endswith('/dirs.rkt'))
        match = re.search(r'\(define directory-apis(.*?)\n\(for\*', self.source('config-inventory.rkt'), re.S)
        self.assertIsNotNone(match)
        for api in re.findall(r'\b(?:find|get)-[a-z0-9?-]+', match.group(1)):
            self.assertIn(api, official, api)

    def test_receipts_fail_closed(self):
        src = self.source('receipt-lib.rkt')
        for fragment in ['get-compilation-bytecode-file', '#:roots (list K)',
                         'decode-dependency', "'indirect", "'ext", 'collects-relative->path',
                         'Unknown .dep dependency encoding', 'source hash does not match',
                         'module-predefined?', 'module-compiled-imports', 'module-compiled-submodules',
                         'resolve-module-path-index', 'source fallback is forbidden']:
            self.assertIn(fragment, src)
        self.assertNotIn('dynamic-require', src)

    def test_required_source_and_registration_coverage(self):
        src = self.source('rebuilt-receipts.rkt')
        for fragment in ['RUNTIME-PINS.json', "'(13 10)", 'racket/gui/base', 'drracket/drracket',
                         'drracket/private/tools', '(append (cdr spec) (list (car spec)))',
                         'drscheme-language-modules', 'drscheme-language-readers',
                         'get-drscheme-language-positions', 'get-textbook-pls',
                         'compile-omit-paths', 'assume-virtual-sources']:
            self.assertIn(fragment, src)
        self.assertIn("'arbitrary_dynamic_graph_proven #f", src)
        self.assertIn("'child_place_dynamic_audit_complete #f", src)

    def test_encoded_dependency_classification_model(self):
        # Pair notation models Racket's wrappers independently of file suffixes.
        def decode(dep):
            indirect = isinstance(dep, tuple) and dep[0] == 'indirect'
            item = dep[1] if indirect else dep
            external = isinstance(item, tuple) and item[0] == 'ext'
            path = item[1] if external else item
            if not (isinstance(path, bytes) or
                    isinstance(path, list) and len(path) >= 3 and path[0] == 'collects'
                    and all(isinstance(x, bytes) for x in path[1:])):
                raise ValueError('unknown encoding')
            return path, external, indirect
        collect = ['collects', b'racket', b'base.rkt']
        self.assertEqual(decode(collect), (collect, False, False))
        self.assertEqual(decode(('indirect', collect)), (collect, False, True))
        self.assertEqual(decode(('ext', b'/clone/data.rkt')), (b'/clone/data.rkt', True, False))
        self.assertEqual(decode(('indirect', ('ext', collect))), (collect, True, True))
        self.assertEqual(decode(b'/clone/module.rkt'), (b'/clone/module.rkt', False, False))
        for invalid in [('unknown', collect), ['collects', b'racket'], 'relative.rkt']:
            with self.assertRaises(ValueError):
                decode(invalid)

    def test_runtime_module_path_public_provenance(self):
        ev = json.loads(self.source('API-PROVENANCE.json'))['evidence']
        runtime = next(x['content'] for x in ev if x['path'] == 'racket/collects/racket/runtime-path.rkt')
        embed = next(x['content'] for x in ev if x['path'] == 'racket/collects/compiler/embed.rkt')
        self.assertIn('(require (only-in (for-label mod-path)))', runtime)
        self.assertIn('(define-syntax (define-runtime-module-path-index stx)', runtime)
        self.assertIn('(runtime-paths ,module-path)', embed)
        self.assertIn('(module-compiled-cross-phase-persistent? code)', embed)
        source = self.source('receipt-lib.rkt')
        for fragment in ['(runtime-paths ,module-path)', '(make-base-empty-namespace)',
                         '(module-compiled-cross-phase-persistent? code)',
                         '[current-security-guard (make-read-only-guard)]',
                         "(eq? (car spec) 'module)", 'registered-runtime-module-path',
                         "'kind \"data\"", "'runtime_paths"]:
            self.assertIn(fragment, source)
        self.assertIn('filename', self.source('README.md'))

    def test_config_safe_parent_and_escape_models(self):
        clone = '/arm/runtime'
        base = clone + '/collects'
        safe = posixpath.normpath(base + '/../lib')
        outside = posixpath.normpath(base + '/../../../outside')
        self.assertEqual(safe, clone + '/lib')
        self.assertFalse(outside.startswith(clone + '/'))
        src = self.source('config-inventory.rkt')
        self.assertIn("'raw_path (path->string raw)", src)
        self.assertIn('(define full (physical raw))', src)
        self.assertIn("'resolved_class_source (file-record actual-class-source)", src)

    def test_unchanged_closure_fast_path_and_actual_hash(self):
        src = self.source('audit-loads.rkt')
        self.assertIn('(unless (hash-has-key? verified-roots identity)', src)
        self.assertIn('(make-immutable-hash', src)
        for forbidden in ['receipt-one!', 'receipt-result', 'receipt-lib.rkt',
                          'runtime-module-paths!', '(expand ', '(eval ']:
            self.assertNotIn(forbidden, src)
        self.assertIn('(configuration!)', src)
        self.assertIn('(equal? (digest selected)', src)
        self.assertIn("(hash-ref (hash-ref row 'bytecode) 'sha256)", src)

    def test_pinned_worker_root_and_registry_scope(self):
        src = self.source('rebuilt-receipts.rkt')
        self.assertIn('drracket/private/expanding-place', src)
        self.assertIn("'export \"start\"", src)
        self.assertIn("'live_registry_observed #f", src)
        self.assertIn("'online_handler_registry_complete #f", src)
        self.assertIn("'ordered_online_handler_registry_complete #f", src)
        self.assertIn('Pinned dynamic worker seam differs', src)

    def test_case_insensitive_inventory_guard_model(self):
        # Pure inventory input only: do not create case-distinct files on disk.
        def unique(names):
            lowered = [name.casefold() for name in names]
            return len(set(lowered)) == len(lowered)
        self.assertTrue(unique(['core-first.rkt', 'receipt-lib.rkt']))
        self.assertFalse(unique(['Receipt.rkt', 'receipt.rkt']))
        names = [p.name for p in HERE.iterdir()]
        self.assertTrue(unique(names))

    def test_runtime_guard_preserves_arguments(self):
        src = self.source('audit-loads.rkt')
        self.assertNotIn('(current-command-line-arguments ', src)
        self.assertNotIn('(putenv ', src)
        self.assertIn('(original-resolver module relative syntax #f)', src)
        self.assertIn('(original-resolver module relative syntax load?)', src)
        self.assertIn('(current-load/use-compiled', src)
        self.assertIn('(current-load\n', src)
        self.assertIn('(original-exit-handler 96)', src)
        self.assertIn('source fallback', src)
        self.assertIn("'child_place_dynamic_audit_complete #f", src)

    def test_every_audit_writer_uses_separate_output_lock(self):
        src = self.source('audit-loads.rkt')
        tree = forms(src)
        records = [node for node in walk(tree)
                   if len(node) >= 2 and node[0] == 'define'
                   and node[1] == ['record!', 'event', 'payload']]
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(len(record), 3)
        self.assertEqual(record[2][:2], ['call-with-semaphore', 'output-lock'])
        body = record[2][2]
        self.assertEqual(body[:2], ['lambda', []])
        self.assertEqual([node[0] for node in body[2:]], ['display', 'emit'])
        self.assertIn('(define output-lock (make-semaphore 1))', src)
        self.assertIn('(define gate-lock (make-semaphore 1))', src)
        self.assertNotIn('gate-lock', str(record))
        # There is no bypass writer for primitive, declaration, closure, failure
        # or installed events: every actual output form is inside record!.
        output_forms = [node for node in walk(tree)
                        if node and isinstance(node[0], str)
                        and node[0] in {'display', 'emit', 'write-json', 'newline',
                                       'displayln', 'printf', 'fprintf', 'flush-output'}]
        self.assertEqual(output_forms, body[2:])
        self.assertEqual(src.count('OBJECT_HASH_LOAD_AUDIT '), 1)
        for event in ['"primitive"', '"evaluated-module"', '"rejected"', '"installed"']:
            self.assertIn('(record! ' + event, src)
        self.assertIn('(record! "modules"', src)

    def test_serialized_split_writer_all_schedules_model(self):
        # Exhaustively schedule two split writers with a shared mutex. This
        # verifies the portable record-boundary model, not Racket execution.
        prefix = 'OBJECT_HASH_LOAD_AUDIT '
        rows = [dict(event='primitive', data={'name': '#%kernel'}),
                dict(event='evaluated-module', data={'name': 'fixture'})]
        chunks = [[prefix, json.dumps(row, sort_keys=True), '\n'] for row in rows]
        finished = set()
        def visit(positions, owner, output):
            if positions == (5, 5):
                finished.add(output)
                return
            for worker in range(2):
                step = positions[worker]
                if step == 5:
                    continue
                if step == 0:
                    if owner is not None:
                        continue
                    next_owner, next_output = worker, output
                elif step == 4:
                    if owner != worker:
                        continue
                    next_owner, next_output = None, output
                else:
                    if owner != worker:
                        continue
                    next_owner, next_output = owner, output + chunks[worker][step - 1]
                updated = list(positions)
                updated[worker] += 1
                visit(tuple(updated), next_owner, next_output)
        visit((0, 0), None, '')
        self.assertEqual(len(finished), 2)
        for output in finished:
            lines = output.splitlines()
            self.assertEqual(len(lines), 2)
            self.assertTrue(all(line.startswith(prefix) for line in lines))
            parsed = [json.loads(line[len(prefix):]) for line in lines]
            self.assertCountEqual(parsed, rows)

    def test_prebuild_handoff_source_contract(self):
        src = self.source('audit-loads.rkt')
        for fragment in ['prebuild-receipts.json', 'OBJECT_HASH_PREBUILD_RECEIPT_SHA256',
                         '(hex (sha256-bytes raw))', 'Prebuild receipt raw SHA-256 mismatch',
                         'object-hash-rebuild-receipts/v1', "(hash-ref receipt 'mode) \"full\"",
                         "(hash-ref receipt 'runtime_root) (path->string C)",
                         "(hash-ref receipt 'probe_root) (path->string Q)",
                         "(hash-ref receipt 'helper_root) (path->string H)",
                         "(hash-ref receipt 'compiled_root) (path->string K)",
                         'Unknown runtime module outside the accepted prebuild closure',
                         "(for ([field (in-list '(source bytecode dependency))])",
                         '(verify-file! (hash-ref row field))',
                         "'prebuild_receipt_sha256 expected-receipt-sha256",
                         "'live_registry_observed #f", "'arbitrary_dynamic_graph_proven #f"]:
            self.assertIn(fragment, src)
        tree = forms(src)
        config = next(node for node in walk(tree) if len(node) > 1 and node[0] == 'define'
                      and node[1] == ['configuration!'])
        self.assertNotIn('getenv', str(config))
        for name in ['current-compiled-file-roots', 'use-compiled-file-paths',
                     'current-library-collection-paths', 'current-library-collection-links',
                     'find-config-dir', 'find-collects-dir', 'effective-executable']:
            self.assertIn(name, str(config))
        self.assertEqual(src.count('(assert-layout!)'), 1)
        evidence = json.loads(self.source('API-PROVENANCE.json'))['evidence']
        getinfo = next(row['content'] for row in evidence
                       if row['path'] == 'racket/collects/setup/getinfo.rkt')
        self.assertIn('filter-environment-variables', getinfo)
        self.assertIn('(make-environment-variables)', getinfo)

    def test_prebuild_handoff_refusal_models(self):
        # Pure bytes/maps: no native code or fake case-distinct filesystem files.
        roots = dict(runtime_root='/W/runtime', probe_root='/W/probe',
                     helper_root='/W/ci', compiled_root='/W/compiled')
        paths = dict(source='/W/runtime/collects/example.rkt',
                     bytecode='/W/compiled/example_rkt.zo',
                     dependency='/W/compiled/example_rkt.dep')
        files = {path: ('original-' + kind).encode() for kind, path in paths.items()}
        row = {'nominal_path': paths['source']}
        for kind, path in paths.items():
            row[kind] = dict(path=path, size=len(files[path]),
                             sha256=hashlib.sha256(files[path]).hexdigest())
        receipt = dict(schema='object-hash-rebuild-receipts/v1', mode='full',
                       registered_and_static_closure_complete=True, modules=[row],
                       live_registry_observed=False, online_handler_registry_complete=False,
                       child_place_dynamic_audit_complete=False, arbitrary_dynamic_graph_proven=False, **roots)
        raw = json.dumps(receipt, sort_keys=True).encode()
        expected = hashlib.sha256(raw).hexdigest()
        def accept(raw_bytes, wanted, expected_roots):
            if hashlib.sha256(raw_bytes).hexdigest() != wanted:
                raise ValueError('wrong receipt hash')
            obj = json.loads(raw_bytes)
            if (obj['schema'] != 'object-hash-rebuild-receipts/v1' or obj['mode'] != 'full'
                    or any(obj[key] != value for key, value in expected_roots.items())):
                raise ValueError('wrong schema/mode/root')
            flags = ('live_registry_observed', 'online_handler_registry_complete',
                     'child_place_dynamic_audit_complete', 'arbitrary_dynamic_graph_proven')
            if any(obj.get(flag, None) is not False for flag in flags):
                raise ValueError('missing or incorrect coverage flag')
            return {record['nominal_path']: record for record in obj['modules']}
        known = accept(raw, expected, roots)
        for flag in ('live_registry_observed', 'online_handler_registry_complete',
                     'child_place_dynamic_audit_complete', 'arbitrary_dynamic_graph_proven'):
            for bad in (True, None):
                altered = dict(receipt)
                if bad is None:
                    altered.pop(flag)
                else:
                    altered[flag] = bad
                altered_raw = json.dumps(altered, sort_keys=True).encode()
                with self.subTest(flag=flag, bad=bad), self.assertRaises(ValueError):
                    accept(altered_raw, hashlib.sha256(altered_raw).hexdigest(), roots)
        def check(path, current_files, current_root='/W/compiled', collections=('/W/runtime/collects',),
                  main_config='/W/runtime/etc', main_collects='/W/runtime/collects',
                  executable='/W/runtime/bin/racket'):
            if (current_root != roots['compiled_root'] or collections != ('/W/runtime/collects',)
                    or main_config != '/W/runtime/etc' or main_collects != '/W/runtime/collects'
                    or executable != '/W/runtime/bin/racket'):
                raise ValueError('changed effective parameters')
            if path not in known:
                raise ValueError('unknown module')
            for kind in ('source', 'bytecode', 'dependency'):
                record = known[path][kind]
                data = current_files[record['path']]
                if len(data) != record['size'] or hashlib.sha256(data).hexdigest() != record['sha256']:
                    raise ValueError('changed ' + kind)
        check(paths['source'], files)
        with self.assertRaises(ValueError):
            accept(raw, '0' * 64, roots)
        with self.assertRaises(ValueError):
            accept(raw, expected, dict(roots, runtime_root='/other/runtime'))
        for field in ['source', 'bytecode', 'dependency']:
            changed = dict(files, **{paths[field]: b'changed'})
            with self.subTest(field=field), self.assertRaises(ValueError):
                check(paths['source'], changed)
        with self.assertRaises(ValueError):
            check('/W/runtime/unknown.rkt', files)
        with self.assertRaises(ValueError):
            check(paths['source'], files, current_root='/other/compiled')
        with self.assertRaises(ValueError):
            check(paths['source'], files, collections=('/other/collects',))
        for field in ('main_config', 'main_collects', 'executable'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                check(paths['source'], files, **{field: '/other/path'})
        # A selected-bytecode check is repeated even after root verification.
        check(paths['source'], files)
        changed_bytecode = b'changed after first resolution'
        self.assertNotEqual(hashlib.sha256(changed_bytecode).hexdigest(), row['bytecode']['sha256'])

    def test_compact_actual_load_event_contract(self):
        src = self.source('audit-loads.rkt')
        events = [node for node in walk(forms(src))
                  if len(node) == 3 and node[:2] == ['record!', '"modules"']]
        self.assertEqual(len(events), 1)
        event = events[0][2]
        self.assertEqual(event[0], 'hasheq')
        self.assertEqual(event[1::2], ["'nominal_path", "'source", "'bytecode", "'dependency",
                                       "'prebuild_receipt_sha256"])
        self.assertEqual(event[-1], 'expected-receipt-sha256')
        self.assertNotIn("'dependencies", str(event))
        self.assertNotIn("'reason", str(event))
        self.assertIn("(eq? (hash-ref receipt flag) #f)", src)
        self.assertIn('Prebuild receipt coverage flags are missing or differ', src)

    def test_sha256_predicate_source_and_native_self_check(self):
        src = self.source('audit-loads.rkt')
        self.assertIn('(= (string-length s) 64)', src)
        self.assertIn('#rx"^[0-9a-f]+$"', src)
        self.assertNotIn('#rx"^[0-9a-f]{64}$"', src)
        tree = forms(src)
        predicate = next(node for node in walk(tree) if len(node) > 1 and node[0] == 'define'
                         and node[1] == ['sha256-string?', 's'])
        self.assertIn('string-length', str(predicate))
        native_check = next(node for node in walk(tree) if len(node) > 1 and node[0] == 'define'
                            and node[1] == ['check-sha256-predicate!'])
        for name in ['positive-64-hex', 'literal-braces', 'short', 'long', 'nonhex',
                     'uppercase', 'nonstring']:
            self.assertIn('"' + name + '"', str(native_check))
        initialization = next(node for node in tree
                              if isinstance(node, list) and len(node) > 1 and node[0] == 'define-values'
                              and node[1] == ['known-modules', 'known-bytecode', 'prebuild-module-count'])
        self.assertEqual(initialization[2][0], 'with-handlers')
        self.assertEqual(initialization[2][2], ['check-sha256-predicate!'])
        self.assertEqual(src.count('(check-sha256-predicate!)'), 2)  # definition + one startup call

    def test_sha256_predicate_positive_and_refusal_models(self):
        def accepts(value):
            return isinstance(value, str) and len(value) == 64 and re.fullmatch('[0-9a-f]+', value) is not None
        examples = [('positive-64-hex', '0123456789abcdef' * 4, True),
                    ('literal-braces', 'a{64}', False), ('short', 'a' * 63, False),
                    ('long', 'a' * 65, False), ('nonhex', 'a' * 63 + 'g', False),
                    ('uppercase', 'A' * 64, False), ('nonstring', None, False)]
        for label, value, expected in examples:
            with self.subTest(label=label):
                self.assertIs(accepts(value), expected)

    def test_all_helper_regexp_literals_use_reviewed_common_syntax(self):
        # Review each Racket literal independently of Python's regex dialect.
        # Tight allowlist: adding a pattern requires an explicit source review.
        allowed = {'^[0-9a-f]+$', '[.]zo$', '^profile-', '^addon-tethered-',
                   '^[a-zA-Z]+://', '[.]rkt$'}
        seen = []
        for path in HERE.glob('*.rkt'):
            for kind, pattern in re.findall(r'#(rx|px)(?:#)?"((?:\\.|[^"\\])*)"', path.read_text()):
                self.assertEqual(kind, 'rx', path.name)
                self.assertIn(pattern, allowed, (path.name, pattern))
                self.assertNotIn('{', pattern)
                self.assertNotIn('}', pattern)
                self.assertNotIn('\\', pattern)
                seen.append((path.name, pattern))
        self.assertEqual(len(seen), 8)
        provenance = json.loads(self.source('API-PROVENANCE.json'))['evidence']
        manual = next(row['content'] for row in provenance
                      if row['path'] == 'pkgs/racket-doc/scribblings/reference/regexps.scrbl')
        grammar = next(row['content'] for row in provenance
                       if row['path'] == 'pkgs/racket-doc/scribblings/reference/rx.rkt')
        self.assertIn('@litchar["{"] and @litchar["}"] as literals', manual)
        self.assertIn('Atom{N}', grammar)
        self.assertIn('Match Atom exactly N times', grammar)

    def test_pinned_startup_order_and_boundary(self):
        ev = json.loads(self.source('API-PROVENANCE.json'))['evidence']
        main = next(x['content'] for x in ev if x['path'] == 'racket/src/cs/main.sps')
        self.assertIn('[("-t" "--require")', main)
        self.assertIn('(add-namespace-require-load! `(file ,file-name) file-name)', main)
        self.assertIn('(reverse loads)', main)
        self.assertIn('(current-command-line-arguments remaining-command-line-arguments)', main)
        self.assertIn('[("--")', main)


if __name__ == '__main__':
    unittest.main(verbosity=2)
