#!/usr/bin/env python3
"""Read-only evidence gate. It never runs Racket or creates native evidence."""
import sys
sys.dont_write_bytecode=True
import argparse, hashlib, importlib.util, json, math, struct, zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'reference/native-light-tool-gates'
spec=importlib.util.spec_from_file_location('inherited_light_verifier',REF/'scripts/validate-light-tool-result.py')
inherited=importlib.util.module_from_spec(spec);spec.loader.exec_module(inherited)
EXPECTED=json.loads((ROOT/'native/tests/native-light-caret-expected.json').read_text())
DYNAMIC={'visible_first_line','visible_last_line','rendered_line','line_top','line_bottom',
         'view_left','view_top','view_width','view_height','contrast_ratio'}
PREFLIGHTS=inherited.PREFLIGHTS+[
 ('native-light-caret-standalone.rkt',[], 'OPENRACKET_CARET_OK original-patched-typed-state-color-viewport-refusals',None,None),
 ('native-light-caret-standalone.rkt',['--inject-wrong-state'],
  'OPENRACKET_CARET_FAILURE control=wrong-state exception=exn:test:check check=check-equal?',
  'OPENRACKET_CARET_INJECTING_FAILURE wrong-state','OPENRACKET_CARET_OK'),
 ('native-light-caret-standalone.rkt',['--inject-wrong-color'],
  'OPENRACKET_CARET_FAILURE control=wrong-color exception=exn:test:check check=check-equal?',
  'OPENRACKET_CARET_INJECTING_FAILURE wrong-color','OPENRACKET_CARET_OK')]
require=inherited.require
exact=inherited.exact

def digest(raw):return hashlib.sha256(raw).hexdigest()
def luminance(rgb):
    def linear(n):
        c=n/255.0
        return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
    return sum(w*linear(n) for w,n in zip((0.2126,0.7152,0.0722),rgb))
def contrast(fg,bg):
    a,b=sorted((luminance(fg),luminance(bg)))
    return (b+.05)/(a+.05)
def finite(v):
    if type(v) not in (int,float):return False
    try:return math.isfinite(v)
    except (OverflowError,TypeError,ValueError):return False
def validate_state(state,arm):
    require(arm in EXPECTED,'Explicit original/patched arm required')
    expected=EXPECTED[arm]
    require(type(state) is dict and state.keys()==expected.keys()|DYNAMIC,'Exact complete caret evidence required')
    for k,v in expected.items():require(exact(state[k],v),'Actual caret mismatch: '+k)
    for k in ('visible_first_line','visible_last_line','rendered_line'):
        require(type(state[k]) is int and state[k]>=0,'Nonnegative exact line required: '+k)
    for k in DYNAMIC-{'visible_first_line','visible_last_line','rendered_line'}:
        require(finite(state[k]),'Finite coordinate or contrast required: '+k)
    require(state['visible_first_line']<=state['rendered_line']<=state['visible_last_line'],'Current line outside viewport')
    require(state['line_top']<state['line_bottom'],'Empty line geometry')
    require(state['view_width']>0 and state['view_height']>0,'Nonempty viewport required')
    require(state['view_top']<=state['line_top']<state['line_bottom']<=state['view_top']+state['view_height'],'Line is not fully visible')
    ratio=contrast(state['gutter_foreground'],state['gutter_background'])
    require(abs(state['contrast_ratio']-ratio)<=1e-12,'Contrast must be independently reproducible')
    if arm=='patched':require(ratio>=4.5,'Unrounded patched contrast below 4.5')
    return ratio

def validate_preflights(records):
    # Reuse the original strict routine and preserve all nine original controls.
    original=inherited.PREFLIGHTS
    try:
        inherited.PREFLIGHTS=PREFLIGHTS
        inherited.validate_preflights(records)
    finally:inherited.PREFLIGHTS=original

def expected_composition(arm):
    files=json.loads((REF/'reference/accepted-0520-CONTENTS-SHA256.json').read_text())
    if arm=='patched':files['tool/info.rkt']=digest((ROOT/'production/tool/info.rkt').read_bytes())
    files.update(json.loads((REF/'FROZEN-NATIVE-ALLOWLIST.json').read_text())['files'])
    files.update({p.relative_to(ROOT/'native').as_posix():digest(p.read_bytes())
                  for p in (ROOT/'native').rglob('*') if p.is_file()})
    return files

def validate_composition(receipt,arm):
    require(receipt.get('arm')==arm and receipt.get('accepted_input_members')==155,'Accepted155 composition required')
    require(receipt.get('accepted_manifest_sha256')=='2569c1bacdfb70ddc3042908b19d9e898fcebd274418668085bfe51f3a739552','Exact accepted input identity required')
    require(receipt.get('native_overlay_manifest_sha256')=='85185f6682f917385ce61809ecf94c26885344f6d8b0c091a31f5239f3080d98','Exact frozen native overlay identity required')
    require(receipt.get('product_changes')==([] if arm=='original' else ['tool/info.rkt']),'Only requested product delta allowed')
    require(exact(receipt.get('files'),expected_composition(arm)),'Complete composed source differs')

def required_racket_modules():
    overlay=json.loads((REF/'FROZEN-NATIVE-ALLOWLIST.json').read_text())['files']
    modules={n for n in overlay if n.endswith('.rkt')}
    modules.update(p.relative_to(ROOT/'native').as_posix() for p in (ROOT/'native').rglob('*.rkt'))
    modules.update('tests/'+n for n in ('independent-native-workflows.rkt','independent-native-appearance-workflows.rkt','independent-native-stop-returning.rkt'))
    return sorted(modules)

def validate_build(records,composition_sha):
    require(type(records) is list and len(records)==2,'Both native reader and compiler receipts required')
    for stage in ('reader','compile'):
        matches=[r for r in records if r.get('stage')==stage]
        require(len(matches)==1,'One exact '+stage+' receipt required')
        r=matches[0]
        require(type(r.get('exit_code')) is int and r['exit_code']==0 and r.get('timed_out') is False,'Failed or missing '+stage)
        require(type(r.get('timeout_seconds')) is int and r['timeout_seconds']==(30 if stage=='reader' else 180),'Unchanged reader/compiler supervisor deadline required')
        require(r.get('composition_sha256')==composition_sha and r.get('modules')==required_racket_modules(),'Reader/compiler did not cover exact composed native modules/dependencies')

def png_size(raw):
    require(raw.startswith(b'\x89PNG\r\n\x1a\n'),'Native capture must be PNG')
    offset=8;chunks=[]
    while offset<len(raw):
        require(offset+12<=len(raw),'Truncated PNG')
        length=struct.unpack('>I',raw[offset:offset+4])[0]
        tag=raw[offset+4:offset+8];end=offset+12+length
        require(end<=len(raw),'Truncated PNG chunk')
        payload=raw[offset+8:end-4];crc=struct.unpack('>I',raw[end-4:end])[0]
        require(zlib.crc32(tag+payload)&0xffffffff==crc,'PNG CRC mismatch')
        chunks.append((tag,payload));offset=end
    require(chunks and chunks[0][0]==b'IHDR' and len(chunks[0][1])==13 and chunks[-1]==(b'IEND',b''),'Complete PNG required')
    width,height=struct.unpack('>II',chunks[0][1][:8])
    require(width>0 and height>0 and any(t==b'IDAT' and p for t,p in chunks),'Nonempty capture required')
    return width,height

def validate_supervision(s,ready_bytes,png_bytes,composition_sha,arm):
    require(s.get('arm')==arm and s.get('composition_sha256')==composition_sha,'Supervisor source/arm mismatch')
    require(type(s.get('timeout_seconds')) is int and s['timeout_seconds']==60,'Unchanged outer60 deadline required')
    require(s.get('timed_out') is False and type(s.get('exit_code')) is int and s['exit_code']==0,'Native process must finish successfully')
    require(s.get('process_group_alive_after_cleanup') is False,'No surviving native process group')
    keys=['started_monotonic','ready_monotonic','capture_completed_monotonic','ack_monotonic','exited_monotonic','deadline_monotonic']
    require(all(finite(s.get(k)) for k in keys),'Complete finite monotonic supervision timestamps required')
    require(abs(s['deadline_monotonic']-s['started_monotonic']-60)<=1e-6,'Deadline must be fixed at original process start')
    require(all(s[a]<=s[b] for a,b in zip(keys,keys[1:])),'Ready/capture/ack/exit order or outer deadline violated')
    require(s['ack_monotonic']-s['ready_monotonic']<20,'Capture and acknowledgment must finish within unchanged20-second wait')
    require(s.get('capture_tool')=='screencapture' and s.get('capture_after_ready') is True,'Actual macOS screen capture after READY required')
    require(s.get('ready_sha256')==digest(ready_bytes) and s.get('png_sha256')==digest(png_bytes),'Capture and READY bytes are not bound to supervisor receipt')
    require(s.get('fresh_process') is True and s.get('fresh_profile') is True and s.get('initial_ready_absent') is True and s.get('initial_ack_absent') is True,'Fresh isolated process/profile/coordination required')
    png_size(png_bytes)

def validate_result(arm,report,stdout,stderr,supervisor):
    inherited.validate_result('modern-light','macro-stepper',report,stdout,stderr,supervisor['exit_code'],supervisor['timed_out'])
    state=report.get('caret_state');ratio=validate_state(state,arm)
    lines=stdout.splitlines()
    states=[json.loads(line.split(' ',1)[1]) for line in lines if line.startswith('OPENRACKET_NATIVE_CARET_STATE ')]
    require(len(states)==1 and exact(states[0],state),'Unique actual caret snapshot must equal READY report')
    caret=next(i for i,line in enumerate(lines) if line.startswith('OPENRACKET_NATIVE_CARET_STATE '))
    after=max(i for i,line in enumerate(lines) if line.startswith('OPENRACKET_NATIVE_LIGHT_STATE '))
    result=next(i for i,line in enumerate(lines) if line.startswith('OPENRACKET_NATIVE_RESULT '))
    require(after<caret<result,'Caret capture must follow unchanged tool workflow and light observations')
    require('OPENRACKET_CARET_FAILURE' not in stdout+stderr and 'OPENRACKET_CARET_INJECTING_FAILURE' not in stdout+stderr,'Headless injection is never native success')
    return ratio

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arm',choices=['original','patched'],required=True)
    for name in ('report','stdout','stderr','supervisor','composition','preflights','build','png'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();load=lambda path:json.loads(path.read_text())
    ready=a.report.read_bytes();composition=a.composition.read_bytes();sha=digest(composition)
    validate_composition(json.loads(composition),a.arm)
    validate_preflights(load(a.preflights));validate_build(load(a.build),sha)
    s=load(a.supervisor);validate_supervision(s,ready,a.png.read_bytes(),sha,a.arm)
    ratio=validate_result(a.arm,json.loads(ready),a.stdout.read_text(),a.stderr.read_text(),s)
    print(json.dumps({'status':'accepted','arm':a.arm,'contrast_ratio':ratio,'native_scope':'collapsed-caret Macro Stepper capture','screenshot_pixels_contrast_measured':False,'full_accessibility_claim':False}))
if __name__=='__main__':main()
