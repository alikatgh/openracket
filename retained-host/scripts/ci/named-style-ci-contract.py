"""Pure isolation contract for the separate, default-off named-style lookup experiment."""
import pathlib
MODES=('stock','candidate-off','candidate-on')
CLEAR={'PYTHONOPTIMIZE','PLT_LINKS','PLTLINKS','PLT_ZO_PATH','PLTDRDEBUG','PLTDRCM','PLTDRPAR','PLTCONFIGDIR','PLT_COMPILED_FILE_CHECK','PLTUSERHOME','PLTADDONDIR','PLTCOMPILEDROOTS','PLTCOLLECTS',
       'XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'}

def selected_runtime(mode,stock,candidate):
    if mode not in MODES:raise ValueError('Unknown named-style arm')
    return pathlib.Path(stock if mode=='stock' else candidate).resolve()

def environment(base,mode,purpose,*,temp,stock,candidate):
    if not purpose or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in purpose):
        raise ValueError('Explicit bounded profile label required')
    root=selected_runtime(mode,stock,candidate);temp=pathlib.Path(temp).resolve()
    s=pathlib.Path(stock).resolve();c=pathlib.Path(candidate).resolve()
    if s==c or s.is_relative_to(c) or c.is_relative_to(s):raise ValueError('Independent non-overlapping runtime roots required')
    if root==temp or not root.is_relative_to(temp):raise ValueError('Disposable runtime must stay inside runner temp')
    env={k:v for k,v in base.items() if not k.startswith('OPENRACKET_') and k not in CLEAR}
    home=temp/f'named-style-{mode}-{purpose}';addon=temp/f'named-style-{mode}-{purpose}-addon'
    env.update(RACKET=str(root/'bin/racket'),RACO=str(root/'bin/raco'),
               PLTUSERHOME=str(home),PLTADDONDIR=str(addon),
               XDG_CONFIG_HOME=str(home/'.config'),XDG_CACHE_HOME=str(home/'.cache'),
               XDG_DATA_HOME=str(home/'.local/share'))
    if mode!='stock':env['OPENRACKET_NAMED_STYLE_INDEX']='1' if mode=='candidate-on' else '0'
    return env

# These unmodified seams exclude all earlier scan, autosave, budget and appearance experiments.
UNCHANGED={
 'text':(('text-misc.rkt','framework','private'),'7f95100d31c510ae1b29ddf01c6801d34ba709880b0dfc953ccd895a5bb06638'),
 'color':(('color.rkt','framework','private'),'da45ea64a5a0b413296a60ebe61d3e5ee69a27b53a6f1e13ae258701bdce1578'),
 'unit':(('unit.rkt','drracket','private'),'535a8a60592727cbba63bcd4485925cfaec49dbc3ebb9173715eb4ec5c7caff5'),
 'toolbar':(('switchable-button.rkt','mrlib'),'532a707597787d6e61d420f815ee14f6a2ed1ccd342070271da5268056bd61de'),
}

UNCHANGED['xref']=(('xref.rkt','drracket','private','syncheck'),'acd0ea9b93bcbb4d7df18f022f803f7ce6bd572b0aca0ac170ff0164917873f7')

def trial_order():
    return [(pair,mode) for pair in range(1,4) for mode in (('candidate-on','stock') if pair==2 else ('stock','candidate-on'))]

UNCHANGED['interval']=(('interval-map.rkt','data'),'1e18a3dafc6e1e87fd79c6fc67b5fd1c5cfd803f3caebf7c9f0ab0801ebb45de')


def clean_environment(base):
    return {k:v for k,v in base.items() if not k.startswith("OPENRACKET_") and k not in CLEAR}
