#!/usr/bin/env python3
"""Source-only fresh composition. No install, subprocess, network or native run."""
import argparse, hashlib, json, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'reference/native-light-tool-gates'
ACCEPTED=REF/'reference/accepted-0520-CONTENTS-SHA256.json'
ACCEPTED_SHA='2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552'
OVERLAY=REF/'FROZEN-NATIVE-ALLOWLIST.json'
OVERLAY_SHA='85185f6682f917385ce61809ecf94c26885344f6d8b0c091a31f5239f3080d98'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def pinned(path,expected):
    raw=path.read_bytes()
    if digest(raw)!=expected:raise ValueError('Pinned manifest differs')
    return json.loads(raw)
def members(root):
    # Disallow symlinks in the input tree, while allowing a symlinked ancestor
    # (e.g. genuine macOS /var -> /private/var TMPDIR aliases).
    out={}
    for path in root.rglob('*'):
        if path.is_symlink():raise ValueError('Input member is a symlink: '+path.relative_to(root).as_posix())
        if path.is_file():out[path.relative_to(root).as_posix()]=digest(path.read_bytes())
    return out

def compose(source, output, arm):
    if arm not in ('original','patched'):raise ValueError('Explicit arm required')
    accepted=pinned(ACCEPTED,ACCEPTED_SHA)
    overlay=pinned(OVERLAY,OVERLAY_SHA)['files']
    if len(accepted)!=155 or len(overlay)!=16:raise ValueError('Exact accepted155 and frozen16 required')
    source=Path(source).resolve(strict=True)
    output=Path(output)
    resolved=output.resolve(strict=False)
    if output.exists() or output.is_symlink():raise ValueError('Output must be absent')
    if resolved==source or source in resolved.parents:raise ValueError('Output may not be inside input')
    actual=members(source)
    # Only manifest members are copied. Extra build evidence stays in input;
    # every accepted source member must exist with the exact frozen bytes.
    for name,pin in accepted.items():
        if actual.get(name)!=pin:raise ValueError('Accepted source missing or changed: '+name)
    for name,pin in overlay.items():
        if digest((REF/name).read_bytes())!=pin:raise ValueError('Frozen native overlay changed: '+name)
    production=(ROOT/'production/tool/info.rkt').read_bytes()
    original=(REF/'reference/production/tool/info.rkt').read_bytes()
    old=b'(framework:line-numbers-current-line-number-foreground #(36 94 219))'
    new=b'(framework:line-numbers-current-line-number-foreground #(35 91 215))'
    if original.count(old)!=1 or production!=original.replace(old,new):raise ValueError('Production delta is not one exact entry')
    additions={p.relative_to(ROOT/'native').as_posix():p for p in (ROOT/'native').rglob('*') if p.is_file()}
    # Fail on case-folded collisions on every filesystem; do not infer case
    # sensitivity from the platform or try to manufacture case-distinct files.
    names=list(set(accepted)|set(overlay)|set(additions))
    if len({n.casefold() for n in names})!=len(names):raise ValueError('Case-folded path collision')
    resolved.mkdir(parents=True)
    for name in accepted:
        destination=resolved/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,destination)
    if arm=='patched':(resolved/'tool/info.rkt').write_bytes(production)
    for name in overlay:
        destination=resolved/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(REF/name,destination)
    for name,path in additions.items():
        destination=resolved/name;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination)
    result={'schema_version':1,'arm':arm,'accepted_manifest_sha256':ACCEPTED_SHA,
      'accepted_input_members':155,'native_overlay_manifest_sha256':OVERLAY_SHA,
      'native_overlay_members':16,'product_changes':([] if arm=='original' else ['tool/info.rkt']),
      'new_test_members':sorted(additions),'native_execution':'not run', 'files':members(resolved)}
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--arm',choices=['original','patched'],required=True)
    p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    result=compose(a.source,a.output,a.arm)
    a.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print('Verified accepted155, applied explicit palette arm, frozen16 native overlay and focused additions')
if __name__=='__main__':main()
