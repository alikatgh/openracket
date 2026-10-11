#!/usr/bin/env python3
"""Future authorized native controls only. No runtime preparation or publication."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
import compare_controls as graph
ROOT=Path(__file__).resolve().parents[1]
HOST_ARMS=graph.MODES
TRACE_ARMS=('stock','stock-again','named-style-candidate-off','named-style-candidate-on')
BANNED={'PYTHONOPTIMIZE','PLTCOLLECTS','PLTCOMPILEDROOTS','PLTCONFIGDIR','PLTLINKS','PLT_LINKS',
        'PLT_COMPILED_FILE_CHECK','PLT_ZO_PATH','PLTDRDEBUG','PLTDRCM','PLTDRPAR','PLTUSERHOME',
        'PLTADDONDIR','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'}

def canonical(path,directory=True):
    if not path.is_absolute() or path.resolve()!=path or path.is_symlink() or not (path.is_dir() if directory else path.is_file()):
        raise ValueError('Explicit canonical non-symlink path required: '+str(path))
    return path

def check_package():
    pins=json.loads((ROOT/'PROVENANCE.json').read_text())['unchanged_copies']
    for name,pin in pins.items():
        p=ROOT/name
        if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=pin:
            raise ValueError('Missing or changed accepted source: '+name)

def mode_for(arm):
    if arm in ('stock','stock-again'):return 'stock'
    if arm in ('candidate-off','named-style-candidate-off'):return 'candidate-off'
    if arm in ('candidate-on','named-style-candidate-on'):return 'candidate-on'
    raise ValueError('Unknown arm')

def environment(base,arm,profile,host=False):
    mode=mode_for(arm)
    contaminated=[key for key in base if key.startswith('OPENRACKET_') or key in BANNED]
    if contaminated:raise ValueError('Refusing inherited experiment/resolver environment: '+', '.join(sorted(contaminated)))
    env=dict(base)
    env.update(PLTUSERHOME=str(profile),PLTADDONDIR=str(profile/'addon'),
               XDG_CONFIG_HOME=str(profile/'.config'),XDG_CACHE_HOME=str(profile/'.cache'),
               XDG_DATA_HOME=str(profile/'.local/share'))
    if mode!='stock':env['OPENRACKET_NAMED_STYLE_INDEX']='1' if mode=='candidate-on' else '0'
    if host:env.update(OPENRACKET_NATIVE_CASE='check-syntax',OPENRACKET_UI='stock')
    return env

def command(runtime,arm,out,host):
    if host:return [str(runtime/'bin/racket'),str(ROOT/'native/bootstrap.rkt'),mode_for(arm),str(runtime)]
    # Every actual worker uses original stock xref semantics. The outer labels
    # and named-style flag do not authenticate GUI activation in these captures.
    return [str(runtime/'bin/racket'),str(ROOT/'trace/upstream/tests/native-trace.rkt'),
            '--mode','stock','--runtime-root',str(runtime),'--timeout','30','--output',str(out/'trace.json')]

def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGKILL)
    process.wait(timeout=5)

def capture(runtime,arm,out,host,*,popen=subprocess.Popen,clock=time.monotonic,sleep=time.sleep,screen=subprocess.run):
    out.mkdir();profile=out/'profile';profile.mkdir()
    env=environment(os.environ,arm,profile,host)
    ready=out/'ready.json';done=out/'capture-done';png=out/'screenshot.png'
    if host:env.update(OPENRACKET_READY_FILE=str(ready),OPENRACKET_CAPTURE_DONE=str(done))
    timeout=60 if host else 200
    cmd=command(runtime,arm,out,host)
    result={'arm':arm,'command':cmd,'runtime_root':str(runtime),'profile':str(profile),
            'named_style_flag':env.get('OPENRACKET_NAMED_STYLE_INDEX'),
            'native_executed':False,'returncode':None,'timed_out':False,'timeout_seconds':timeout,
            'capture_attempted':False,'capture_done_written':False}
    process=None
    try:
        with (out/'stdout.bin').open('wb') as stdout,(out/'stderr.bin').open('wb') as stderr:
            process=popen(cmd,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
            result['native_executed']=True
            deadline=clock()+timeout
            while process.poll() is None and clock()<deadline:
                if host and ready.exists() and not result['capture_attempted']:
                    result['capture_attempted']=True
                    try:
                        remaining=deadline-clock()
                        if remaining<=0:raise subprocess.TimeoutExpired('screen deadline',0)
                        shot=screen(['/usr/sbin/screencapture','-x',str(png)],timeout=min(15,remaining),check=False,
                                    stdout=subprocess.DEVNULL,stderr=stderr)
                        result['capture_returncode']=shot.returncode
                        if shot.returncode==0:result['screenshot']=graph.png_record(png.read_bytes())
                    except (OSError,ValueError,subprocess.TimeoutExpired):result['capture_error']=traceback.format_exc()
                    done.write_text('Native capture attempted\n');result['capture_done_written']=True
                sleep(.2)
            if process.poll() is None or clock()>=deadline:
                result['timed_out']=True
                terminate(process)
            result['returncode']=process.wait(timeout=5)
    except BaseException:
        result['failure']=traceback.format_exc()
        if process is not None and process.poll() is None:terminate(process)
    finally:
        result['files']={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in out.iterdir() if p.is_file()}
        (out/'process.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def run_matrix(stock,candidate,out):
    report={'passed':False,'native_executed':False,'host':{},'trace':{},'failures':[]}
    rows={};captures=[]
    for kind,arms in [('host',HOST_ARMS),('trace',TRACE_ARMS)]:
        for arm in arms:
            destination=out/(kind+'-'+arm)
            runtime=stock if mode_for(arm)=='stock' else candidate
            try:
                process=capture(runtime,arm,destination,kind=='host')
                report[kind][arm]=process
                report['native_executed']|=process['native_executed']
                if process['timed_out'] or process['returncode']!=0:raise ValueError('Unsuccessful native process')
                if kind=='host':
                    rows[arm]=graph.validate((destination/'stdout.bin').read_bytes(),
                                            (destination/'ready.json').read_bytes(),process,arm,(destination/'screenshot.png').read_bytes())
                else:captures.append(destination/'trace.json')
            except BaseException:report['failures'].append({'kind':kind,'arm':arm,'details':traceback.format_exc()})
    try:
        if len(rows)==3:report['graph_comparison']=graph.compare(rows)
        if len(captures)==4:
            spec=importlib.util.spec_from_file_location('trace_gate',ROOT/'trace/compare-named-style-trace.py')
            gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
            raw=[p.read_bytes() for p in captures]
            report['trace_comparison']=gate.compare(*[json.loads(b) for b in raw],
                                                    json.loads((ROOT/'trace/upstream/manifest.json').read_text()))
            report['trace_comparison']['input_sha256']={str(p):hashlib.sha256(b).hexdigest() for p,b in zip(captures,raw)}
        report['passed']=not report['failures'] and len(rows)==3 and len(captures)==4
    except BaseException:report['failures'].append({'kind':'comparison','details':traceback.format_exc()})
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stock-root',type=Path,required=True);p.add_argument('--candidate-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--authorize-native-execution',action='store_true')
    a=p.parse_args()
    if not a.authorize_native_execution:p.error('Native execution remains on hold; explicit authorization required')
    if os.uname().sysname!='Darwin':p.error('This capture adapter requires the established macOS native screen contract')
    check_package()
    roots=[canonical(a.stock_root),canonical(a.candidate_root)]
    if roots[0]==roots[1] or roots[0] in roots[1].parents or roots[1] in roots[0].parents:p.error('Separate nonoverlapping prepared runtimes required')
    for root in roots:
        executable=canonical(root/'bin/racket',False)
        if not os.access(executable,os.X_OK):p.error('Racket executable not executable')
    environment(os.environ,'stock',a.output/'probe')
    out=a.output.absolute()
    if out.exists():p.error('New output directory required; previous raw evidence is never overwritten')
    out.mkdir(parents=True)
    result=run_matrix(*roots,out)
    print(json.dumps({'passed':result['passed'],'native_executed':result['native_executed'],'report':str(out/'report.json')}))
    return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
