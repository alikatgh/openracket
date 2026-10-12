"""Synthetic dyld witnesses only. No Apple runtime or native FFI is executed."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from test_source import ROOT, fake_macho, image_snapshot, s

WEBKIT = '/System/Library/Frameworks/WebKit.framework/Versions/A/WebKit'
CRYPTEX = '/System/Volumes/Preboot/Cryptexes/OS' + WEBKIT


class SharedCache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve(strict=True)
        self.app = self.base / "Probe λ's.app"
        self.app.mkdir()
        self.main = self.app / 'main'
        self.main.write_bytes(fake_macho())
        self.images = [str(self.main), WEBKIT]
        self.snapshot = image_snapshot(self.images, [WEBKIT])

    def tearDown(self):
        self.temp.cleanup()

    def classify(self):
        return s.classify_loaded_images(self.images, self.snapshot, self.app)

    def test_missing_shared_cache_image_never_requires_disk_resolution(self):
        real = s.existing
        def strict(path):
            if str(path) in (WEBKIT, CRYPTEX):
                raise AssertionError('virtual cache name resolved as standalone file')
            return real(path)
        with mock.patch.object(s, 'existing', side_effect=strict):
            result = self.classify()
        self.assertEqual(result[1], {'raw': WEBKIT, 'kind': 'os-shared-cache', 'witness_index': 1})
        self.assertEqual(self.snapshot['records'][1]['raw'], WEBKIT)

    def test_exact_webkit_cryptex_alias_regression(self):
        # Model macOS realpath's Cryptex target outside the old static roots.
        resolve = Path.resolve
        def redirected(path, strict=False):
            if str(path) == WEBKIT:
                if strict:
                    raise FileNotFoundError(CRYPTEX)
                return Path(CRYPTEX)
            return resolve(path, strict=strict)
        with mock.patch.object(Path, 'resolve', redirected):
            self.assertFalse(s.is_system_path(WEBKIT))
            with self.assertRaises(FileNotFoundError):
                s.existing(WEBKIT)
            self.assertEqual(self.classify()[1]['kind'], 'os-shared-cache')

    def test_real_dangling_alias_fixture_with_explicit_test_roots(self):
        # This is a genuine symlink fixture. Its test root is never a production allowlist.
        system = self.base / 'System/Library'; system.mkdir(parents=True)
        alias = system / 'WebKit'; alias.symlink_to('../../Cryptex/missing')
        self.images[1] = str(alias)
        self.snapshot = image_snapshot(self.images, [str(alias)])
        with mock.patch.object(s, 'SYSTEM_ROOTS', (str(system) + '/',)):
            self.assertFalse(s.is_system_path(alias))
            self.assertEqual(self.classify()[1]['kind'], 'os-shared-cache')
            self.snapshot['records'][1]['flags'] = 0
            with self.assertRaisesRegex(s.Refusal, 'no file or cache proof'): self.classify()

    def test_missing_cache_api_result_refused(self):
        del self.snapshot['records'][1]['shared_cache_contains_path']
        with self.assertRaises(s.Refusal): self.classify()

    def test_false_cache_api_result_refused(self):
        self.snapshot['records'][1]['shared_cache_contains_path'] = False
        with self.assertRaisesRegex(s.Refusal, 'unproved OS shared-cache'): self.classify()

    def test_absent_cache_header_flag_refused(self):
        self.snapshot['records'][1]['flags'] = 0
        with self.assertRaises(s.Refusal): self.classify()

    def test_missing_snapshot_refused(self):
        self.snapshot = None
        with self.assertRaises(s.Refusal): self.classify()

    def test_missing_record_refused(self):
        self.snapshot['records'].pop()
        with self.assertRaises(s.Refusal): self.classify()

    def test_mismatched_index_or_name_refused(self):
        for key, value in [('index', 0), ('raw', CRYPTEX), ('raw', str(self.main))]:
            with self.subTest(key=key, value=value):
                snapshot = copy.deepcopy(self.snapshot)
                snapshot['records'][1][key] = value
                with self.assertRaises(s.Refusal):
                    s.classify_loaded_images(self.images, snapshot, self.app)

    def test_non_system_and_cryptex_only_forged_names_refused(self):
        for raw in [CRYPTEX, str(self.app / 'missing.dylib'), '/Applications/Racket/lib/missing',
                    '/tmp/missing.dylib', '/System/LibraryExtra/missing', '/usr/library/missing']:
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(s.Refusal, 'unproved OS shared-cache'):
                    s.classify_loaded_images([raw], image_snapshot([raw], [raw]), self.app)

    def test_lexical_traversal_and_noncanonical_names_refused(self):
        for raw in ['/System/Library/../../tmp/x', '/usr/lib/../lib/x', '/usr/lib/./x',
                    '/usr/lib//x', '//usr/lib/x', '/usr/lib/x/', '/usr/lib/x\0other']:
            with self.subTest(raw=raw):
                with self.assertRaises(s.Refusal):
                    s.classify_loaded_images([raw], image_snapshot([raw], [raw]), self.app)

    def test_unproved_missing_system_image_refused(self):
        raw = '/usr/lib/openracket-synthetic-missing.dylib'
        with self.assertRaisesRegex(s.Refusal, 'no file or cache proof'):
            s.classify_loaded_images([raw], image_snapshot([raw]), self.app)

    def test_missing_app_image_refused_even_with_cache_path_result(self):
        self.main.unlink()
        self.snapshot['records'][0]['shared_cache_contains_path'] = True
        with self.assertRaisesRegex(s.Refusal, 'no file or cache proof'): self.classify()

    def test_app_symlink_escape_refused(self):
        outside = self.base / 'outside'; outside.write_bytes(fake_macho())
        self.main.unlink(); self.main.symlink_to(outside)
        with self.assertRaisesRegex(s.Refusal, 'external loaded image'): self.classify()

    def test_system_symlink_escape_without_both_native_proofs_refused(self):
        system = self.base / 'System/Library'; system.mkdir(parents=True)
        outside = self.base / 'outside'; outside.write_bytes(fake_macho())
        alias = system / 'image'; alias.symlink_to(outside)
        with mock.patch.object(s, 'SYSTEM_ROOTS', (str(system) + '/',)):
            with self.assertRaisesRegex(s.Refusal, 'external loaded image'):
                s.classify_loaded_images([str(alias)], image_snapshot([str(alias)]), self.app)

    def test_exact_boolean_and_integer_types(self):
        changes = [('schema', True), ('count', True), ('count', 2.0), ('stable', 1), ('stable', False)]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                witness = copy.deepcopy(self.snapshot); witness[key] = value
                with self.assertRaises(s.Refusal):
                    s.classify_loaded_images(self.images, witness, self.app)
        for key in ['index', 'magic', 'cpu_type', 'file_type', 'flags', 'shared_cache_contains_path']:
            values = [True, 1.0, '1', None, -1, 2**32] if key != 'shared_cache_contains_path' else [0, 1, 'true', None]
            for value in values:
                with self.subTest(key=key, value=value):
                    witness = copy.deepcopy(self.snapshot); witness['records'][1][key] = value
                    with self.assertRaises(s.Refusal):
                        s.classify_loaded_images(self.images, witness, self.app)

    def test_wrong_magic_architecture_or_file_type_refused(self):
        for key, value in [('magic', 0xFEEDFACE), ('cpu_type', 0x01000007), ('file_type', 2)]:
            with self.subTest(key=key):
                witness = copy.deepcopy(self.snapshot); witness['records'][1][key] = value
                with self.assertRaises(s.Refusal):
                    s.classify_loaded_images(self.images, witness, self.app)

    def test_duplicate_or_invalid_header_address_refused(self):
        for address in ['0', '', True, '0x100000', '-1', 'f'*17, self.snapshot['records'][0]['header_address']]:
            with self.subTest(address=address):
                witness = copy.deepcopy(self.snapshot); witness['records'][1]['header_address'] = address
                with self.assertRaises(s.Refusal):
                    s.classify_loaded_images(self.images, witness, self.app)

    def test_duplicate_image_name_refused(self):
        images = [WEBKIT, WEBKIT]
        with self.assertRaises(s.Refusal):
            s.classify_loaded_images(images, image_snapshot(images, [WEBKIT]), self.app)

    def test_cache_classification_used_by_active_closure(self):
        self.main.write_bytes(fake_macho([WEBKIT]))
        with mock.patch.object(s, 'is_system_path', return_value=False):
            result = s.loaded_closure(self.app, self.images, self.main,
                                      s.macho_inventory(self.app), self.snapshot)
        self.assertEqual(result, [{'image': str(self.main), 'dependency': WEBKIT, 'system': True}])

    def test_cache_evidence_does_not_satisfy_missing_runtime_dependency(self):
        self.main.write_bytes(fake_macho(['@executable_path/missing-runtime']))
        with self.assertRaisesRegex(s.Refusal, 'no measured resolution'):
            s.loaded_closure(self.app, self.images, self.main, s.macho_inventory(self.app), self.snapshot)

    def test_native_source_contract_uses_public_api_and_stable_paired_snapshot(self):
        text = (ROOT / 'probe/dyld.rkt').read_text()
        for token in ['_dyld_get_image_header', '_dyld_shared_cache_contains_path', '_stdbool',
                      "'index i 'raw raw", '(ptr-ref mh _uint32 6)', '(ptr-equal?', '(= n (count))']:
            self.assertIn(token, text)
        self.assertEqual(text.count('  (check-stable!)'), 2)
        self.assertNotIn('_dyld_get_shared_cache_range', text)
        self.assertNotIn('_dyld_shared_cache_real_path', text)
        for relative in ['probe/gui.rkt', 'probe/child.rkt']:
            source = (ROOT / relative).read_text()
            self.assertIn('(define-values (images snapshot) (loaded-image-snapshot))', source)
            self.assertIn("'loaded_images images 'loaded_image_snapshot snapshot", source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
