"""Pure fail-closed contracts for the audit-only frozen relative-launcher probe."""
import base64
import hashlib
import json
import os
from pathlib import Path
import stat

FREEZE_PIN = '5c2967fe016ff7d7b1c5acf87de9050e4693ee9fa3f4ccb383b1ad9b6ab268a1'
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
    require(type(members) is dict and len(members) == 22, 'Exactly22 frozen members required')
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Source symlink refused')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(members) | {'MANIFEST.json'}, 'Exact23-file source inventory required')
    for name, pin in members.items():
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts and path.as_posix() == name, 'Unsafe source path')
        source = root / path
        require(source.is_file() and source.stat().st_size == pin['bytes'] and sha(source) == pin['sha256'],
                'Frozen source mismatch: ' + name)
    return members


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


def verdict(assembled, declarations, original_unchanged, handler_unchanged, transport_complete):
    complete = all(x is True for x in (assembled, original_unchanged, handler_unchanged, transport_complete))
    return {'schema': 1, 'status': ('audit-complete-launch-blocked-by-declarations' if declarations else
                                  'audit-complete-no-launch-authorized') if complete else 'audit-failed-or-incomplete',
            'audit_complete': complete, 'construction_and_audit_only': True,
            'native_app_launches': 0, 'native_app_acceptance': False,
            'declarations_block_launch': declarations, 'mandatory_no_launch': True,
            'original_runtime_unchanged': original_unchanged, 'default_handler_unchanged': handler_unchanged,
            'complete_evidence_transport': transport_complete, 'clean_destination_tested': False,
            'full_distribution_acceptance': False}


def wrap_bytes(path):
    raw = path.read_bytes()
    require(len(raw) <= 16 * 1024 * 1024, 'Evidence exceeds16MiB; fail rather than truncate')
    return {'filename': path.name, 'encoding': 'base64', 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'chunks': [base64.b64encode(raw[i:i + 8192]).decode() for i in range(0, len(raw), 8192)]}
