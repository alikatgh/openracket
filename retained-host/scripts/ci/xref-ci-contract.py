"""Pure isolation contract for the separate, default-off xref reply experiment."""
import pathlib
MODES=('stock','candidate-off','candidate-on')
CLEAR={'PLTUSERHOME','PLTADDONDIR','PLTCOMPILEDROOTS','PLTCOLLECTS',
       'XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'}

def selected_runtime(mode,stock,candidate):
    if mode not in MODES:raise ValueError('Unknown xref arm')
    return pathlib.Path(stock if mode=='stock' else candidate).resolve()

def environment(base,mode,purpose,*,temp,stock,candidate):
    if not purpose or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in purpose):
        raise ValueError('Explicit bounded profile label required')
    root=selected_runtime(mode,stock,candidate);temp=pathlib.Path(temp).resolve()
    if root==temp or not root.is_relative_to(temp):raise ValueError('Disposable runtime must stay inside runner temp')
    env={k:v for k,v in base.items() if not k.startswith('OPENRACKET_') and k not in CLEAR}
    home=temp/f'xref-{mode}-{purpose}';addon=temp/f'xref-{mode}-{purpose}-addon'
    env.update(RACKET=str(root/'bin/racket'),RACO=str(root/'bin/raco'),
               PLTUSERHOME=str(home),PLTADDONDIR=str(addon),
               XDG_CONFIG_HOME=str(home/'.config'),XDG_CACHE_HOME=str(home/'.cache'),
               XDG_DATA_HOME=str(home/'.local/share'))
    if mode=='candidate-on':env['OPENRACKET_XREF_REPLY_CELL']='1'
    return env

# These unmodified seams exclude all earlier scan, autosave, budget and appearance experiments.
UNCHANGED={
 'text':(('text-misc.rkt','framework','private'),'7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638'),
 'color':(('color.rkt','framework','private'),'da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578'),
 'unit':(('unit.rkt','drracket','private'),'535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5'),
 'toolbar':(('switchable-button.rkt','mrlib'),'532a707597787d6e61d420f815ee14f6a2ed1ccd342070271da5268056bd61de'),
}
