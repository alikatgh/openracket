"""Bounded process/capture supervision and lossless raw evidence transport."""
import base64, hashlib, importlib.util, json, os, pathlib, signal, struct, subprocess, time, traceback, zlib
P=pathlib.Path
RAW_LIMIT=128*1024*1024
PART_LIMIT=1024*1024

def file_digest(path):
    h=hashlib.sha256()
    with P(path).open('rb') as stream:
        for b in iter(lambda:stream.read(PART_LIMIT),b''):h.update(b)
    return h.hexdigest()

def durable_json(path,value):
    path=P(path)
    with path.open('x') as stream:
        json.dump(value,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def live_group_members(pgid):
    result=subprocess.run(['/bin/ps','-axo','pid=,pgid=,stat=,uid='],text=True,capture_output=True,check=True,timeout=3)
    members=[]
    for line in result.stdout.splitlines():
        columns=line.split()
        if len(columns)!=4:continue
        pid,group,state,uid=columns
        if int(group)==pgid and not state.startswith('Z'):members.append({'pid':int(pid),'state':state,'uid':int(uid)})
    return members

def signal_group(pgid,sig):
    try:os.killpg(pgid,sig);return True
    except ProcessLookupError:return False
    except PermissionError:
        if not live_group_members(pgid):return False
        raise

def terminate_group(process):
    # Same accepted group teardown semantics as performance/run.py; never infer
    # descendant completion merely from the group leader's exit.
    signal_group(process.pid,signal.SIGTERM)
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        signal_group(process.pid,signal.SIGKILL);process.wait(timeout=5)
    if live_group_members(process.pid):signal_group(process.pid,signal.SIGKILL)
    deadline=time.monotonic()+2
    while live_group_members(process.pid):
        if time.monotonic()>=deadline:raise RuntimeError('Process group still has live members after SIGKILL')
        time.sleep(.025)

def png_record(raw):
    def need(ok,why):
        if not ok:raise ValueError(why)
    need(type(raw) is bytes and 45<=len(raw)<=32*1024*1024 and raw[:8]==b'\x89PNG\r\n\x1a\n','Bounded PNG signature')
    pos=8;first=True;data=False;ended=False;width=height=0;compressed=[];palette=False;idat_closed=False
    while pos<len(raw):
        need(pos+12<=len(raw),'Truncated PNG chunk');size=struct.unpack('>I',raw[pos:pos+4])[0];kind=raw[pos+4:pos+8];end=pos+size+12
        need(end<=len(raw),'Truncated PNG payload');payload=raw[pos+8:end-4]
        need(zlib.crc32(kind+payload)==struct.unpack('>I',raw[end-4:end])[0],'PNG CRC')
        if first:
            need(kind==b'IHDR' and size==13,'PNG IHDR');width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',payload)
            need(0<width<=16384 and 0<height<=16384 and width*height<=100_000_000,'PNG dimensions')
            need(color in (0,2,3,4,6) and depth in {0:(1,2,4,8,16),2:(8,16),3:(1,2,4,8),4:(8,16),6:(8,16)}[color] and compression==filtering==0 and interlace in (0,1),'PNG format');first=False
        else:need(kind!=b'IHDR','Duplicate PNG IHDR')
        if kind==b'PLTE':
            need(not data and not palette and color not in (0,4) and size%3==0 and 1<=size//3<=256,'PNG palette');palette=True
            if color==3:need(size//3<=2**depth,'PNG indexed palette size')
        if kind==b'IDAT':
            need(not idat_closed and (color!=3 or palette),'Contiguous PNG data with required palette');data=True;compressed.append(payload)
        elif data:idat_closed=True
        need(kind in (b'IHDR',b'PLTE',b'IDAT',b'IEND') or (kind[0]&32)!=0,'Unknown critical PNG chunk')
        if kind==b'IEND':need(size==0 and end==len(raw) and data,'PNG end');ended=True
        pos=end
    need(ended,'Missing PNG end')
    channels={0:1,2:3,3:1,4:2,6:4}[color]
    passes=[(0,0,1,1)] if interlace==0 else [(0,0,8,8),(4,0,8,8),(0,4,4,8),(2,0,4,4),(0,2,2,4),(1,0,2,2),(0,1,1,2)]
    layouts=[]
    for x,y,dx,dy in passes:
        w=max(0,(width-x+dx-1)//dx);h=max(0,(height-y+dy-1)//dy)
        if w and h:layouts.append((((w*channels*depth+7)//8)+1,h))
    expected=sum(row*rows for row,rows in layouts);need(expected<=128*1024*1024,'Bounded decoded screenshot pixels')
    decoder=zlib.decompressobj()
    try:pixels=decoder.decompress(b''.join(compressed),expected+1)
    except zlib.error as error:raise ValueError('Invalid PNG compressed pixel data') from error
    need(len(pixels)==expected and decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data,'Exact complete PNG pixel stream')
    offset=0
    for stride,rows in layouts:
        for _ in range(rows):need(pixels[offset] in range(5),'PNG scanline filter');offset+=stride
    return {'format':'PNG','bytes':len(raw),'width':width,'height':height,'sha256':hashlib.sha256(raw).hexdigest()}

class Supervisor:
    def __init__(self,reports):
        self.reports=P(reports);self.reports.mkdir(parents=True,exist_ok=True);self.lease=self.reports/'launch-blocked.json';self.blocked=False
    def run(self,name,argv,env,cwd,timeout,*,host=False,popen=subprocess.Popen,clock=time.monotonic,sleep=time.sleep):
        if self.blocked or self.lease.exists():raise RuntimeError('Launch blocked by durable pending/unverified lease')
        out=self.reports/name;out.mkdir();ready=out/'ready.json';done=out/'capture-done';png=out/'screenshot.png'
        env=dict(env)
        if host:env.update(OPENRACKET_READY_FILE=str(ready),OPENRACKET_CAPTURE_DONE=str(done))
        row={'name':name,'command':[str(x) for x in argv],'environment':env,'cwd':str(cwd),'timeout_seconds':timeout,'native_executed':False,'returncode':None,'timed_out':False,'output_bound_exceeded':False,'cleanup_verified':False,'capture_attempted':False,'capture_done_written':False}
        durable_json(out/'command.json',row)
        durable_json(self.lease,{'name':name,'command':row['command'],'state':'prelaunch'})
        proc=None;completion=False;launch_attempted=False
        try:
            with (out/'stdout.bin').open('wb') as stdout,(out/'stderr.bin').open('wb') as stderr:
                deadline=clock()+timeout;launch_attempted=True
                proc=popen(row['command'],env=env,cwd=str(cwd),stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
                row['native_executed']=True;row['pid']=proc.pid
                while proc.poll() is None and clock()<deadline:
                    if stdout.tell()+stderr.tell()>RAW_LIMIT:row['output_bound_exceeded']=True;break
                    if host and ready.exists() and not row['capture_attempted']:
                        row['capture_attempted']=True
                        screen=None;screen_lease=out/'capture-lease.json'
                        try:
                            remaining=deadline-clock()
                            if remaining<=0:raise subprocess.TimeoutExpired('capture deadline',0)
                            screen_cmd=['/usr/sbin/screencapture','-x',str(png)]
                            durable_json(screen_lease,{'command':screen_cmd,'state':'prelaunch','timeout_seconds':min(15,remaining)})
                            with (out/'capture-stdout.bin').open('wb') as so,(out/'capture-stderr.bin').open('wb') as se:
                                screen_deadline=clock()+min(15,remaining)
                                screen=popen(screen_cmd,env=env,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
                                try:row['capture_returncode']=screen.wait(timeout=max(0,screen_deadline-clock()))
                                except subprocess.TimeoutExpired:terminate_group(screen);raise
                                if live_group_members(screen.pid):terminate_group(screen)
                            screen_lease.unlink()
                            if row['capture_returncode']==0:row['screenshot']=png_record(png.read_bytes())
                        except BaseException:
                            row['capture_error']=traceback.format_exc()
                            if screen is not None:
                                try:terminate_group(screen);screen_lease.unlink(missing_ok=True)
                                except BaseException:self.blocked=True;row['capture_cleanup_error']=traceback.format_exc()
                            elif screen_lease.exists():
                                self.blocked=True;row['capture_cleanup_error']='Uncertain capture spawn without process handle'
                        if self.blocked:break
                        done.write_text('Native capture attempted\n');row['capture_done_written']=True
                    sleep(.05)
                if proc.poll() is None or clock()>=deadline or row['output_bound_exceeded'] or self.blocked:
                    row['timed_out']=clock()>=deadline;terminate_group(proc)
                elif live_group_members(proc.pid):terminate_group(proc)
                row['returncode']=proc.wait(timeout=5);completion=True
                if stdout.tell()+stderr.tell()>RAW_LIMIT:row['output_bound_exceeded']=True
                row['cleanup_verified']=not self.blocked
        except BaseException:
            row['failure']=traceback.format_exc()
            if proc is not None and not completion:
                try:terminate_group(proc);completion=True;row['cleanup_verified']=not self.blocked;row['returncode']=proc.poll()
                except BaseException:self.blocked=True;row['cleanup_error']=traceback.format_exc()
        finally:
            if proc is None:
                completion=not launch_attempted
                if launch_attempted:self.blocked=True;row['cleanup_error']='Uncertain spawn: Popen raised without returning a process handle'
            if completion and not self.blocked:
                try:self.lease.unlink()
                except BaseException:self.blocked=True;row['cleanup_verified']=False;row['lease_cleanup_error']=traceback.format_exc()
            else:self.blocked=True
            row['passed']=not self.blocked and not self.lease.exists() and row['returncode']==0 and row['cleanup_verified'] and not row['timed_out'] and not row['output_bound_exceeded'] and not row.get('failure')
            if host:row['passed']=row['passed'] and row['capture_attempted'] and row['capture_done_written'] and row.get('capture_returncode')==0 and 'screenshot' in row
            row['files']={p.name:{'bytes':p.stat().st_size,'sha256':file_digest(p)} for p in out.iterdir() if p.is_file()}
            durable_json(out/'process.json',row)
        return row,out

def raw_documents(path,relative):
    path=P(path);size=path.stat().st_size;digest=hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(PART_LIMIT),b''):digest.update(b)
    count=max(1,(size+PART_LIMIT-1)//PART_LIMIT)
    with path.open('rb') as stream:
        for index in range(count):
            raw=stream.read(PART_LIMIT)
            yield {'schema':'object-hash-raw-evidence/v1','source_relative_path':relative,'raw_bytes':size,'raw_sha256':digest.hexdigest(),'part':index,'parts':count,'part_bytes':len(raw),'part_sha256':hashlib.sha256(raw).hexdigest(),'encoding':'base64','chunks':[base64.b64encode(raw[n:n+12288]).decode('ascii') for n in range(0,len(raw),12288)]}

def restore_documents(documents):
    if type(documents) is not list or not documents:raise ValueError('No raw document parts')
    fields={'schema','source_relative_path','raw_bytes','raw_sha256','part','parts','part_bytes','part_sha256','encoding','chunks'}
    for row in documents:
        if type(row) is not dict or set(row)!=fields or row['schema']!='object-hash-raw-evidence/v1' or row['encoding']!='base64':raise ValueError('Raw document shape')
        for k in ('raw_bytes','part','parts','part_bytes'):
            if type(row[k]) is not int or row[k]<0:raise ValueError('Exact nonnegative integer required')
        if row['parts']<1 or row['part']>=row['parts'] or row['part_bytes']>PART_LIMIT or row['parts']!=max(1,(row['raw_bytes']+PART_LIMIT-1)//PART_LIMIT):raise ValueError('Raw size/sequence bounds')
        path=row['source_relative_path']
        if type(path) is not str or not path or pathlib.PurePosixPath(path).is_absolute() or '..' in pathlib.PurePosixPath(path).parts or str(pathlib.PurePosixPath(path))!=path:raise ValueError('Relative evidence path required')
        for k in ('raw_sha256','part_sha256'):
            if type(row[k]) is not str or len(row[k])!=64 or any(c not in '0123456789abcdef' for c in row[k]):raise ValueError('Raw hash encoding')
        if type(row['chunks']) is not list or any(type(x) is not str or len(x)>16384 for x in row['chunks']):raise ValueError('Bounded raw chunks')
    first=documents[0];raw=[]
    if len(documents)!=first['parts']:raise ValueError('Missing raw part')
    for i,row in enumerate(documents):
        if row['part']!=i or any(row[k]!=first[k] for k in ('schema','source_relative_path','raw_bytes','raw_sha256','parts','encoding')):raise ValueError('Raw part identity/order mismatch')
        b=b''.join(base64.b64decode(x,validate=True) for x in row['chunks'])
        if len(b)!=row['part_bytes'] or hashlib.sha256(b).hexdigest()!=row['part_sha256']:raise ValueError('Raw part byte hash mismatch')
        raw.append(b)
    out=b''.join(raw)
    if len(out)!=first['raw_bytes'] or hashlib.sha256(out).hexdigest()!=first['raw_sha256']:raise ValueError('Raw complete byte hash mismatch')
    return out

def emit_all(reports,emitter):
    reports=P(reports);transport=reports/'transport';transport.mkdir(exist_ok=True);index=[];errors=[]
    # Enumerate before making transport copies; no recursive self-transport.
    paths=[p for p in sorted(reports.rglob('*')) if p.is_file() and not p.is_relative_to(transport)]
    for n,path in enumerate(paths):
        relative=str(path.relative_to(reports))
        try:
            if path.is_symlink():raise ValueError('Evidence link refused')
            entry={'path':relative,'raw_bytes':path.stat().st_size,'raw_sha256':file_digest(path),'parts_emitted':[]};index.append(entry)
            for part,row in enumerate(raw_documents(path,relative)):
                try:
                    folder=transport/('raw-%05d-%04d'%(n,part));folder.mkdir();target=folder/'supervisor.json';target.write_text(json.dumps(row,separators=(',',':'))+'\n');emitter.emit(target);entry['parts_emitted'].append(part)
                except Exception as error:errors.append({'path':relative,'part':part,'error':str(error)})
        except Exception as error:errors.append({'path':relative,'error':str(error)})
    result={'schema':'object-hash-raw-index/v1','complete':not errors,'files':index,'errors':errors}
    target=transport/'summary.json';target.write_text(json.dumps(result,separators=(',',':'))+'\n')
    try:emitter.emit(target)
    except Exception as error:
        errors.append({'path':'transport/summary.json','error':str(error)});result['complete']=False
        # Never retry a potentially partial emitted document.
        (reports/'transport-failure.json').write_text(json.dumps(result,sort_keys=True)+'\n')
    return result
