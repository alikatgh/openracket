#!/usr/bin/env python3
"""Create only fresh bounded synthetic fixtures/config after native preparation.
Does not build, register, compile, launch, mutate an existing profile or use Racket.
"""
import argparse,json,pathlib,plistlib,secrets
import quit_contract as C
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--mode',choices=('stock','modern-dark'),required=True);p.add_argument('--case',choices=('clean','save','discard'),required=True);p.add_argument('--app',type=pathlib.Path,required=True);p.add_argument('--profile',type=pathlib.Path,required=True);p.add_argument('--runtime',type=pathlib.Path,required=True)
a=p.parse_args();root=a.root.resolve(strict=True);app=a.app.resolve(strict=True);profile=a.profile.resolve(strict=True);runtime=a.runtime.resolve(strict=True)
for value in (app,profile):C.need(C.inside(value,root),'Prepared case path must be within new root')
info=plistlib.loads((app/'Contents/Info.plist').read_bytes());native=info['CFBundleExecutable']
if a.mode=='modern-dark':native=json.loads((app/'Contents/Resources/build-record.json').read_text())['native_executable']
output=root/'evidence';output.mkdir();docs=root/'documents';docs.mkdir();fixture=docs/"Quit λ's 日本語.rkt"
original='#lang racket/base\n(define gate-answer 42)\n';edited=original+';; Intended unsaved edit: café 日本語 λ\n'
with fixture.open('xb') as f:f.write(original.encode())
c={'schema':1,'run_id':'quit-'+secrets.token_hex(12),'mode':a.mode,'case':a.case,'root_dir':str(root),'output_dir':str(output),'profile_path':str(profile),'app_path':str(app),'native_executable_path':str((app/'Contents/MacOS'/native).resolve(strict=True)),'bundle_id':info['CFBundleIdentifier'],'fixture_path':str(fixture),'original_text':original,'edited_text':edited,'runtime_root':str(runtime),'step_tokens':{},'memory_mib':128 if a.mode=='stock' else 256,'process_timeout_seconds':150}
c['step_tokens']={s:secrets.token_hex(24) for s in C.stages(c)};C.validate_config(c)
path=root/'case-config.json'
with path.open('x',encoding='utf-8') as f:json.dump(c,f,ensure_ascii=False,indent=2);f.write('\n')
print(path)
