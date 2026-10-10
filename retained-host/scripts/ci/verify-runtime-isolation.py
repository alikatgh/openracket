#!/usr/bin/env python3
"""Verify actual collection resolution and unchanged pristine source bytes."""
import hashlib, json, os, pathlib, subprocess, sys
assert os.environ.get('GITHUB_ACTIONS') == 'true', 'CI only'
temp=pathlib.Path(os.environ['RUNNER_TEMP']).resolve()
stock=pathlib.Path(os.environ['OPENRACKET_CI_STOCK_RACKET']).resolve().parents[1]
modern=pathlib.Path(os.environ['RACKET']).resolve().parents[1]
assert stock.is_relative_to(temp) and modern.is_relative_to(temp)
checks={'toolbar':('switchable-button.rkt','mrlib'), 'framework':('main.rkt','framework'), 'drracket':('drracket.rkt','drracket')}

def inspect(runtime, addon):
    env=dict(os.environ, PLTADDONDIR=addon)
    result={}
    for name,(file,collection) in checks.items():
        code='(display (collection-file-path '+json.dumps(file)+' '+json.dumps(collection)+'))'
        path=pathlib.Path(subprocess.check_output([str(runtime/'bin/racket'),'-e',code],env=env,text=True)).resolve()
        assert path.is_relative_to(runtime), f'{name} resolved outside intended runtime: {path}'
        result[name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    return result

stock_files=inspect(stock,os.environ['OPENRACKET_CI_STOCK_ADDON'])
baseline=temp/'openracket-pristine-source-sha256.json'
if sys.argv[1:] == ['baseline']:
    assert not baseline.exists(), 'Do not overwrite pristine baseline'
    baseline.write_text(json.dumps(stock_files,indent=2)+'\n')
    print('PRISTINE_SOURCE_BASELINE '+json.dumps(stock_files,sort_keys=True))
elif sys.argv[1:] == ['compare']:
    assert stock != modern, 'Pristine and modern runtimes must be distinct'
    assert json.loads(baseline.read_text()) == stock_files, 'Pristine stock source changed'
    modern_files=inspect(modern,os.environ['PLTADDONDIR'])
    for name in checks:
        a=pathlib.Path(stock_files[name]['path']).stat()
        b=pathlib.Path(modern_files[name]['path']).stat()
        assert (a.st_dev,a.st_ino)!=(b.st_dev,b.st_ino), 'Mutable hardlink between runtimes'
    assert not (pathlib.Path(stock_files['toolbar']['path']).parent/'private/openracket-paint.rkt').exists(), 'Pristine painter was modified'
    print('PRISTINE_SOURCE_UNCHANGED '+json.dumps(stock_files,sort_keys=True))
    print('MODERN_COLLECTION_RESOLUTION '+json.dumps(modern_files,sort_keys=True))
else:
    raise SystemExit('Use baseline or compare')
