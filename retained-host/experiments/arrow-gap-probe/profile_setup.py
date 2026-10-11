"""Pre-timing, bounded setup of one authorized preference in a fresh profile."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

MIB = 1024 * 1024
PINS = {'eval_helpers': 'e32ed81fbbc6b85ce8149cbcf486c50321ece7fc3668931a394f36e91c401b62',
        'framework_preferences': '59269376296892080cdbc7421e10015e99f8165d3a9c1051254ed7b81097af5c'}
KEY = 'drracket:child-only-memory-limit'
DISK_KEY = 'plt:framework-pref:' + KEY


def validate_setup(report, limit_mib, env, racket):
    errors = []
    def check(value, message):
        if not value:
            errors.append(message)
    expected = limit_mib * MIB
    root = Path(racket).resolve().parents[1]
    check(type(limit_mib) is int and limit_mib in (128, 256, 512), 'Unsupported requested limit')
    check(report.get('status') == 'verified' and report.get('phase') == 'before-timed-gui', 'Setup did not verify')
    check(report.get('runtime_version') == '9.3', 'Wrong runtime version')
    check(Path(report.get('runtime_root', '')).resolve() == root, 'Wrong runtime root')
    check(Path(report.get('runtime_executable', '')).resolve() == Path(racket).resolve(), 'Wrong setup executable')
    for key in ('expected_limit_bytes', 'selected_limit_bytes', 'readback_limit_bytes', 'persisted_limit_bytes'):
        check(type(report.get(key)) is int and report.get(key) == expected, 'Wrong setup field: ' + key)
    check(report.get('original_default_limit_bytes') == report.get('expected_default_limit_bytes') == 128 * MIB,
          'Fresh stock default differs')
    check(report.get('preference_key') == KEY and report.get('persisted_preference_key') == DISK_KEY, 'Wrong changed key')
    check(report.get('profile_was_empty') is True and report.get('addon_was_empty') is True and
          report.get('gui_initialized') is False and report.get('only_expected_preference_changed') is True,
          'Fresh one-key headless setup not established')
    check(report.get('legacy_preference_store_absent') is True and
          report.get('runtime_fallback_store_absent') is True, 'Fallback profile isolation not established')
    home, addon = (Path(env[k]).resolve() for k in ('PLTUSERHOME', 'PLTADDONDIR'))
    check(Path(report.get('profile_path', '')).resolve() == home and
          Path(report.get('addon_path', '')).resolve() == addon, 'Active profiles do not match intended paths')
    store = Path(report.get('preference_store_path', '')).resolve()
    check(store.is_relative_to(home), 'Preference store outside fresh home')
    check(store.is_file() and not store.is_symlink() and store.stat().st_size <= 1024 * 1024 and
          hashlib.sha256(store.read_bytes()).hexdigest() == report.get('preference_store_sha256'),
          'Actual persisted store hash differs before GUI launch')
    check(report.get('disk_key_count_before') == 0 and report.get('disk_key_count_after') == 1 and
          report.get('one_key_delta') == [{'key': DISK_KEY, 'before_present': False, 'after_value': expected}],
          'Persisted delta is not exactly the one memory key')
    sources = report.get('sources', {})
    check(set(sources) == set(PINS), 'Setup source evidence incomplete')
    for key, pin in PINS.items():
        row = sources.get(key, {})
        check(row.get('sha256') == row.get('expected_sha256') == pin and
              Path(row.get('path', '')).resolve().is_relative_to(root), 'Wrong original setup source: ' + key)
    return errors


def prepare_memory_profile(args, env, directory, terminate_group, *, timeout_seconds=30):
    started = time.monotonic()
    output = directory / 'memory-profile.json'
    helper = args.profile_helper.resolve()
    result = {'verified': False, 'gui_started': False, 'timeout': False, 'errors': [], 'configuration': None}
    try:
        if args.memory_limit_mib not in (128, 256, 512):
            raise ValueError('Unsupported requested memory limit')
        if not helper.is_file() or args.profile_helper.is_symlink():
            raise ValueError('Missing reviewed regular profile helper')
        if not env.get('PLTADDONDIR') or not Path(env['PLTADDONDIR']).is_absolute():
            raise ValueError('Explicit fresh absolute PLTADDONDIR required')
        addon = Path(env['PLTADDONDIR'])
        if addon.is_symlink():
            raise ValueError('PLTADDONDIR may not be a symlink')
        addon.mkdir(parents=True, exist_ok=True)
        result['helper_sha256'] = hashlib.sha256(helper.read_bytes()).hexdigest()
        command = [str(args.racket), str(helper), '--limit-mib', str(args.memory_limit_mib),
                   '--output', str(output), '--runtime-root', str(Path(args.racket).resolve().parents[1])]
        result['command'] = command
        with (directory / 'profile-setup.stdout.log').open('w') as out, (directory / 'profile-setup.stderr.log').open('w') as err:
            process = subprocess.Popen(command, env=env, stdout=out, stderr=err, start_new_session=True)
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                result['timeout'] = True
                terminate_group(process)
        result['exit_code'] = process.returncode
        if output.exists():
            if output.is_symlink() or output.stat().st_size > 32768:
                raise ValueError('Invalid setup evidence file')
            result['configuration'] = json.loads(output.read_text())
        if result['timeout'] or process.returncode != 0:
            result['errors'].append('Headless profile setup failed or timed out')
        if isinstance(result['configuration'], dict):
            result['errors'].extend(validate_setup(result['configuration'], args.memory_limit_mib, env, args.racket))
        else:
            result['errors'].append('No structured profile setup evidence')
        result['verified'] = not result['errors']
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        result['errors'].append(str(error))
    result['elapsed_ms_before_timed_process'] = (time.monotonic() - started) * 1000
    stderr = directory / 'profile-setup.stderr.log'
    if not result['verified'] and stderr.exists():
        result['stderr_tail'] = stderr.read_text(errors='replace')[-4000:]
    return result
