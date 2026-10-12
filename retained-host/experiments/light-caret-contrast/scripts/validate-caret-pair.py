#!/usr/bin/env python3
"""Require both completed native arms, using read-only result validation."""
import sys
sys.dont_write_bytecode=True
import argparse, importlib.util, json, re
from pathlib import Path
spec=importlib.util.spec_from_file_location('caret',Path(__file__).with_name('validate-caret-result.py'))
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
def validate_pair(original,patched):
    receipts=[];results=[]
    for arm,folder in [('original',Path(original)),('patched',Path(patched))]:
        def load(name):return json.loads((folder/name).read_text())
        raw=(folder/'composition.json').read_bytes();composition=json.loads(raw);sha=v.digest(raw)
        v.validate_composition(composition,arm);v.validate_build(load('build.json'),sha)
        v.validate_preflights(load('preflights.json'))
        s=load('supervisor.json');report=(folder/'ready.json').read_bytes()
        v.validate_supervision(s,report,(folder/'capture.png').read_bytes(),sha,arm)
        ratio=v.validate_result(arm,json.loads(report),(folder/'stdout.txt').read_text(),(folder/'stderr.txt').read_text(),s)
        v.require(isinstance(s.get('profile_id'),str) and re.fullmatch('[A-Za-z0-9_-]{1,100}',s['profile_id']),'Non-path disposable profile identifier required')
        v.require(isinstance(s.get('launch_id'),str) and re.fullmatch('[A-Za-z0-9_-]{1,100}',s['launch_id']),'Distinct supervisor launch identifier required')
        v.require(isinstance(s.get('process_id'),int) and not isinstance(s['process_id'],bool) and s['process_id']>0,'Native process identifier required')
        v.require(isinstance(s.get('official_runtime_sha256'),str) and re.fullmatch('[0-9a-f]{64}',s['official_runtime_sha256']),'Official runtime content digest required')
        receipts.append(s);results.append({'arm':arm,'contrast_ratio':ratio})
    v.require(receipts[0]['profile_id']!=receipts[1]['profile_id'],'Arms must use distinct fresh profiles')
    v.require(receipts[0]['launch_id']!=receipts[1]['launch_id'],'Duplicated launch receipt')
    v.require((receipts[0]['process_id'],receipts[0]['started_monotonic'])!=(receipts[1]['process_id'],receipts[1]['started_monotonic']),'Arms must have distinct recorded process-start identities')
    v.require(receipts[0]['official_runtime_sha256']==receipts[1]['official_runtime_sha256'],'Same pinned official runtime required')
    return {'status':'accepted','matrix':results,'scope':'intended current-line number colors and actual collapsed-caret captures','full_accessibility_claim':False,'screenshot_pixels_contrast_measured':False}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--original',type=Path,required=True);p.add_argument('--patched',type=Path,required=True);a=p.parse_args()
    print(json.dumps(validate_pair(a.original,a.patched)))
if __name__=='__main__':main()
