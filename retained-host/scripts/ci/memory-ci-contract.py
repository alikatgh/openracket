"""Fresh-profile boundaries for the Mac stock-memory setting experiment."""
import pathlib
LIMITS=(128,256,512)
ORDER=((128,256,512),(256,512,128),(512,128,256))
CLEAR={'PLTCONFIGDIR','PLT_COMPILED_FILE_CHECK','PLTUSERHOME','PLTADDONDIR','PLTCOMPILEDROOTS','PLTCOLLECTS',
       'XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'}
def environment(base,purpose,*,temp,runtime):
 if not purpose or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in purpose):
  raise ValueError('Explicit bounded fresh profile label required')
 root=pathlib.Path(runtime).resolve();temp=pathlib.Path(temp).resolve()
 if root==temp or not root.is_relative_to(temp):raise ValueError('Disposable clone required')
 result={k:v for k,v in base.items() if not k.startswith('OPENRACKET_') and k not in CLEAR}
 home=temp/f'memory-{purpose}';addon=temp/f'memory-{purpose}-addon'
 result.update(RACKET=str(root/'bin/racket'),RACO=str(root/'bin/raco'),
  PLTUSERHOME=str(home),PLTADDONDIR=str(addon),XDG_CONFIG_HOME=str(home/'.config'),
  XDG_CACHE_HOME=str(home/'.cache'),XDG_DATA_HOME=str(home/'.local/share'))
 return result

def require_capacity(physical_bytes):
 if type(physical_bytes) is not int or physical_bytes<4*1024**3:
  raise ValueError('At least 4 GiB physical runner RAM required for the bounded 512 MiB setting experiment')
 return physical_bytes
