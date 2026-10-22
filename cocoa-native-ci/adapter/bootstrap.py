"""Single-command SDK helper bootstrap. Never a general command runner.

A failure leaves launch-blocked.json in place. Before the helper exists, the
unreaped direct child anchors signals, but descendant quiescence is NOT claimed.
Success is accepted only after the SHA-bound new helper certifies quiescence.
The compiled helper never gets permission to launch a process.
"""
from pathlib import Path
import hashlib, json, os, select, signal, stat, sys, time

LIMIT = 4 * 1024 * 1024

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()

def durable(path, value, *, replace=False):
    path = Path(path)
    target = path.with_name(path.name + '.new') if replace else path
    with target.open('x') as f:
        json.dump(value, f, sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
    if replace: os.replace(target, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def physical(path):
    p = Path(path)
    if not p.is_absolute() or p.resolve(strict=True) != p: raise ValueError('Physical absolute path required')
    return p

def observe(pid):
    return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)

def bootstrap(module, source, compiler, sdk, output, root, env, *, timeout=90):
    """Only compile the exact pinned helper. Linux/native fakes are not accepted."""
    if sys.platform != 'darwin' or sys.version_info < (3, 13): raise ValueError('Darwin Python >=3.13 required')
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL: raise ValueError('Default SIGCHLD required')
    source, compiler, sdk, root = map(physical, (source, compiler, sdk, root))
    output = root / 'openracket_process_inventory.dylib'
    pin = json.loads((source.parent/'darwin-process-helper-source-pin.json').read_bytes())
    if sha(source) != pin['source_sha256'] or sha(source.parent/pin['official_source_proof']) != pin['official_source_proof_sha256']:
        raise ValueError('Exact helper source/proof pin mismatch')
    if output.exists() or output.is_symlink(): raise ValueError('Fresh helper output required')
    argv = [str(compiler), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fvisibility=hidden',
            '-isysroot', str(sdk), '-dynamiclib', '-Wl,-install_name,@rpath/openracket_process_inventory.dylib',
            '-o', str(output), str(source)]
    lease = root/'launch-blocked.json'
    row = {'schema':'openracket-sdk-bootstrap/v1','argv':argv,'timeout_seconds':timeout,
           'source_sha256':sha(source),'compiler_physical_path':str(compiler),'compiler_sha256':sha(compiler),
           'sdk_path':str(sdk),'environment_sha256':hashlib.sha256(json.dumps(env,sort_keys=True).encode()).hexdigest(),
           'phase':'prelaunch','safe_to_continue':False,'group_quiescent':False,'leader_reaped':False,
           'started_ns':time.time_ns(),'signals':[]}
    durable(lease,row)
    pid = None; group = False; reaped = False; opened = []; helper_sha = None
    out = err = None
    def anchored_signal(sig):
        if pid is None or reaped: return
        observe(pid)  # Ownership and unreaped PID proof; never recover PIDs from disk.
        if group:
            if os.getpgid(pid) != pid or os.getsid(pid) != pid: raise RuntimeError('Bootstrap leader lost session/group')
            os.killpg(pid,sig)
        else: os.kill(pid,sig)
        row['signals'].append(signal.Signals(sig).name)
    try:
        out=os.open(root/'compiler.stdout',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        err=os.open(root/'compiler.stderr',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        gate_r,gate_w=os.pipe();ready_r,ready_w=os.pipe();opened=[gate_r,gate_w,ready_r,ready_w]
        os.set_blocking(ready_r,False)
        inherited=[int(n) for n in os.listdir('/dev/fd') if n.isdigit()]
        deadline=time.monotonic()+timeout
        oldmask=signal.pthread_sigmask(signal.SIG_BLOCK,signal.valid_signals()-{signal.SIGKILL,signal.SIGSTOP})
        try:
            pid=os.fork()
            if pid==0:
                module.Supervisor._child_exec(argv,str(root),env,gate_r,ready_w,out,err,inherited,oldmask)
                os._exit(127)
        finally: signal.pthread_sigmask(signal.SIG_SETMASK,oldmask)
        row['pid']=pid
        for fd in (gate_r,ready_w): os.close(fd);opened.remove(fd)
        ready=b''
        while not ready.startswith(b'R'):
            if time.monotonic()>=deadline: raise TimeoutError('Bootstrap readiness deadline')
            available,_,_=select.select([ready_r],[],[],min(.05,max(0,deadline-time.monotonic())))
            if available:
                chunk=os.read(ready_r,4096);ready+=chunk
                if not chunk or ready.startswith(b'E'): raise RuntimeError('Bootstrap child setup failed')
            if observe(pid) is not None: raise RuntimeError('Bootstrap child exited before exec gate')
        if os.getpgid(pid)!=pid or os.getsid(pid)!=pid: raise RuntimeError('Bootstrap session/group mismatch')
        group=True;row.update(phase='owned',pgid=pid,sid=pid)
        durable(lease,row,replace=True)
        if time.monotonic()>=deadline: raise TimeoutError('Bootstrap deadline before exec')
        os.write(gate_w,b'G');os.close(gate_w);opened.remove(gate_w)
        while observe(pid) is None:
            if time.monotonic()>=deadline: raise TimeoutError('Compiler deadline')
            if max(os.fstat(out).st_size,os.fstat(err).st_size)>LIMIT: raise RuntimeError('Compiler output bound exceeded')
            time.sleep(.02)
        status=observe(pid)
        if status.si_code != os.CLD_EXITED or status.si_status != 0: raise RuntimeError('Compiler did not exit successfully')
        if max(os.fstat(out).st_size,os.fstat(err).st_size)>LIMIT: raise RuntimeError('Compiler output bound exceeded')
        if sha(source)!=row['source_sha256'] or sha(compiler)!=row['compiler_sha256']: raise RuntimeError('Bootstrap input changed')
        helper_sha=sha(output)
        inventory=module._DarwinSDKInventory(str(output),helper_sha)
        row['output_sha256']=helper_sha
        birth=inventory.identity(pid)
        if birth.pgid!=pid or not birth.dead: raise RuntimeError('Unreaped compiler identity mismatch')
        row['leader_birth']=birth.start
        quiet=False;cleanup_deadline=time.monotonic()+3;sent=False
        while time.monotonic()<cleanup_deadline:
            observe(pid)
            before=inventory.pids();live=False;seen=False
            for child in before:
                if time.monotonic()>=cleanup_deadline: raise TimeoutError('Bootstrap inventory deadline')
                try: identity=inventory.identity(child)
                except ProcessLookupError: continue
                if child==pid:
                    seen=True
                    if identity.start!=birth.start or identity.pgid!=pid: raise RuntimeError('Compiler identity changed')
                if identity.pgid==pid and not identity.dead: live=True
            after=inventory.pids()
            if seen and not live and not (after-before): quiet=True;break
            if not sent: anchored_signal(signal.SIGTERM);sent=True
            elif cleanup_deadline-time.monotonic()<2: anchored_signal(signal.SIGKILL)
            time.sleep(.02)
        if not quiet: raise RuntimeError('Bootstrap descendant cleanup unverified')
        got,status=os.waitpid(pid,os.WNOHANG)
        if got!=pid: raise RuntimeError('Compiler not reapable after quiescence')
        reaped=True;row.update(phase='complete',safe_to_continue=True,group_quiescent=True,leader_reaped=True,returncode=os.waitstatus_to_exitcode(status))
    except BaseException as error:
        row.update(phase='blocked',error=type(error).__name__+': '+str(error),safe_to_continue=False)
        # No inventory fallback. Stop only memory-owned/anchored processes.
        if pid is not None and not reaped:
            try:
                anchored_signal(signal.SIGTERM);time.sleep(.25);anchored_signal(signal.SIGKILL)
                until=time.monotonic()+2
                while observe(pid) is None and time.monotonic()<until: time.sleep(.02)
                if observe(pid) is not None:
                    got,status=os.waitpid(pid,os.WNOHANG)
                    if got==pid:reaped=True;row.update(leader_reaped=True,returncode=os.waitstatus_to_exitcode(status))
            except BaseException as cleanup: row['cleanup_error']=type(cleanup).__name__+': '+str(cleanup)
        # Even a reaped compiler does not prove descendants quiet on failure.
        row['group_quiescent']=False
        raise
    finally:
        for fd in opened:
            try: os.close(fd)
            except OSError: pass
        for fd in (out,err):
            if fd is not None:os.fsync(fd);os.close(fd)
        row['finished_ns']=time.time_ns()
        row['logs']={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in (root/'compiler.stdout',root/'compiler.stderr') if p.is_file()}
        if output.is_file() and not output.is_symlink(): row['partial_output']={'bytes':output.stat().st_size,'sha256':sha(output)}
        durable(root/'bootstrap-receipt.json',row)
        durable(lease,row,replace=True)
    return output,helper_sha,row
