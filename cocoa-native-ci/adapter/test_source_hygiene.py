"""Read-only package checks: no extracted source, subprocesses or temp files."""
import copy
import io
import json
import lzma
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import run_native_ci as runner
import source_bundle as bundle

BASE = Path(__file__).resolve().parent.parent


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.payload = b'print(1)\n'
        self.row = {'path': 'one.py', 'bytes': len(self.payload),
                    'sha256': bundle.sha(self.payload), 'mode': 0o444}
        self.manifest = {'files': [self.row]}
        metadata = bundle.packed({'schema': 'openracket-source-only-frame/v1',
                                  'files': [self.row]})
        self.header = bundle.MAGIC + struct.pack('>I', len(metadata)) + metadata
        self.raw = lzma.compress(self.header + self.payload)

    def validate(self, raw, manifest=None, **pin_changes):
        pin = {'bytes': len(raw), 'sha256': bundle.sha(raw), **pin_changes}
        return bundle.validate_payload(raw, manifest or self.manifest, pin)

    def test_valid_frame_returns_exact_payload(self):
        rows, data, start = self.validate(self.raw)
        self.assertEqual(rows, [self.row])
        self.assertEqual(data[start:], self.payload)

    def test_trailing_concatenated_and_truncated_streams_rejected(self):
        for raw in (self.raw + b'extra', self.raw + self.raw, self.raw[:-1]):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                self.validate(raw)

    def test_header_payload_closure_and_member_hash_rejected(self):
        for plain in (b'wrong magic', self.header[:-1], self.header + self.payload[:-1],
                      self.header + self.payload + b'x', self.header + b'x' * len(self.payload)):
            with self.subTest(size=len(plain)), self.assertRaises(ValueError):
                self.validate(lzma.compress(plain))

    def test_pinned_size_type_and_hash_rejected(self):
        for change in ({'bytes': len(self.raw) + 1}, {'bytes': True},
                       {'bytes': bundle.MAX_COMPRESSED + 1}, {'sha256': '0' * 64}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(self.raw, **change)

    def test_decode_bound_rejected(self):
        metadata_size = len(self.header) - len(bundle.MAGIC) - 4
        with patch.object(bundle, 'MAX_TOTAL', len(self.payload)), \
             patch.object(bundle, 'MAX_MANIFEST', metadata_size), \
             self.assertRaisesRegex(ValueError, 'oversize source stream'):
            self.validate(lzma.compress(self.header + self.payload + b'x'))

    def test_manifest_member_metadata_must_match_frame(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['files'][0]['mode'] = 0o555
        with self.assertRaisesRegex(ValueError, 'member map/mode'):
            self.validate(self.raw, manifest)

    def test_manifest_paths_duplicates_modes_sizes_and_hashes_rejected(self):
        for change in ({'path': '../escape'}, {'path': '/absolute'}, {'path': 'a//b'},
                       {'path': 'trailing.'}, {'mode': 0o777}, {'bytes': True},
                       {'bytes': bundle.MAX_FILE + 1}, {'sha256': 'bad'}):
            manifest = {'files': [{**self.row, **change}]}
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(self.raw, manifest)
        for name in ('one.py', 'ONE.py'):
            manifest = {'files': [self.row, {**self.row, 'path': name}]}
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.validate(self.raw, manifest)

    def test_extract_uses_validator_before_creating_destination(self):
        part = BASE / 'source-parts/source-000.bin'
        pin = {'bytes': part.stat().st_size, 'sha256': bundle.sha(part.read_bytes())}
        # A single nonfinal chunk is truncated, even with its own correct hash.
        with patch.object(Path, 'mkdir', side_effect=AssertionError('must not write')):
            with self.assertRaises(ValueError):
                bundle.extract(part, self.manifest, pin, BASE / 'unused-test-destination')


class PackageTests(unittest.TestCase):
    def test_checked_in_package_decodes_without_writes_or_native_launches(self):
        with patch.object(Path, 'mkdir', side_effect=AssertionError('must not write')), \
             patch.object(runner, 'setup', side_effect=AssertionError('must not initialize native CI')):
            result = runner.validate_package()
        self.assertEqual((result['parts'], result['members']), (9, 1159))
        self.assertEqual((result['bundle_bytes'], result['raw_file_bytes']), (4689100, 20551193))
        self.assertTrue(result['decoded_members_verified'])
        self.assertFalse(result['materialized'])
        self.assertFalse(result['native_checks_run'])

    def test_cli_mode_needs_no_root_or_materialized_source(self):
        output = io.StringIO()
        with patch('sys.argv', ['run_native_ci.py', 'validate-package']), \
             patch.object(runner, 'validate_package', return_value={'checked': True}), \
             patch('sys.stdout', output):
            self.assertEqual(runner.main(), 0)
        self.assertEqual(json.loads(output.getvalue()), {'checked': True})

    def test_descriptor_pin_mismatch_rejected(self):
        with patch.object(runner, 'sha', return_value='0' * 64):
            with self.assertRaisesRegex(ValueError, 'manifest hash/type mismatch'):
                runner.public_inputs()

    def test_rebound_bundle_schema_format_fields_and_accounting_rejected(self):
        manifest, pin, parts = runner.public_inputs()
        for change in ({'schema': 'wrong'}, {'format': 'tar'}, {'extra': True},
                       {'members': pin['members'] + 1}, {'raw_file_bytes': 1},
                       {'bytes': True}, {'members': float(pin['members'])},
                       {'raw_file_bytes': float(pin['raw_file_bytes'])},
                       {'sha256': '0' * 64}, {'bytes': pin['bytes'] + 1}):
            # Model reviewed descriptor changes after rebinding their raw hash pins.
            with self.subTest(change=change), \
                 patch.object(runner.json, 'loads', side_effect=[manifest, {**pin, **change}, parts]), \
                 self.assertRaises(ValueError):
                runner.public_inputs()

    def test_rebound_public_schema_and_extra_fields_rejected(self):
        manifest, pin, parts = runner.public_inputs()
        for change in ({'schema': 'wrong'}, {'extra': True}):
            with self.subTest(change=change), \
                 patch.object(runner.json, 'loads', side_effect=[{**manifest, **change}, pin, parts]), \
                 self.assertRaisesRegex(ValueError, 'manifest schema'):
                runner.public_inputs()

    def test_part_reordering_missing_extra_size_and_envelope_mismatch_rejected(self):
        _, _, parts = runner.public_inputs()
        directory = BASE / 'source-parts'
        for change in ({'parts': list(reversed(parts['parts']))}, {'bytes': parts['bytes'] + 1},
                       {'sha256': '0' * 64}, {'schema': 'wrong'}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                bundle.read_parts(directory, {**parts, **change})
        entries = list(directory.iterdir())
        for listing in (entries[:-1], entries + [directory / 'extra.bin']):
            with patch.object(Path, 'iterdir', return_value=iter(listing)), \
                 self.assertRaisesRegex(ValueError, 'Unexpected/missing'):
                bundle.read_parts(directory, parts)
        changed = copy.deepcopy(parts)
        changed['parts'][0]['bytes'] -= 1
        with self.assertRaises(ValueError):
            bundle.read_parts(directory, changed)

    def test_actual_part_byte_tampering_rejected_in_memory(self):
        _, _, parts = runner.public_inputs()
        original_read = Path.read_bytes

        def tampered_read(path):
            raw = original_read(path)
            return bytes([raw[0] ^ 1]) + raw[1:] if path.name == 'source-000.bin' else raw

        with patch.object(Path, 'read_bytes', tampered_read), \
             self.assertRaisesRegex(ValueError, 'Part SHA mismatch'):
            bundle.read_parts(BASE / 'source-parts', parts)

    def test_symlinked_part_or_directory_rejected(self):
        _, _, parts = runner.public_inputs()
        for name in ('source-parts', 'source-000.bin'):
            with self.subTest(name=name), \
                 patch.object(Path, 'is_symlink', lambda path: path.name == name), \
                 self.assertRaises(ValueError):
                bundle.read_parts(BASE / 'source-parts', parts)


if __name__ == '__main__':
    unittest.main(verbosity=2)
