"""Independent pure protocol validator. Never supplies app success or cleans up."""
import hashlib,json,math,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE_PINS={r['module']:r['sha256'] for r in json.loads((ROOT/'driver/source-pins.json').read_text())}
KEYS={'schema','run_id','mode','case','root_dir','output_dir','profile_path','app_path','native_executable_path','bundle_id','fixture_path','original_text','edited_text','runtime_root','step_tokens','memory_mib','process_timeout_seconds'}
TOKEN=re.compile(r'[A-Za-z0-9_-]{16,100}\Z')
ID_KEYS=('frame_id','tab_id','definitions_id','interactions_id','definitions_canvas_id','interactions_canvas_id')
def need(value,why):
    if not value:raise ValueError(why)
def digest(b):return hashlib.sha256(b).hexdigest()
def finite_real(value):
    # Avoid converting arbitrary-size integers to float; math.isfinite would
    # raise OverflowError instead of the validator's ordinary refusal.
    return (type(value) is int and -(2**53)<=value<=2**53) or (type(value) is float and math.isfinite(value))
def stages(c):
    return ['ready','quit-confirm-1','terminal-response'] if c['case']=='clean' else ['ready','dirty','quit-confirm-1','unsaved-1','cancelled','quit-confirm-2','unsaved-2','terminal-response']
def path(c,key):return pathlib.Path(c[key]).resolve(strict=True)
def inside(child,parent):return child!=parent and child.is_relative_to(parent)
def validate_config(c):
    need(isinstance(c,dict) and set(c)==KEYS,'Exact config keys required')
    need(type(c['schema']) is int and c['schema']==1,'Schema integer 1')
    need(isinstance(c['run_id'],str) and TOKEN.fullmatch(c['run_id']),'Run ID')
    need(c['mode'] in ('stock','modern-dark') and c['case'] in ('clean','save','discard'),'Known mode/case')
    need(type(c['process_timeout_seconds']) is int and c['process_timeout_seconds']==150,'Frozen 150-second deadline')
    need(type(c['memory_mib']) is int and c['memory_mib']==(128 if c['mode']=='stock' else 256),'Existing mode memory contract')
    for k in ('root_dir','output_dir','profile_path','app_path','native_executable_path','fixture_path','runtime_root'):
        v=c[k];need(isinstance(v,str) and 1<=len(v)<=4096 and not any(x in v for x in '\0\r\n') and pathlib.Path(v).is_absolute(),'Absolute path '+k)
        need(not pathlib.Path(v).is_symlink(),'Managed symlink refused '+k);path(c,k)
    for k in ('output_dir','profile_path','app_path','fixture_path'):need(inside(path(c,k),path(c,'root_dir')),k+' containment')
    need(inside(path(c,'native_executable_path'),path(c,'app_path')),'Native bundle containment')
    need(isinstance(c['bundle_id'],str) and re.fullmatch(r'[A-Za-z0-9.-]+',c['bundle_id']),'Bundle ID')
    for k in ('original_text','edited_text'):
        s=c[k];need(isinstance(s,str) and 1<=len(s)<=4096 and s.startswith('#lang racket/base\n') and s.endswith('\n') and '\0' not in s,'Bounded UTF-8 text')
    a,b=c['original_text'],c['edited_text'];need(b.startswith(a) and b[len(a):].startswith(';; '),'Only appended comment')
    need(path(c,'fixture_path').read_bytes()==a.encode(),'Exact initial fixture bytes')
    ts=c['step_tokens'];need(isinstance(ts,dict) and set(ts)==set(stages(c)),'Exact stage token keys')
    need(all(isinstance(x,str) and TOKEN.fullmatch(x) for x in ts.values()) and len(set(ts.values()))==len(ts),'Unique tokens')
    return c

def envelope(c,stage):return {'schema':1,'run_id':c['run_id'],'stage':stage,'token':c['step_tokens'][stage]}
def file_for(c,stage,kind):return path(c,'output_dir')/(c['run_id']+'.'+stage+'.'+kind+'.json')
def validate_envelope(r,c,stage):
    need(isinstance(r,dict),'Report object')
    need(type(r.get('schema')) is int,'Exact schema type')
    for k,v in envelope(c,stage).items():need(r.get(k)==v,'Envelope '+k)

def validate_activation(a,frame_id):
    need(type(a) is dict and set(a)=={'active_focus','focus_frame_id','edit_target_frame_id'},'Exact activation witness required')
    need(a['active_focus'] is True,'Actual active original frame required')
    for key in ('focus_frame_id','edit_target_frame_id'):
        need(type(a[key]) is int and a[key]>0 and a[key]==frame_id,'Actual original-frame activation '+key)

def validate_ready(r,c,stage,pid,baseline=None):
    need(type(pid) is int and pid>1,'Exact external child PID')
    validate_envelope(r,c,stage);need(stage!='terminal-response' and r.get('status')=='ready','Real stage READY required')
    for k,v in [('test_actor',True),('handler_replaced',False),('test_exit_used',False),('entrypoint_replaced',False)]:need(r.get(k) is v,'Scope '+k)
    need(type(r.get('checks')) is int and r['checks']>0,'Native checks required')
    i=r.get('identity',{});need(type(i.get('pid')) is int and i['pid']==pid and type(i.get('running_pid')) is int and i['running_pid']==pid and i.get('same_running_application') is True,'Independent process identity')
    need(pathlib.Path(i.get('process_image_path','')).resolve()==path(c,'native_executable_path'),'Actual dyld image')
    for k in ('running_bundle_identifier','main_bundle_identifier'):need(i.get(k)==c['bundle_id'],'Actual bundle ID')
    for k in ('running_bundle_path','main_bundle_path'):need(pathlib.Path(i.get(k,'')).resolve()==path(c,'app_path'),'Actual bundle path')
    h=r.get('host',{});dirty=c['case']!='clean' and stage!='ready'
    for k in ID_KEYS:need(type(h.get(k)) is int and h[k]>0,'Live object identity '+k)
    if baseline is not None:
        for k in ID_KEYS:need(h[k]==baseline[k],'Retained live object '+k)
    need(pathlib.Path(h.get('filename','')).resolve()==path(c,'fixture_path'),'Fixture identity')
    need(h.get('text')==c['edited_text' if dirty else 'original_text'] and h.get('modified') is dirty,'Actual exact buffer state')
    need(h.get('disk_sha256')==digest(c['original_text'].encode()),'Disk preserved before final response')
    need(h.get('verify_exit') is True and h.get('handler_unchanged') is True,'Normal handler/preferences preserved')
    m=r.get('mode_evidence',{});need(m.get('mode')==c['mode'] and type(m.get('memory_mib')) is int and m['memory_mib']==c['memory_mib'] and m.get('finder_or_apple_event_route_tested') is False,'Mode scope')
    if c['mode']=='stock':need(m.get('stock_control')=='official-generator native app running unchanged DrRacket' and m.get('native') is False,'Precise independent stock control')
    else:
        n=m.get('native',{});need(n.get('backend')=='cocoa' and n.get('explicit-name')=='NSAppearanceNameDarkAqua' and n.get('effective-name')=='NSAppearanceNameDarkAqua','Actual explicit/effective native dark appearance')
    sources=r.get('sources',[]);need(isinstance(sources,list) and len(sources)==len(SOURCE_PINS),'Complete source witness')
    need({s.get('module'):s.get('sha256') for s in sources}==SOURCE_PINS,'Exact source pins')
    e=r.get('evidence',{})
    if stage=='ready':
        need(e.get('fixture_opened_by_driver') is False and e.get('fixture_mutated') is False,'Genuine original fixture open')
        validate_activation(e.get('activation'),h['frame_id'])
    elif stage.startswith('quit-confirm'):
        validate_activation(e.get('request_activation'),h['frame_id'])
        need(type(e.get('request_attempt')) is int and e['request_attempt']==int(stage[-1]) and type(e.get('request_frame_id')) is int and e['request_frame_id']==h['frame_id'] and e.get('parent_frame_id') is False,'Quit request/frame binding')
        need(e.get('kind')=='quit' and e.get('shown') is True and e.get('checkbox_values')==[False],'Actual stock Quit confirmation')
        need(type(e.get('dialog_id')) is int and e['dialog_id']>0 and isinstance(e.get('message'),str) and e['message'],'Actual stock modal identity/message')
        need(isinstance(e.get('labels'),list) and len(e['labels'])==2,'Stock Quit controls')
    elif stage.startswith('unsaved'):
        validate_activation(e.get('request_activation'),h['frame_id'])
        need(type(e.get('request_attempt')) is int and e['request_attempt']==int(stage[-1]) and type(e.get('request_frame_id')) is int and e['request_frame_id']==h['frame_id'] and type(e.get('parent_frame_id')) is int and e['parent_frame_id']==h['frame_id'],'Unsaved request/parent binding')
        need(e.get('kind')=='unsaved' and e.get('shown') is True and e.get('checkbox_values')==[],'Actual unsaved dialog')
        need(type(e.get('dialog_id')) is int and e['dialog_id']>0 and isinstance(e.get('message'),str) and e['message'],'Actual unsaved modal identity/message')
        need(isinstance(e.get('labels'),list) and len(e['labels'])==3,'Stock unsaved controls')
    elif stage=='cancelled':
        need(e.get('focus_restored') is True and type(e.get('focus_frame_id')) is int and e['focus_frame_id']==h['frame_id'] and type(e.get('edit_target_frame_id')) is int and e['edit_target_frame_id']==h['frame_id'],'Natural focus return to original frame')
        need(e.get('exit_state_reset') is True and e.get('live_identity_preserved') is True,'Cancel is real and reversible')
        need(type(e.get('responsive_gui_turns')) is int and e['responsive_gui_turns']>=3,'Independent responsive turns')
        need(finite_real(e.get('stable_ms')) and e['stable_ms']>=1000,'Stable live Cancel interval')
    return h

def validate_terminal(r,c,pid,prior):
    validate_envelope(r,c,'terminal-response')
    need(r.get('status')=='response-dispatched' and r.get('case')==c['case'] and type(r.get('pid')) is int and r['pid']==pid,'Final stock response receipt')
    for k in ('test_exit_used','handler_replaced','cleanup_used'):need(r.get(k) is False,'Terminal '+k)
    response=r.get('response',{});need(response.get('callback_returned') is True and response.get('modal_dismissed') is True and response.get('event')=='button','Real callback returned')
    need(type(response.get('dialog_id')) is int and response['dialog_id']==prior['evidence']['dialog_id'],'Same acknowledged final dialog')
    need(type(response.get('button_id')) is int and response['button_id']>0,'Original button identity')
    # Compare against the actual localized label set captured in the identified
    # stock dialog; case chooses a fixed original index, never a report-supplied action.
    index=0 if c['case'] in ('clean','save') else 2
    need(response.get('label')==prior['evidence']['labels'][index],'Exact selected stock response')

def validate_complete(c,records,pid,returncode,elapsed,disk_bytes,*,cleanup_used,failure_seen,survivors):
    need(type(returncode) is int and returncode==0,'Natural child exit status must be zero')
    need(cleanup_used is False and failure_seen is False and not survivors,'No cleanup/failure/survivor can satisfy success')
    need(finite_real(elapsed) and 0<=elapsed<150,'Exit inside frozen process bound')
    need([x['stage'] for x in records]==stages(c),'Exact ordered complete transcript')
    baseline=None;prior=None
    for x in records:
        stage=x['stage'];r=x['report']
        if stage=='terminal-response':validate_terminal(r,c,pid,prior)
        else:
            h=validate_ready(r,c,stage,pid,baseline)
            if baseline is None:baseline=h
            need(x.get('capture_ok') is True and x.get('ack_written') is True,'Actual capture and ACK required')
            need(isinstance(x.get('screenshot_sha256'),str) and re.fullmatch('[a-f0-9]{64}',x['screenshot_sha256']),'Screenshot hash required')
        prior=r
    expected=c['edited_text' if c['case']=='save' else 'original_text'].encode()
    need(disk_bytes==expected,'Independent final exact disk bytes')
    return {'status':'passed','run_id':c['run_id'],'mode':c['mode'],'case':c['case'],'pid':pid,'natural_exit':0,
            'elapsed_seconds':elapsed,'original_disk_sha256':digest(c['original_text'].encode()),'final_disk_hex':disk_bytes.hex(),'final_disk_sha256':digest(disk_bytes),'cleanup_used':False,
            'installed_quit_handling':True,'finder_or_apple_event_route_tested':False,'stages':stages(c)}
