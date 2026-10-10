import copy
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('compare_native', Path(__file__).with_name('compare-native-lexer.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ComparisonTests(unittest.TestCase):
    def fixture(self):
        return {'status': 'complete', 'racket_version': '9.3', 'preserved_preferences': {},
                'activation_environment': {key: 'unset' for key in module.APPEARANCE},
                'dont_stop_violations': 0,
                'cases': {key: {'text': 'λ', 'tokens_by_position': [[0, 'symbol', 0, 1]]}
                          for key in module.REQUIRED}}

    def test_matching(self):
        self.assertEqual(module.compare(self.fixture(), self.fixture())['status'], 'equivalent')

    def test_no_partial_or_appearance_mismatch(self):
        a, b = self.fixture(), self.fixture()
        b['status'] = 'failed'
        with self.assertRaises(ValueError): module.compare(a, b)
        b = self.fixture(); b['activation_environment']['OPENRACKET_HOST_THEME'] = 'dark'
        with self.assertRaises(ValueError): module.compare(a, b)

    def test_position_difference_detected(self):
        a, b = self.fixture(), self.fixture()
        b['cases']['definitions-insert']['tokens_by_position'] = [[0, 'string', 0, 1]]
        with self.assertRaisesRegex(ValueError, 'tokens_by_position'): module.compare(a, b)
