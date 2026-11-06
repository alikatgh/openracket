#!/usr/bin/env python3
"""Small replay-evidence regressions using the real codec and memory-only I/O."""
import contextlib
import hashlib
import importlib.util
import io
import json
import pathlib
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_codec(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / 'retained-host' / 'scripts' / 'ci' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


emitter = load_codec('edge_evidence_emitter', 'emit-replay-evidence.py')
decoder = load_codec('edge_evidence_decoder', 'decode-replay-evidence.py')


class EvidenceEdgeTests(unittest.TestCase):
    def frames(self, value):
        # Exercise emit(), including its framing and digests, without a temp file.
        source = mock.Mock(spec=pathlib.Path)
        source.name = 'replay.json'
        source.stem = 'replay'
        source.parent.name = 'runtime'
        source.is_file.return_value = True
        source.is_symlink.return_value = False
        source.read_bytes.return_value = json.dumps(value, ensure_ascii=False).encode()
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            emitter.emit(source)
        return stream.getvalue().splitlines()

    def sink(self):
        output = mock.MagicMock(spec=pathlib.Path)
        path = output.__truediv__.return_value
        path.exists.return_value = False
        return output, path

    def assert_rejected(self, lines, message=None):
        output, path = self.sink()
        with self.assertRaisesRegex(AssertionError, message or ''):
            decoder.decode('\n'.join(lines), output)
        output.mkdir.assert_not_called()
        path.write_text.assert_not_called()

    def test_falsy_and_nested_null_payloads_roundtrip_with_exact_types_and_digest(self):
        for value in (None, False, 0, '', [], {}, {'rows': [None, False, 0, 'λ🌱']}):
            with self.subTest(value=value):
                output, path = self.sink()
                rows = decoder.decode('\n'.join(self.frames(value)), output)
                self.assertEqual(len(rows), 1)
                path.write_text.assert_called_once()
                restored = json.loads(path.write_text.call_args.args[0])
                self.assertEqual(type(restored), type(value))
                self.assertEqual(decoder.packed(restored), decoder.packed(value))
                expected = hashlib.sha256(decoder.packed(value).encode()).hexdigest()
                self.assertEqual(rows[0]['canonical_sha256'], expected)

    def test_mixed_duplicate_null_payloads_are_rejected_before_writing(self):
        for first, second in ((None, {}), ({}, None), (None, False), (0, None)):
            with self.subTest(first=first, second=second):
                lines = self.frames(first)
                duplicate = self.frames(second)[1]
                self.assert_rejected(lines[:2] + [duplicate] + lines[2:],
                                     'Repeated evidence document payload')

    def test_missing_payload_and_eof_are_distinct_from_explicit_null(self):
        lines = self.frames(None)
        self.assert_rejected([lines[0], lines[-1]], 'Missing evidence document payload')
        for prefix in (lines[:1], lines[:2]):
            with self.subTest(prefix=prefix):
                self.assert_rejected(prefix, 'Truncated evidence document')

    def test_null_cannot_bypass_whole_document_digest(self):
        for original, replacement in ((None, False), (None, 0), ({'ok': True}, None)):
            with self.subTest(original=original, replacement=replacement):
                lines = self.frames(original)
                lines[1] = self.frames(replacement)[1]
                self.assert_rejected(lines, 'Whole-document hash mismatch')

    def test_null_payload_cannot_hide_unreferenced_array_chunks(self):
        lines = self.frames(None)
        marker, body = lines[0].split(' ', 1)
        header = json.loads(body)
        header['arrays'] = 1
        lines[0] = marker + ' ' + json.dumps(header)
        lines.insert(2, 'OPENRACKET_REPLAY_ARRAY_JSON ' + json.dumps(
            {'label': 'runtime-replay', 'id': 0, 'index': 0, 'items': [None]}))
        self.assert_rejected(lines)

    def test_repeated_begin_after_null_payload_is_rejected(self):
        lines = self.frames(None)
        self.assert_rejected(lines[:2] + [lines[0]] + lines[2:],
                             'Repeated begin without end')

    def test_adjacent_json_objects_in_evidence_record_are_rejected_before_writing(self):
        lines = self.frames(None)
        lines[1] += ' {}'
        output, path = self.sink()
        with self.assertRaises(json.JSONDecodeError):
            decoder.decode('\n'.join(lines), output)
        output.mkdir.assert_not_called()
        path.write_text.assert_not_called()

    def test_corrupt_null_payload_record_does_not_count_as_present(self):
        # Non-object suffixes no longer match a marked JSON log record. The END
        # record must still reject the resulting absent payload, rather than
        # confusing the decoder's initial None with an explicitly received null.
        for suffix in (' null', ' true', ' garbage', '\x00'):
            with self.subTest(suffix=suffix):
                lines = self.frames(None)
                lines[1] += suffix
                self.assert_rejected(lines, 'Missing evidence document payload')


if __name__ == '__main__':
    unittest.main(verbosity=2)
