"""Pure fail-closed contracts for the frozen launcher-isolation path probe."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import posixpath
import re

FREEZE_PIN = '2bbdcfe499a35de6d2a12b1c3b62a0f57c4b69eeee5394300782d1297ba5fb48'
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
    require(type(members) is dict and len(members) == 36, 'Exactly36 frozen members required')
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Source symlink refused')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(members) | {'MANIFEST.json'}, 'Exact37-file source inventory required')
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


def same_json(left, right):
    # Python considers False == 0 and 1 == 1.0. Recorded JSON proof must bind
    # both values and their JSON types, including nested independent documents.
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def exact_fields(value, fields, message):
    require(isinstance(value, dict) and set(value) == set(fields), message)


def recorded_path(value):
    """Pure normalized POSIX name check; never consult a relocated filesystem."""
    return (isinstance(value, str) and value.startswith('/') and not value.startswith('//')
            and '\0' not in value and str(PurePosixPath(value)) == value
            and '..' not in PurePosixPath(value).parts)


def recorded_inside(value, root):
    return recorded_path(value) and recorded_path(str(root)) and PurePosixPath(value).is_relative_to(PurePosixPath(root))


def recorded_system(value):
    return recorded_path(value) and any(value.startswith(root) for root in ('/System/Library/', '/usr/lib/'))


def recorded_sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def recorded_macho(build, original_app, baseline):
    require(build.get('bundle') == str(original_app) and same_json(build.get('handler_baseline'), baseline),
            'Build location/default baseline mismatch')
    require(build.get('status') == 'assembled-not-launched' and recorded_sha(build.get('native_sha256')),
            'Missing generated native identity')
    launch_gate(build)
    rows = build.get('macho')
    require(isinstance(rows, list) and rows, 'Missing recorded Mach-O inventory')
    indexed = {}
    for row in rows:
        exact_fields(row, {'path', 'sha256', 'slices'}, 'Malformed recorded Mach-O inventory row')
        name = row['path']
        require(isinstance(name, str) and name and name != '.' and not name.startswith('/') and '\0' not in name
                and str(PurePosixPath(name)) == name and '..' not in PurePosixPath(name).parts
                and name not in indexed and recorded_sha(row['sha256']), 'Invalid or duplicate Mach-O identity')
        parts = row['slices']
        require(isinstance(parts, list) and parts, 'Missing Mach-O slices')
        for part in parts:
            exact_fields(part, {'cpu_type', 'dependencies', 'rpaths'}, 'Malformed Mach-O slice')
            require(type(part['cpu_type']) is int and 0 <= part['cpu_type'] <= 0xffffffff, 'Invalid Mach-O CPU type')
            for key in ('dependencies', 'rpaths'):
                require(isinstance(part[key], list) and all(isinstance(s, str) and s and '\0' not in s for s in part[key]),
                        'Invalid recorded loader names')
        arm = [part for part in parts if part['cpu_type'] == 0x0100000C]
        require(len(arm) == 1, 'Missing or duplicate recorded arm64 slice')
        indexed[name] = {'sha256': row['sha256'], **arm[0]}
    native = indexed.get('Contents/MacOS/ProbeNative', {})
    require(native.get('sha256') == build['native_sha256'], 'Generated native hash differs from Mach-O inventory')
    require('Contents/Resources/runtime/bin/racket' in indexed, 'Console executable absent from Mach-O inventory')
    return indexed


def recorded_images(observed, classifications, app, executable, inventory):
    """Bind frozen launch-time classifications to the exact same raw witnesses.

    This checks recorded proof, not current file existence. File resolution was
    performed by the pinned supervisor before relocation. No classifier is rerun.
    """
    images, snapshot = observed.get('loaded_images'), observed.get('loaded_image_snapshot')
    require(isinstance(images, list) and 1 <= len(images) <= 8192
            and all(recorded_path(name) for name in images) and len(set(images)) == len(images), 'Invalid recorded image names')
    exact_fields(snapshot, {'schema', 'method', 'count', 'stable', 'records'}, 'Malformed recorded dyld snapshot')
    require(type(snapshot['schema']) is int and snapshot['schema'] == 1
            and snapshot['method'] == 'public-dyld-name-header-cache-v1'
            and type(snapshot['count']) is int and snapshot['count'] == len(images)
            and snapshot['stable'] is True, 'Invalid or unstable recorded dyld snapshot')
    records = snapshot['records']
    require(isinstance(records, list) and len(records) == len(images)
            and isinstance(classifications, list) and len(classifications) == len(images), 'Classification/witness count mismatch')
    addresses, measured, caches = set(), {}, set()
    for index, (raw, record, classification) in enumerate(zip(images, records, classifications)):
        exact_fields(record, {'index', 'raw', 'header_address', 'magic', 'cpu_type', 'file_type', 'flags',
                              'shared_cache_contains_path'}, 'Malformed recorded dyld header')
        require(type(record['index']) is int and record['index'] == index and record['raw'] == raw,
                'Recorded header index/raw mismatch')
        address = record['header_address']
        require(isinstance(address, str) and re.fullmatch('[1-9a-f][0-9a-f]{0,15}', address) is not None
                and address not in addresses, 'Invalid or duplicate recorded header address')
        addresses.add(address)
        for key in ('magic', 'cpu_type', 'file_type', 'flags'):
            require(type(record[key]) is int and 0 <= record[key] <= 0xffffffff, 'Recorded header must use exact uint32 fields')
        require(record['magic'] == 0xFEEDFACF and record['cpu_type'] == 0x0100000C, 'Unexpected recorded Mach-O architecture')
        require(type(record['shared_cache_contains_path']) is bool, 'Recorded cache query must be exact Boolean')
        require(isinstance(classification, dict), 'Missing recorded classification')
        kind = classification.get('kind')
        fields = {'raw', 'kind', 'witness_index'} | (set() if kind == 'os-shared-cache' else {'resolved'})
        exact_fields(classification, fields, 'Unexpected recorded classification fields')
        require(type(classification['witness_index']) is int and classification['witness_index'] == index
                and classification['raw'] == raw, 'Classification index/raw mismatch')
        in_cache = bool(record['flags'] & 0x80000000)
        if kind == 'os-shared-cache':
            require(in_cache and record['file_type'] == 6 and record['shared_cache_contains_path'] is True
                    and recorded_system(raw), 'Unproved recorded shared-cache image')
            caches.add(raw)
        else:
            require(kind in ('os-file', 'bundle-file') and not in_cache, 'Unknown or inconsistent file classification')
            resolved = classification['resolved']
            require(recorded_path(resolved), 'Invalid recorded resolved image name')
            if kind == 'os-file':
                require(recorded_system(raw) and recorded_system(resolved), 'Recorded OS file escapes existing system roots')
            else:
                require(recorded_inside(raw, app) and recorded_inside(resolved, app), 'Recorded bundle image escapes its observation')
                relative = PurePosixPath(resolved).relative_to(PurePosixPath(app)).as_posix()
                require(relative in inventory, 'Recorded bundle image absent from Mach-O inventory')
                # These receipts carry no independent alias-to-inventory map.
                # Require the same inventoried raw and resolved name rather than
                # guessing a historical symlink/case-fold relationship.
                raw_relative = PurePosixPath(raw).relative_to(PurePosixPath(app)).as_posix()
                require(raw_relative == relative, 'Recorded raw image lacks exact inventory identity')
                require(resolved not in measured, 'Duplicate recorded bundle image identity')
                measured[resolved] = inventory[relative]
        if raw == str(executable):
            require(kind == 'bundle-file' and classification['resolved'] == str(executable)
                    and record['file_type'] == 2, 'Actual process image is not the recorded executable')
    require(str(executable) in images and str(executable) in measured, 'Actual GUI/child executable absent from its own image witness')
    system = observed.get('paths', {}).get('system', {})
    for key, expected in (('run-file', str(executable)), ('exec-file', str(PurePosixPath(app) / 'Contents/Resources/runtime/bin/racket'))):
        record = system.get(key)
        exact_fields(record, {'absolute', 'exists', 'raw', 'resolved'}, 'Missing executable path record')
        require(record['exists'] is True and record['resolved'] == expected and record['absolute'] == expected
                and record['raw'] == expected, 'Executable path record belongs to another process/location')
    return measured, caches


def recorded_closure(rows, measured, caches, executable):
    require(isinstance(rows, list), 'Missing recorded active closure')
    expected = [(image, dep) for image in sorted(measured) for dep in measured[image]['dependencies']]
    require(len(rows) == len(expected), 'Recorded closure differs from inventory dependency count')
    def expand(value, image):
        if value.startswith('@loader_path/'):
            value = str(PurePosixPath(image).parent / value[len('@loader_path/'):])
        elif value.startswith('@executable_path/'):
            value = str(PurePosixPath(executable).parent / value[len('@executable_path/'):])
        else:
            require(value.startswith('/'), 'Unsupported recorded loader token')
        return posixpath.normpath(value)
    for row, (image, dependency) in zip(rows, expected):
        require(isinstance(row, dict) and row.get('image') == image and row.get('dependency') == dependency,
                'Recorded closure image/dependency identity mismatch')
        if 'system' in row:
            exact_fields(row, {'image', 'dependency', 'system'}, 'Unexpected system closure fields')
            require(row['system'] is True and (dependency in caches or recorded_system(dependency)), 'Unproved recorded system dependency')
        else:
            exact_fields(row, {'image', 'dependency', 'resolved_candidates'}, 'Unexpected bundle closure fields')
            candidates = row['resolved_candidates']
            require(isinstance(candidates, list) and candidates and all(recorded_path(v) for v in candidates)
                    and candidates == sorted(set(candidates)), 'Invalid recorded closure candidates')
            if dependency.startswith('@rpath/'):
                bases = [(v, image) for v in measured[image]['rpaths']] + [(v, str(executable)) for v in measured[str(executable)]['rpaths']]
                lexical = [posixpath.normpath(expand(v, owner) + '/' + dependency[len('@rpath/'):]) for v, owner in bases]
            else:
                lexical = [expand(dependency, image)]
            known = sorted({candidate for candidate in lexical if candidate in measured or candidate in caches or recorded_system(candidate)})
            require(candidates == known, 'Recorded dependency candidates differ from complete bound candidate set')


def validate_summary_recorded(value, original_app, relocated_app, work, baseline, build, reports, post_witnesses):
    """Pure data validation of the frozen supervisor's two launch-time receipts."""
    require(all(recorded_path(str(p)) for p in (original_app, relocated_app, work)), 'Noncanonical recorded observation roots')
    require(str(original_app) != str(relocated_app), 'Observation locations must differ')
    exact_fields(value, {'schema', 'status', 'observations', 'original_runtime_present', 'recorded_original_runtime_absent',
                         'clean_destination_tested', 'initially_unset_handler_tested', 'full_distribution_acceptance',
                         'unresolved_static_loader_context'}, 'Unexpected native summary fields')
    require(isinstance(reports, list) and len(reports) == 2 and isinstance(post_witnesses, list)
            and len(post_witnesses) == 2, 'Exactly two independent report/post-witness documents required')
    inventory = recorded_macho(build, original_app, baseline)
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
        exact_fields(row, {'profile', 'verdict', 'report', 'active_non_system_dylib_closure', 'bundle_inventory_digest'},
                     'Unexpected native observation fields')
        verdict = row['verdict']
        exact_fields(verdict, {'status', 'bundle', 'profile', 'loaded_image_classifications'}, 'Unexpected native verdict fields')
        require(row['profile'] == str(profile) and verdict['status'] == 'path-and-identity-observation-validated'
                and verdict['bundle'] == str(app) and verdict['profile'] == str(profile), 'Native observation location mismatch')
        classifications = verdict['loaded_image_classifications']
        exact_fields(classifications, {'gui', 'child'}, 'Exact GUI/child classifications required')
        require(recorded_sha(row.get('bundle_inventory_digest')),
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
        require(identity.get('process_image_path') == str(app / 'Contents/MacOS/ProbeNative')
                and identity.get('main_bundle_path') == str(app) and identity.get('running_bundle_path') == str(app)
                and identity.get('main_bundle_identifier') == 'org.openracket.relative-path-probe'
                and identity.get('running_bundle_identifier') == 'org.openracket.relative-path-probe'
                and identity.get('same_running_application') is True, 'Native outer application identity mismatch')
        require(child.get('status') == 'observed' and type(child.get('schema')) is int and child['schema'] == 1
                and (child.get('version'), child.get('gc')) == ('9.3', 'cs'), 'Console child observation missing')
        closure = row.get('active_non_system_dylib_closure')
        require(isinstance(closure, dict) and set(closure) == {'gui', 'child'}
                and all(isinstance(v, list) for v in closure.values()), 'Active dylib closure missing')
        for arm, observed, executable in (('gui', report, app / 'Contents/MacOS/ProbeNative'),
                                           ('child', child, app / 'Contents/Resources/runtime/bin/racket')):
            measured, caches = recorded_images(observed, classifications[arm], app, executable, inventory)
            recorded_closure(closure[arm], measured, caches, executable)
        require(same_json(reports[index], report), 'Raw native result differs from summary')
        post = post_witnesses[index]
        exact_fields(post, {'schema', 'bundle_unchanged', 'bundle_before_digest', 'bundle_after_digest',
                            'handler_before', 'handler_after', 'owned_process_group_cleanup_certain'},
                     'Unexpected post-launch witness fields')
        require(type(post.get('schema')) is int and post['schema'] == 1
                and post.get('bundle_unchanged') is True and post.get('owned_process_group_cleanup_certain') is True
                and same_json(post.get('handler_before'), baseline) and same_json(post.get('handler_after'), baseline)
                and post.get('bundle_before_digest') == post.get('bundle_after_digest') == row['bundle_inventory_digest'],
                'Native post-launch immutability/cleanup/default witness failed')
    require(observations[0]['bundle_inventory_digest'] == observations[1]['bundle_inventory_digest'],
            'Bundle inventory changed across relocation')


def validate_summary(value, original_app, relocated_app, work, baseline):
    # Read only independent receipt documents. Never resolve/stat historical
    # app/image paths: the first bundle has intentionally moved by this point.
    build = json.loads((work / 'build.json').read_text())
    reports, posts = [], []
    for index in range(2):
        profile = work / ('run-profile-%d' % index)
        reports.append(json.loads((profile / 'result.json').read_text()))
        posts.append(json.loads((profile / 'post-launch-witness.json').read_text()))
    validate_summary_recorded(value, original_app, relocated_app, work, baseline, build, reports, posts)


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
