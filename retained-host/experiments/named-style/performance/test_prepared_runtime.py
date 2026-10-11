"""Arm-input and installed additive-source verification, without a native process."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import accept_gui
import capture
import prepare_gui
from test_gui_source import HERE, originals_for_arm

HELPERS = {'gui-observer.rkt', 'gui-phase.rkt', 'capture-host.rkt', 'memory-profile.rkt',
           'activation.rkt', 'heartbeat.rkt', 'binding-export.rkt', 'style-witness.rkt'}
EXTRA = ('activation.rkt', 'heartbeat.rkt', 'binding-export.rkt', 'style-witness.rkt')

def sha(data): return hashlib.sha256(data).hexdigest()

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.synthetic_styles = {arm: ('synthetic style '+arm).encode() for arm in ('stock','candidate')}
        self.style_pins = {arm+'_sha256': sha(raw) for arm,raw in self.synthetic_styles.items()}
        self.pin_patch = patch.object(prepare_gui, 'style_pins', return_value=self.style_pins)
        self.pin_patch.start(); self.addCleanup(self.pin_patch.stop)

    def fixture(self, arm):
        root = self.base / arm; root.mkdir()
        source = root / 'share/pkgs/drracket-core-lib/drracket/private'
        (source / 'syncheck').mkdir(parents=True)
        originals = originals_for_arm(arm)
        for name, text in originals.items(): (source / name).write_bytes(text.encode())
        self.assertEqual(prepare_gui.verify_sources(source, root, arm), originals)
        transformed = {name: prepare_gui.TRANSFORMS[name](text) for name, text in originals.items()}
        for name, text in transformed.items(): (source / name).write_bytes(text.encode())
        racket = root / 'bin/racket'; racket.parent.mkdir(); racket.write_bytes(b'non-executable fixture')
        style = root/'share/pkgs/snip-lib/racket/snip/private/style.rkt'; style.parent.mkdir(parents=True); style.write_bytes(self.synthetic_styles[arm])
        manifest = dict(style_source=prepare_gui.verify_style_source(style, root, arm), schema_version=1, arm=arm, diagnostic_root=str(root), source_root=str(source), racket=str(racket),
                        stock_pins=prepare_gui.PINS, original_pins=prepare_gui.arm_pins(arm),
                        diagnostic_sources={name: sha(text.encode()) for name, text in transformed.items()},
                        helpers={name: sha((HERE / name).read_bytes()) for name in HELPERS},
                        helper_paths={name: str(HERE / name) for name in HELPERS}, compiled=True, compile_exit_code=0)
        path = root / 'openracket-gui-phase-manifest.json'; path.write_text(json.dumps(manifest))
        return path, manifest, source

    def verify(self, path, arm): return accept_gui.verify_runtime(path, HERE, EXTRA, arm)

    def test_both_exact_arm_inputs_and_transforms_verify(self):
        for arm in ('stock', 'candidate'):
            path, manifest, source = self.fixture(arm)
            self.assertEqual(self.verify(path, arm), manifest['diagnostic_sources'])
            with self.assertRaises(ValueError): self.verify(path, 'candidate' if arm == 'stock' else 'stock')

    def test_declared_hash_cannot_hide_unapproved_original_or_transform_delta(self):
        path, manifest, source = self.fixture('candidate')
        gui = source / 'syncheck/gui.rkt'
        for original in (gui.read_bytes() + b'\n', gui.read_bytes().replace(b'(20 . <= .', b'(19 . <= .')):
            gui.write_bytes(original)
            manifest['diagnostic_sources']['syncheck/gui.rkt'] = sha(original)
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'exact pinned additive transform'): self.verify(path, 'candidate')

    def test_production_hash_cannot_substitute_for_installed_observed_hash(self):
        path, manifest, source = self.fixture('candidate')
        manifest['diagnostic_sources']['syncheck/gui.rkt'] = manifest['original_pins']['syncheck/gui.rkt']
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'Actual diagnostic source differs'): self.verify(path, 'candidate')

    def test_helper_path_hash_set_and_compile_proof_fail_closed(self):
        path, manifest, _ = self.fixture('stock')
        changes = [lambda m: m.update(compiled=False), lambda m: m.update(compile_exit_code=True),
                   lambda m: m['helpers'].pop('binding-export.rkt'),
                   lambda m: m['helpers'].update({'binding-export.rkt': '0'*64}),
                   lambda m: m['helper_paths'].update({'activation.rkt': '/foreign/activation.rkt'}),
                   lambda m: m['original_pins'].update({'syncheck/gui.rkt': '0'*64}),
                   lambda m: m.update(arm='candidate')]
        for mutate in changes:
            value = copy.deepcopy(manifest); mutate(value); path.write_text(json.dumps(value))
            with self.subTest(mutate=mutate), self.assertRaises(ValueError): self.verify(path, 'stock')

    def test_linked_hardlinked_and_foreign_sources_are_refused(self):
        path, manifest, source = self.fixture('stock')
        gui = source / 'syncheck/gui.rkt'; saved = gui.read_bytes()
        elsewhere = self.base / 'elsewhere.rkt'; elsewhere.write_bytes(saved)
        gui.unlink(); gui.symlink_to(elsewhere)
        with self.assertRaises(ValueError): self.verify(path, 'stock')
        gui.unlink(); gui.hardlink_to(elsewhere)
        with self.assertRaises(ValueError): self.verify(path, 'stock')
        gui.unlink(); gui.write_bytes(saved)
        moved = self.base / 'openracket-gui-phase-manifest.json'; moved.write_bytes(path.read_bytes())
        with self.assertRaises(ValueError): self.verify(moved, 'stock')

    def test_transform_marker_spoofing_and_wrong_arm_input_refused(self):
        path, manifest, source = self.fixture('candidate')
        originals = originals_for_arm('candidate')
        for name, text in originals.items(): (source / name).write_bytes(text.encode())
        self.assertEqual(prepare_gui.verify_sources(source, source.parents[4], 'stock'), originals)
        for name, text in originals.items():
            changed = prepare_gui.TRANSFORMS[name](text)
            if 'GUI-OBSERVE-BEGIN' in changed:
                malformed = changed.replace('GUI-OBSERVE-END', 'GUI-OBSERVE-WRONG-END', 1)
                self.assertNotEqual(prepare_gui.undo_transform(malformed), text)

    def test_actual_style_hash_path_alias_and_foreign_runtime_fail_closed(self):
        path, manifest, _ = self.fixture('candidate')
        style = Path(manifest['style_source']['source']); saved = style.read_bytes()
        for raw in (b'wrong style', b'x' * (1024 * 1024 + 1)):
            style.write_bytes(raw)
            with self.assertRaises(ValueError):self.verify(path,'candidate')
        style.write_bytes(saved)
        other = self.base/'foreign-style.rkt'; other.write_bytes(saved)
        style.unlink();style.symlink_to(other)
        with self.assertRaises(ValueError):self.verify(path,'candidate')
        style.unlink();style.hardlink_to(other)
        with self.assertRaises(ValueError):self.verify(path,'candidate')
        style.unlink();style.write_bytes(saved)
        for change in ({'source':str(other)}, {'sha256':'0'*64}, {'module':'wrong'}):
            m=copy.deepcopy(manifest);m['style_source'].update(change);path.write_text(json.dumps(m))
            with self.assertRaises(ValueError):self.verify(path,'candidate')

if __name__ == '__main__': unittest.main()
