"""Pure fail-closed contracts for the frozen launcher-isolation path probe."""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat

FREEZE_PIN = 'd8e5844ae4ede6171a9f4bd1d89ba837eb656b06a006f61e53b888d44f6eedc2'
CLAIMS = {'CFBundleDocumentTypes', 'UTExportedTypeDeclarations', 'UTImportedTypeDeclarations'}
NATIVE_TIMEOUT = 120
CLEANUP_TIMEOUT = 5
MAX_NATIVE_LOG = 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def guard(env, system, machine):
    for key, expected in {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'alikatgh/openracket',
                          'GITHUB_REF': 'refs/heads/prototype/retained-drracket',
                          'GITHUB_EVENT_NAME': 'push'}.items():
        require(env.get(key) == expected, 'CI guard: ' + key)
    require(system == 'Darwin' and machine == 'arm64', 'Apple Silicon macOS required')
    event = json.loads(Path(env['GITHUB_EVENT_PATH']).read_text())
    repo = event['repository']
    require(repo.get('full_name') == 'alikatgh/openracket' and repo.get('private') is False
            and repo.get('visibility') == 'public', 'Public repository required')


def frozen_sources(root):
    require(not root.is_symlink() and root.is_dir(), 'Unsafe frozen source root')
    require(sha(root / 'MANIFEST.json') == FREEZE_PIN, 'Frozen manifest pin mismatch')
    members = json.loads((root / 'MANIFEST.json').read_text())
    require(type(members) is dict and len(members) == 26, 'Exactly26 frozen members required')
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Source symlink refused')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(members) | {'MANIFEST.json'}, 'Exact27-file source inventory required')
    for name, pin in members.items():
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts and path.as_posix() == name, 'Unsafe source path')
        source = root / path
        require(source.is_file() and source.stat().st_size == pin['bytes'] and sha(source) == pin['sha256'],
                'Frozen source mismatch: ' + name)
    return members


def selected_runtime(stock, temp, require_existing):
    require(stock.name == 'racket' and stock.parent.name == 'bin', 'Expected selected console executable')
    raw = stock.parent.parent
    # Resolve ancestor aliases (macOS /var -> /private/var) but never follow a
    # changed runtime leaf during final evidence collection.
    runtime = raw.parent.resolve(strict=require_existing) / raw.name
    require(runtime.is_relative_to(temp) and runtime != temp, 'Original runtime must be inside runner temporary root')
    if require_existing:
        require(runtime.is_dir() and not runtime.is_symlink(), 'Original runtime must be a real directory')
    return runtime


def inventory(root):
    """Independent lstat witness, including times; never traverse a symlink."""
    require(root.is_dir() and not root.is_symlink(), 'Unsafe runtime root')
    entries = {}
    def walk(path):
        info = path.lstat()
        row = {'mode': stat.S_IMODE(info.st_mode), 'mtime_ns': info.st_mtime_ns}
        if stat.S_ISLNK(info.st_mode):
            row.update(kind='link', target=os.readlink(path))
        elif stat.S_ISREG(info.st_mode):
            row.update(kind='file', bytes=info.st_size, sha256=sha(path))
        elif stat.S_ISDIR(info.st_mode):
            row.update(kind='directory')
        else:
            raise ValueError('Unexpected special runtime entry: ' + str(path))
        entries[path.relative_to(root).as_posix()] = row
        if row['kind'] == 'directory':
            for child in sorted(path.iterdir()):
                walk(child)
    walk(root)
    return entries


def tree_digest(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def changes(before, after):
    return [{'path': name, 'before': before.get(name), 'after': after.get(name)}
            for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]


def claims_present(rows):
    require(isinstance(rows, list), 'Missing complete plist rows')
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'plist', 'sha256', 'bundle_identifier', 'declarations'},
                'Malformed plist witness')
        require(isinstance(row['plist'], str) and isinstance(row['sha256'], str)
                and len(row['sha256']) == 64, 'Invalid plist path/hash')
        require(isinstance(row['declarations'], dict) and set(row['declarations']) <= CLAIMS, 'Malformed declaration data')
    return any(bool(row['declarations']) for row in rows)


def validate_audit(value, before):
    require(type(value.get('schema')) is int and value['schema'] == 1, 'Audit schema must be exact1')
    require(value.get('inventory') == before and value.get('inventory_digest') == tree_digest(before),
            'Audited runtime differs from independent pre-import baseline')
    claims_present(value.get('nested_apps'))
    require(isinstance(value.get('macho'), list) and value['macho'], 'Missing complete Mach-O rows')
    require(isinstance(value.get('static_loader_context_pending'), list), 'Missing loader-context diagnostic')
    return value['inventory_digest']


def validate_build(value, runtime, digest, handler):
    require(type(value.get('schema')) is int and value['schema'] == 1, 'Build schema must be exact1')
    require(value.get('status') == 'assembled-not-launched', 'Only assembled-not-launched is accepted')
    require(value.get('original_runtime') == str(runtime) and value.get('original_runtime_digest') == digest,
            'Build original runtime/digest mismatch')
    require(value.get('handler_baseline') == handler, 'Build handler differs from independent baseline')
    blocked = claims_present(value.get('nested_apps'))
    require(type(value.get('native_launch_blocked_by_declarations')) is bool
            and value['native_launch_blocked_by_declarations'] is blocked, 'Declaration block flag mismatch')
    require(value.get('manual_signing_or_security_changes') is False
            and value.get('intrinsic_generator_ad_hoc_signing') is True, 'Unexpected signing/security contract')
    require(isinstance(value.get('macho'), list) and value['macho']
            and isinstance(value.get('static_loader_context_pending'), list), 'Incomplete build metadata')
    require(isinstance(value.get('native_sha256'), str) and len(value['native_sha256']) == 64,
            'Missing generated native hash')
    return blocked


def validate_copy_plan(plan, original, build):
    require(original.get('DrRacket.app', {}).get('kind') == 'directory', 'Exact stock launcher directory missing')
    require(not any('/' not in name and name.casefold() == 'drracket.app' and name != 'DrRacket.app'
                    for name in original), 'Conflicting stock launcher spelling')
    excluded = {name: entry for name, entry in original.items()
                if name == 'DrRacket.app' or name.startswith('DrRacket.app/')}
    retained = {name: entry for name, entry in original.items() if name not in excluded}
    expected = {'schema': 1, 'excluded_path': 'DrRacket.app', 'original_inventory_digest': tree_digest(original),
                'original_entry_count': len(original), 'excluded_entries': excluded,
                'excluded_inventory_digest': tree_digest(excluded), 'excluded_entry_count': len(excluded),
                'retained_entry_count': len(retained), 'retained_inventory_digest': tree_digest(retained)}
    require(type(plan.get('schema')) is int and plan == expected, 'Exact fixed exclusion manifest mismatch')
    require(build.get('runtime_copy_plan') == 'runtime-copy-plan.json'
            and build.get('retained_runtime_digest') == tree_digest(retained), 'Build retained witness mismatch')
    return retained


def launch_gate(build):
    blocked = claims_present(build.get('nested_apps'))
    pending = build.get('static_loader_context_pending')
    require(isinstance(pending, list), 'Missing static loader contexts')
    require(type(build.get('native_launch_blocked_by_loader_context')) is bool
            and build['native_launch_blocked_by_loader_context'] is bool(pending), 'Loader block flag mismatch')
    require(type(build.get('native_launch_blocked_by_declarations')) is bool
            and build['native_launch_blocked_by_declarations'] is blocked, 'Declaration block flag mismatch')
    require(not blocked and pending == [], 'Remaining declarations or loader contexts block all native app launches')


def protected_witness(value, original, source):
    require(type(value.get('schema')) is int and value['schema'] == 1, 'Protected witness schema')
    require(value.get('original_runtime_unchanged') is True and value.get('source_unchanged') is True,
            'Protected input witness failed')
    require(value.get('original_runtime_before') == value.get('original_runtime_after') == tree_digest(original)
            and value.get('source_before') == value.get('source_after') == tree_digest(source),
            'Protected input witness digest mismatch')


def same_path(raw, expected):
    return isinstance(raw, str) and Path(raw).is_absolute() and Path(raw).resolve() == expected.resolve()


def validate_summary(value, original_app, relocated_app, work, baseline):
    require(type(value.get('schema')) is int and value['schema'] == 1
            and value.get('status') == 'bounded-path-probe-passed', 'Native path probe did not pass')
    require(value.get('clean_destination_tested') is False and value.get('full_distribution_acceptance') is False,
            'Unsupported distribution acceptance claim')
    require(value.get('original_runtime_present') is True and value.get('recorded_original_runtime_absent') is False,
            'Original runtime was removed or unavailable')
    require(type(value.get('initially_unset_handler_tested')) is bool
            and value['initially_unset_handler_tested'] is (baseline.get('default_handler') is None),
            'Initially-unset handler coverage mismatch')
    require(value.get('unresolved_static_loader_context') == [], 'Unresolved loader contexts remain')
    observations = value.get('observations')
    require(isinstance(observations, list) and len(observations) == 2, 'Exactly two native observations required')
    for index, app in enumerate((original_app, relocated_app)):
        row = observations[index]
        profile = work / ('run-profile-%d' % index)
        require(row.get('profile') == str(profile)
                and row.get('verdict') == {'status': 'path-and-identity-observation-validated',
                                          'bundle': str(app), 'profile': str(profile)}, 'Native observation location mismatch')
        require(isinstance(row.get('bundle_inventory_digest'), str) and len(row['bundle_inventory_digest']) == 64,
                'Missing native bundle witness')
        report = row.get('report', {})
        require(report.get('status') == 'observed' and type(report.get('schema')) is int and report['schema'] == 1,
                'Missing actual native report')
        require((report.get('version'), report.get('os'), report.get('gc')) == ('9.3', 'macosx', 'cs'),
                'Wrong native report runtime')
        identity, child = report.get('identity', {}), report.get('child', {})
        require(type(identity.get('pid')) is int and identity['pid'] > 0
                and identity.get('running_pid') == identity['pid'] and type(identity.get('running_pid')) is int
                and type(child.get('pid')) is int and child['pid'] > 0 and child['pid'] != identity['pid'],
                'Actual independent process identities missing')
        require(same_path(identity.get('process_image_path'), app / 'Contents/MacOS/ProbeNative')
                and same_path(identity.get('main_bundle_path'), app) and same_path(identity.get('running_bundle_path'), app)
                and identity.get('main_bundle_identifier') == 'org.openracket.relative-path-probe'
                and identity.get('running_bundle_identifier') == 'org.openracket.relative-path-probe'
                and identity.get('same_running_application') is True, 'Native outer application identity mismatch')
        require(child.get('status') == 'observed' and type(child.get('schema')) is int and child['schema'] == 1
                and (child.get('version'), child.get('gc')) == ('9.3', 'cs'), 'Console child observation missing')
        closure = row.get('active_non_system_dylib_closure')
        require(isinstance(closure, dict) and set(closure) == {'gui', 'child'}
                and all(isinstance(v, list) for v in closure.values()), 'Active dylib closure missing')
        require(json.loads((profile / 'result.json').read_text()) == report, 'Raw native result differs from summary')
        post = json.loads((profile / 'post-launch-witness.json').read_text())
        require(type(post.get('schema')) is int and post['schema'] == 1
                and post.get('bundle_unchanged') is True and post.get('owned_process_group_cleanup_certain') is True
                and post.get('handler_before') == post.get('handler_after') == baseline
                and post.get('bundle_before_digest') == post.get('bundle_after_digest') == row['bundle_inventory_digest'],
                'Native post-launch immutability/cleanup/default witness failed')
    require(observations[0]['bundle_inventory_digest'] == observations[1]['bundle_inventory_digest'],
            'Bundle inventory changed across relocation')


def verdict(assembled, observed, inputs_unchanged, handler_unchanged, transport_complete, errors):
    complete = all(x is True for x in (assembled, observed, inputs_unchanged, handler_unchanged, transport_complete)) and not errors
    return {'schema': 1, 'status': 'bounded-path-probe-passed' if complete else 'isolation-probe-failed-or-incomplete',
            'probe_complete': complete, 'two_location_path_identity_acceptance': complete,
            'original_inputs_unchanged': inputs_unchanged, 'default_handler_unchanged': handler_unchanged,
            'complete_evidence_transport': transport_complete, 'clean_destination_tested': False,
            'full_distribution_acceptance': False, 'original_preferences_file_separately_observed': False,
            'errors': list(errors)}


def wrap_bytes(path, source_relative_path=None):
    raw = path.read_bytes()
    require(len(raw) <= 16 * 1024 * 1024, 'Evidence exceeds16MiB; fail rather than truncate')
    return {'filename': path.name, 'source_relative_path': source_relative_path or path.name,
            'encoding': 'base64', 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'chunks': [base64.b64encode(raw[i:i + 8192]).decode() for i in range(0, len(raw), 8192)]}
