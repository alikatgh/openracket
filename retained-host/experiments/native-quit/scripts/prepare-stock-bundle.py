#!/usr/bin/env python3
"""Test-only metadata cleanup for a newly generated official stock-control app.
Changes only this disposable plist's document-type claim. Native bytes stay exact.
"""
import argparse,hashlib,json,pathlib,plistlib

def prepare(app):
    if not app.is_absolute() or app.is_symlink():raise ValueError('Absolute nonsymlink fresh test app required')
    app=app.resolve(strict=True)
    contents=app/'Contents';macos=contents/'MacOS';p=contents/'Info.plist'
    for component in (contents,macos,p):
        if component.is_symlink():raise ValueError('Symlinked managed app component refused: '+str(component))
    if not contents.is_dir() or not macos.is_dir() or not p.is_file():raise ValueError('Expected original bundle components')
    canonical_plist=p.resolve(strict=True)
    if canonical_plist==app or not canonical_plist.is_relative_to(app):raise ValueError('Plist escapes disposable app')
    before=p.read_bytes();info=plistlib.loads(before)
    if info.get('CFBundleIdentifier')!='org.racket-lang.OpenRacketStockQuitControl':raise ValueError('Exact official-generator stock-control name required')
    if info.get('CFBundleExecutable')!='OpenRacketStockQuitControl' or info.get('CFBundlePackageType')!='APPL':raise ValueError('Original native entry required')
    if 'LSEnvironment' in info:raise ValueError('Unexpected environment metadata refused')
    native=app/'Contents/MacOS'/info['CFBundleExecutable']
    if native.is_symlink():raise ValueError('Native symlink refused')
    canonical_native=native.resolve(strict=True)
    if canonical_native==app or not canonical_native.is_relative_to(app) or not native.is_file():raise ValueError('Native entry escapes disposable app')
    original_native=native.read_bytes();expected=dict(info);expected.pop('CFBundleDocumentTypes',None)
    proof=app.parent/'stock-control-metadata.json'
    if proof.exists() or proof.is_symlink():raise ValueError('Prepared stock app cannot be rewritten')
    if 'CFBundleDocumentTypes' in info:p.write_bytes(plistlib.dumps(expected,sort_keys=False))
    actual=plistlib.loads(p.read_bytes())
    if actual!=expected or native.read_bytes()!=original_native:raise ValueError('Unexpected generated app mutation')
    result={'scope':'official-generator native app running unchanged DrRacket','app_path':str(app),'native_executable_path':str(native),'bundle_id':actual['CFBundleIdentifier'],'plist_before_sha256':hashlib.sha256(before).hexdigest(),'plist_after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'native_sha256':hashlib.sha256(original_native).hexdigest(),'native_bytes_unchanged':True,'removed_only_document_types':True,'before_metadata':info,'after_metadata':actual}
    with proof.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('app',type=pathlib.Path);a=p.parse_args();print(json.dumps(prepare(a.app)))
