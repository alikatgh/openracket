#!/usr/bin/env python3
"""Validate existing numeric graph output, without claiming a complete table."""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path, PurePosixPath
ROOT = Path(__file__).resolve().parents[1]
PINS = json.loads((ROOT/'RUNTIME-PINS.json').read_text())
HOST_SHA = '5d3fec70cb1ccae6ac91ea7ef2dc382011e7c173a2a8d34a51e6e01dad5fd448'
MODES = ('stock', 'candidate-off', 'candidate-on')
EDGES = [[6,17,19,25],[6,17,35,35],[6,17,36,37],[6,17,40,40],
         [6,17,44,44],[6,17,50,50],[27,31,45,49],[32,33,38,39]]
class Refused(ValueError):pass

def need(value, why):
    if not value:raise Refused(why)

def no_duplicates(pairs):
    result={}
    for key,value in pairs:
        need(key not in result,'duplicate JSON field: '+key)
        result[key]=value
    return result

def decode(raw):
    return json.loads(raw, object_pairs_hook=no_duplicates,
                      parse_constant=lambda value: (_ for _ in ()).throw(Refused('nonfinite JSON')))

def unique_json(text, prefix):
    lines=[line for line in text.splitlines() if line.startswith(prefix+' ')]
    need(len(lines)==1 and text.count(prefix)==1,'unique exact '+prefix+' record required')
    return decode(lines[0][len(prefix)+1:])

def canonical(value):
    need(type(value) is str and value.startswith('/') and value!='/' and
         str(PurePosixPath(value))==value and '..' not in PurePosixPath(value).parts,
         'canonical absolute path required')
    return PurePosixPath(value)

def validate_source(source, mode):
    fields={'schema','mode','version','runtime_root','executable','flag','activation',
            'state_export','source_first_load','sources','host_sha256'}
    need(type(source) is dict and set(source)==fields,'source proof fields')
    need(mode in MODES and source['mode']==mode and source['version']=='9.3' and
         source['schema']=='openracket-named-style-control-source/v1','source mode/version/schema')
    stock=mode=='stock';enabled=mode=='candidate-on'
    need(source['flag']==(None if stock else ('1' if enabled else '0')),'exact flag')
    need(source['activation']=='unexported' if stock else
         type(source['activation']) is bool and source['activation'] is enabled,'actual activation')
    need(source['state_export']==('unexported' if stock else 'present') and
         source['source_first_load'] is True,'source-first and exact diagnostic export presence')
    root=canonical(source['runtime_root']);exe=canonical(source['executable'])
    need(root in exe.parents,'actual executable outside selected runtime')
    need(source['host_sha256']==HOST_SHA,'unchanged accepted host')
    need(type(source['sources']) is dict and set(source['sources'])==set(PINS),'all runtime pins')
    for module,pin in PINS.items():
        row=source['sources'][module]
        need(type(row) is dict and set(row)=={'path','sha256'},'source record fields')
        path=canonical(row['path'])
        need(root in path.parents and str(path).endswith('/'+module+'.rkt'),'actual resolved module path')
        expected=pin['stock' if stock else 'candidate'] if type(pin) is dict else pin
        need(row['sha256']==expected,'runtime source pin: '+module)
    return source

def png_record(raw):
    need(type(raw) is bytes and 45 <= len(raw) <= 32*1024*1024 and
         raw[:8]==b'\x89PNG\r\n\x1a\n','real bounded PNG signature required')
    offset=8;first=True;seen_data=False;ended=False;width=height=0
    while offset<len(raw):
        need(offset+12<=len(raw),'truncated PNG chunk')
        size=struct.unpack('>I',raw[offset:offset+4])[0];kind=raw[offset+4:offset+8]
        end=offset+12+size
        need(end<=len(raw),'truncated PNG payload')
        payload=raw[offset+8:offset+8+size]
        need(zlib.crc32(kind+payload)==struct.unpack('>I',raw[end-4:end])[0],'PNG chunk CRC')
        if first:
            need(kind==b'IHDR' and size==13,'PNG must begin with IHDR')
            width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',payload)
            need(0<width<=16384 and 0<height<=16384 and width*height<=100_000_000,
                 'bounded positive PNG dimensions')
            need(color in {0,2,3,4,6} and depth in {1,2,4,8,16} and compression==filtering==0 and interlace in {0,1},
                 'PNG IHDR format')
            first=False
        else:need(kind!=b'IHDR','duplicate PNG header')
        if kind==b'IDAT':seen_data=True
        if kind==b'IEND':
            need(size==0 and end==len(raw) and seen_data,'complete PNG end and data required')
            ended=True
        offset=end
    need(ended,'PNG end missing')
    return {'format':'PNG','bytes':len(raw),'width':width,'height':height,
            'sha256':hashlib.sha256(raw).hexdigest()}

def validate(raw, ready_raw, process, mode, png_raw):
    need(type(process) is dict and type(process.get('returncode')) is int and process['returncode']==0
         and process.get('timed_out') is False and process.get('native_executed') is True,
         'actual successful bounded process required')
    need(process.get('timeout_seconds')==60 and type(process.get('timeout_seconds')) is int,
         'unchanged 60-second outer bound')
    need(process.get('capture_attempted') is True and process.get('capture_done_written') is True,
         'READY/capture handshake required')
    need(type(process.get('capture_returncode')) is int and process['capture_returncode']==0,
         'successful screenshot process required')
    screenshot=png_record(png_raw)
    need(process.get('screenshot')==screenshot and
         all(type(process['screenshot'][key]) is int for key in ('bytes','width','height')),
         'actual screenshot bytes/dimensions/hash must match capture record')
    text=raw.decode('utf-8');ready=decode(ready_raw)
    need('OPENRACKET_NATIVE_FAILURE' not in text,'native failure output')
    need(text.splitlines().count('OPENRACKET_NATIVE_READY')==1 and text.count('OPENRACKET_NATIVE_READY')==1,
         'unique successful READY marker')
    source=validate_source(unique_json(text,'OPENRACKET_NAMED_STYLE_CONTROL_SOURCE'),mode)
    need(process.get('runtime_root')==source['runtime_root'] and
         type(process.get('command')) is list and len(process['command'])==4 and
         process['command'][0]==source['executable'] and process['command'][2:]==[mode,source['runtime_root']] and
         process.get('arm')==mode and process.get('named_style_flag')==source['flag'],
         'caller mode, actual source root/executable and exact environment agree')
    graph=unique_json(text,'OPENRACKET_BINDING_GRAPH')
    need(type(graph) is list and len(graph)==8 and all(type(edge) is list and len(edge)==4
         and all(type(x) is int for x in edge) for edge in graph) and graph==EDGES,
         'exact typed eight-edge fixture output including all zero spans')
    result=unique_json(text,'OPENRACKET_NATIVE_RESULT')
    need(type(result) is dict and result==ready and result.get('status')=='passed' and
         result.get('genuine_host') is True and result.get('repeated_real_run') is True and
         result.get('ui')=='stock' and result.get('racket')=='9.3' and
         result.get('follow_on_case')=='check-syntax','unchanged genuine host result/READY')
    need(type(result.get('checks')) is int and result['checks']>0 and
         result.get('complete_stock_parity') is False and
         result.get('physical_input_to_photon_measured') is False and
         'native_appearance_lifecycle' in result and result['native_appearance_lifecycle'] is None,
         'typed positive host checks and unchanged bounded scope required')
    follow=result.get('follow_on_result')
    need(type(follow) is dict and follow.get('case')=='check-syntax' and follow.get('status')=='passed',
         'completed unchanged Check Syntax workflow')
    need(text.splitlines().count('OPENRACKET_FOLLOWON_CASE check-syntax completed')==1,'workflow completion')
    return {'source':source,'graph':graph,'raw_sha256':hashlib.sha256(raw).hexdigest(),
            'ready_sha256':hashlib.sha256(ready_raw).hexdigest()}

def compare(rows):
    need(set(rows)==set(MODES),'three independent native control arms required')
    graphs=[rows[mode]['graph'] for mode in MODES]
    need(graphs[0]==graphs[1]==graphs[2]==EDGES,'exact numeric fixture graph differs')
    return {'accepted':True,'modes':list(MODES),'edges_per_mode':8,
            'zero_span_edges_per_mode':4,'numeric_fixture_outputs_equal':True,
            'scope':'Exact existing numeric eight-edge fixture output. The unchanged workflow filters to same-editor endpoints and removes duplicates; this is not proof about filtered entries or complete table/getter semantics. Full telemetry is a separate gate.',
            'raw_sha256':{mode:rows[mode]['raw_sha256'] for mode in MODES}}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for mode in MODES:p.add_argument('--'+mode,type=Path,required=True,help='original host capture directory')
    a=vars(p.parse_args())
    try:
        rows={}
        for mode in MODES:
            root=a[mode.replace('-','_')]
            rows[mode]=validate((root/'stdout.bin').read_bytes(),(root/'ready.json').read_bytes(),
                                decode((root/'process.json').read_bytes()),mode,(root/'screenshot.png').read_bytes())
        print(json.dumps(compare(rows),indent=2));return 0
    except (OSError,ValueError,TypeError,KeyError) as e:
        print(json.dumps({'accepted':False,'error':str(e)}));return 1
if __name__=='__main__':raise SystemExit(main())
