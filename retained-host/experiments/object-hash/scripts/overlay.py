#!/usr/bin/env python3
"""Stage/verify a source-only overlay; never replace a runtime file or execute it."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from generate import ROOT, CLASS_PIN, sha, transform, restore
RELATIVE_CLASS=Path('collects/racket/private/class-internal.rkt')
FILES={'original/class-internal.rkt','overlay/collects/racket/private/class-internal.rkt'}

def overlap(a,b): return a==b or a in b.parents or b in a.parents

def root_path(path):
    if not path.is_absolute():raise ValueError('explicit absolute root required')
    actual=path.resolve(strict=True)
    if not actual.is_dir() or actual==Path(actual.anchor):raise ValueError('invalid root')
    return actual

def child_file(root,relative):
    if relative.is_absolute() or '..' in relative.parts:raise ValueError('invalid relative source path')
    path=root
    for part in relative.parts:
        path=path/part
        if path.is_symlink():raise ValueError('symlink within source/overlay refused')
    if not path.is_file() or root not in path.resolve(strict=True).parents:raise ValueError('source outside root or not a file')
    return path

def stage(source_root,output):
    source_root=root_path(Path(source_root))
    original=child_file(source_root,RELATIVE_CLASS).read_bytes()
    instrumented=transform(original)
    output=Path(output)
    if not output.is_absolute():raise ValueError('explicit absolute output required')
    parent=root_path(output.parent)
    # A symlinked TMPDIR ancestor is accepted after canonicalization; a symlink
    # at the destination itself is never followed, including dangling symlinks.
    if output.exists() or output.is_symlink():raise ValueError('output must be new')
    output=parent/output.name
    if overlap(source_root,output) or overlap(ROOT.resolve(),output):raise ValueError('output overlaps source or package')
    output.mkdir()
    files={'original/class-internal.rkt':original,
           'overlay/collects/racket/private/class-internal.rkt':instrumented}
    for name,data in files.items():
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    manifest={'schema':'openracket-object-hash-overlay/v1','source_root':str(source_root),
              'original_sha256':CLASS_PIN,'native_execution':False,
              'files':{n:sha(b) for n,b in files.items()}}
    (output/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    verify(output)
    return manifest

def verify(output):
    output=root_path(Path(output))
    mpath=child_file(output,Path('MANIFEST.json'))
    if mpath.stat().st_size>16384:raise ValueError('oversized manifest')
    def pairs(entries):
        result={}
        for key,value in entries:
            if key in result:raise ValueError('duplicate manifest key')
            result[key]=value
        return result
    manifest=json.loads(mpath.read_text(),object_pairs_hook=pairs)
    if set(manifest)!={'schema','source_root','original_sha256','native_execution','files'}:raise ValueError('manifest shape')
    if manifest['schema']!='openracket-object-hash-overlay/v1' or manifest['native_execution'] is not False or manifest['original_sha256']!=CLASS_PIN:raise ValueError('manifest identity')
    if not isinstance(manifest['source_root'],str) or not Path(manifest['source_root']).is_absolute():raise ValueError('manifest source root')
    if not isinstance(manifest['files'],dict) or set(manifest['files'])!=FILES:raise ValueError('manifest file allowlist')
    actual=set()
    for p in output.rglob('*'):
        if p.is_symlink():raise ValueError('overlay symlink')
        if p.is_file():actual.add(str(p.relative_to(output)))
    if actual!=FILES|{'MANIFEST.json'}:raise ValueError('overlay closure')
    data={name:child_file(output,Path(name)).read_bytes() for name in FILES}
    if any(sha(data[name])!=pin for name,pin in manifest['files'].items()):raise ValueError('manifest digest mismatch')
    original=data['original/class-internal.rkt'];candidate=data['overlay/collects/racket/private/class-internal.rkt']
    if sha(original)!=CLASS_PIN or transform(original)!=candidate or restore(candidate)!=original:raise ValueError('source transform/reversal mismatch')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('stage');s.add_argument('--source-root',required=True,type=Path);s.add_argument('--output',required=True,type=Path)
    v=sub.add_parser('verify');v.add_argument('output',type=Path)
    a=p.parse_args();result=stage(a.source_root,a.output) if a.action=='stage' else verify(a.output)
    print(json.dumps(result,indent=2))
