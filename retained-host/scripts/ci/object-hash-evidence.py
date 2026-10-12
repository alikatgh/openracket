"""Strict process, native semantics and three-host diagnostic acceptance gates."""
import hashlib,json,pathlib
EDGES=[[6,17,19,25],[6,17,35,35],[6,17,36,37],[6,17,40,40],[6,17,44,44],[6,17,50,50],[27,31,45,49],[32,33,38,39]]

def need(ok,why):
    if not ok:raise ValueError(why)

def decode(raw):
    def pairs(entries):
        d={}
        for k,v in entries:
            need(k not in d,'Duplicate JSON key');d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))

def record(raw,marker):
    prefix=marker.encode()+b' ';lines=[line[len(prefix):] for line in raw.splitlines() if line.startswith(prefix)]
    need(len(lines)==1 and raw.count(marker.encode())==1,'One exact '+marker+' record required')
    need(len(lines[0])<=128*1024,'Bounded native record');return decode(lines[0])

def process(row,bound):
    need(row.get('native_executed') is True and type(row.get('returncode')) is int and row['returncode']==0,'Successful actual process required')
    need(row.get('passed') is True and row.get('cleanup_verified') is True and row.get('timed_out') is False and row.get('output_bound_exceeded') is False,'Complete bounded process and cleanup required')
    need(type(row.get('timeout_seconds')) is int and row['timeout_seconds']==bound,'Exact process bound')

def semantics(raw,row,scenario,flag,observation):
    process(row,30);r=record(raw,'OPENRACKET_OBJECT_HASH_NATIVE_SEMANTICS')
    need(set(r)=={'scenario','status','state'} and r['scenario']==scenario and r['status']=='passed','Exact scenario completion')
    need(r['state']['enabled'] is (flag=='1'),'Actual semantics activation')
    observation.validate(r['state'])
    need(row['environment'].get('OPENRACKET_OBJECT_HASH_PROBE')==flag,'Supervisor scenario flag')
    return {'scenario':scenario,'passed':True,'raw_sha256':hashlib.sha256(raw).hexdigest(),'source_state':r['state']}

def host(raw,ready_raw,png,row,mode,arm,observation,png_record):
    process(row,60)
    need(row.get('capture_attempted') is True and row.get('capture_done_written') is True and type(row.get('capture_returncode')) is int and row['capture_returncode']==0,'READY/capture/ACK required')
    need(row.get('screenshot')==png_record(png),'Original screenshot proof')
    need(raw.splitlines().count(b'OPENRACKET_NATIVE_READY')==1 and raw.count(b'OPENRACKET_NATIVE_READY')==1,'Exact successful READY')
    need(b'OPENRACKET_NATIVE_FAILURE' not in raw,'No native host failure')
    need(raw.splitlines().count(b'OPENRACKET_FOLLOWON_CASE check-syntax completed')==1,'Original workflow completion')
    r=record(raw,'OPENRACKET_NATIVE_RESULT');ready=decode(ready_raw);graph=record(raw,'OPENRACKET_BINDING_GRAPH')
    need(graph==EDGES and all(type(n) is int for e in graph for n in e),'Exact typed eight-edge graph including zero spans')
    need(r==ready and r.get('status')=='passed' and r.get('genuine_host') is True and r.get('repeated_real_run') is True and r.get('ui')=='stock' and r.get('racket')=='9.3' and r.get('follow_on_case')=='check-syntax','Completed original genuine host')
    need(type(r.get('checks')) is int and r['checks']>0 and r.get('complete_stock_parity') is False and r.get('physical_input_to_photon_measured') is False and r.get('native_appearance_lifecycle') is None,'Unchanged bounded scope')
    need(r.get('follow_on_result',{}).get('case')=='check-syntax' and r['follow_on_result'].get('status')=='passed','Original Check Syntax assertions')
    expected=None if mode=='stock' else ('0' if mode=='off' else '1')
    need(row['environment'].get('OPENRACKET_OBJECT_HASH_PROBE')==expected,'Exact host flag')
    if mode=='stock':
        need(b'OPENRACKET_OBJECT_HASH_SOURCE' not in raw and b'OPENRACKET_OBJECT_HASH_OBSERVATION' not in raw,'Stock must run unmodified vendor host')
        assessment={'conclusion':'pristine-stock-control','candidate_speed_or_byte_saving_claim':False}
    else:
        source=record(raw,'OPENRACKET_OBJECT_HASH_SOURCE');state=record(raw,'OPENRACKET_OBJECT_HASH_OBSERVATION')
        need(source['runtime_root']==arm['runtime'] and source['executable']==str(pathlib.Path(arm['runtime'])/'bin/racket'),'Actual clone/executable identity')
        need(source['flag']==expected and source['enabled'] is (mode=='on'),'Actual host activation')
        assessment=observation.validate_run(source,state,r,graph)
    return {'mode':mode,'passed':True,'graph':graph,'assessment':assessment,'raw_sha256':hashlib.sha256(raw).hexdigest(),'ready_raw_sha256':hashlib.sha256(ready_raw).hexdigest(),'screenshot':row['screenshot']}

def matrix(cases,hosts):
    need(len(cases)==16 and len({r['scenario'] for r in cases})==16 and all(r['passed'] for r in cases),'All 16 native scenarios required')
    need(set(hosts)=={'stock','off','on'} and all(r['passed'] and r['graph']==EDGES for r in hosts.values()),'All three complete genuine host controls required')
    return {'schema':'object-hash-native-matrix/v1','passed':True,'semantics':cases,'hosts':hosts,'interpretation':hosts['on']['assessment'],'optimization_implemented':False,'timing_experiment':False,'candidate_adopted':False}

def load_audit(raw,arm,args):
    prefix=b'OBJECT_HASH_LOAD_AUDIT ';events=[]
    for line in raw.splitlines():
        if line.startswith(prefix):
            need(len(line)<=4*1024*1024,'Bounded load audit record');events.append(decode(line[len(prefix):]))
    need(events,'Actual runtime load audit absent')
    for event in events:
        need(type(event) is dict and set(event)=={'schema','event','data'} and type(event['data']) is dict,'Typed load audit event fields')
        need(event.get('event') in ('installed','modules','external_files','primitives','primitive','evaluated-module','rejected'),'Known audit event required')
        need(event.get('schema')=='object-hash-load-audit/v1','Load audit schema')
        need(event.get('event')!='rejected','Native load audit rejection is fatal')
    installed=[x['data'] for x in events if x['event']=='installed']
    need(len(installed)==1,'One installed audit marker required');scope=installed[0]
    need(scope.get('compiled_root')==arm['compiled'] and scope.get('scope')=='initial-place-and-inheriting-threads' and scope.get('child_place_dynamic_audit_complete') is False,'Exact load audit root/scope')
    need(scope.get('live_registry_observed') is False and scope.get('arbitrary_dynamic_graph_proven') is False,'Explicit native unobserved scope flags required')
    need(scope.get('prebuild_receipt_sha256')==arm.get('receipt_sha256') and scope.get('prebuild_receipt')==str(pathlib.Path(arm['work'])/'prebuild-receipts.json'),'Pinned prebuild receipt handoff required')
    need(type(scope.get('prebuild_module_count')) is int and scope['prebuild_module_count']==len(arm.get('receipt_modules',{})) and scope['prebuild_module_count']>0,'Exact prebuild module count')
    need(scope.get('source_roots')==[arm['runtime'],arm['package'],str(pathlib.Path(arm['work'])/'ci')],'Exact audit source roots')
    need(scope.get('arguments_unchanged')==args,'Preloaded audit changed original target arguments')
    rows=[x['data'] for x in events if x['event']=='modules'];need(rows,'Actual source-backed helper/load records required')
    roots=[arm['runtime'],arm['package'],str(pathlib.Path(arm['work'])/'ci')];seen=set()
    def path(value,parents):
        need(type(value) is str and value.startswith('/') and str(pathlib.PurePosixPath(value))==value and '..' not in pathlib.PurePosixPath(value).parts,'Canonical audit file path required')
        need(any(value.startswith(p+'/') for p in parents),'Audit file outside exact arm roots')
        return value
    for row in rows:
        need({'nominal_path','source','bytecode','dependency'}<=set(row),'Source/zo/dep audit row required')
        nominal=path(row['nominal_path'],roots)
        need(row.get('prebuild_receipt_sha256')==arm.get('receipt_sha256'),'Actual module receipt reference mismatch')
        expected=arm.get('receipt_modules',{}).get(nominal);need(expected is not None and all(row.get(key)==expected[key] for key in ('nominal_path','source','bytecode','dependency')),'Actual module row differs from accepted prebuild receipt')
        need(nominal not in seen,'Duplicate module audit record');seen.add(nominal)
        for key,parents in (('source',roots),('bytecode',[arm['compiled']]),('dependency',[arm['compiled']])):
            file=row[key];need(type(file) is dict and set(file)=={'path','size','sha256'},'Exact audit file receipt')
            path(file['path'],parents);need(type(file['size']) is int and file['size']>=0,'Typed audit file size')
            pin=file['sha256'];need(type(pin) is str and len(pin)==64 and all(c in '0123456789abcdef' for c in pin),'Audit file digest')
        need(row['bytecode']['path'].endswith('.zo') and row['dependency']['path']==row['bytecode']['path'][:-3]+'.dep','Audit compiled pair')
    return {'scope':'initial-place-and-inheriting-threads','records':len(events),'live_registry_observed':False,'child_place_dynamic_audit_complete':False,'arbitrary_dynamic_graph_proven':False}
