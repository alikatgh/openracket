"""Run exact native suite and reject skipped Darwin tests without modifying it."""
import importlib.util, json, os, pathlib, sys, unittest
root=pathlib.Path(sys.argv[1]).resolve(strict=True)
if sys.platform!='darwin' or sys.version_info<(3,13):raise SystemExit('Darwin Python>=3.13 required')
if not os.environ.get('OPENRACKET_TEST_PROCESS_HELPER') or not os.environ.get('OPENRACKET_TEST_PROCESS_HELPER_SHA256'):raise SystemExit('Both explicit native prerequisites required')
sys.path.insert(0,str(root/'ci/supervisor'))
spec=importlib.util.spec_from_file_location('native_suite',root/'ci/supervisor/tests/test_owned_process_supervisor.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
suite=unittest.defaultTestLoader.loadTestsFromModule(module)
result=unittest.TextTestRunner(verbosity=2).run(suite)
native_skips=[(test.id(),why) for test,why in result.skipped if '.DarwinNativeTests.' in test.id()]
required=unittest.defaultTestLoader.getTestCaseNames(module.DarwinNativeTests)
print(json.dumps({'schema':'openracket-native-prerequisite-tests/v1','native_test_names':required,'native_required':3,'native_skips':native_skips,'total_tests':result.testsRun,'passed':result.wasSuccessful() and not native_skips and len(required)==3}))
raise SystemExit(0 if result.wasSuccessful() and not native_skips and len(required)==3 else 1)
