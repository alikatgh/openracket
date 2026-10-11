"""Outside-timing raw/canonical evidence binding; never alters source or input files."""
import hashlib,json,pathlib

def canonical(value):
 return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()

def input_record(path,label=None):
 path=pathlib.Path(path)
 if path.is_symlink() or not path.is_file() or path.stat().st_size>24*1024*1024:raise ValueError('Missing, linked or oversized input')
 raw=path.read_bytes()
 def pairs(xs):
  result={}
  for key,value in xs:
   if key in result:raise ValueError('Duplicate input JSON key')
   result[key]=value
  return result
 def invalid(value):raise ValueError('Nonfinite input JSON')
 value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
 if type(value) is not dict:raise ValueError('Input JSON must be object')
 return {'label':label or path.parent.name+'-'+path.stem,'path':str(path.resolve()),'bytes':len(raw),
         'raw_sha256':hashlib.sha256(raw).hexdigest(),'canonical_sha256':hashlib.sha256(canonical(value)).hexdigest()}

INPUT_NAMES=('capture-host','capture-supervisor','memory-profile','gui-observation','worker-init','worker-phase-1','activation','heartbeat','binding-export','style-witness')
def expected_labels():
 return {'stock-prepared-manifest','candidate-prepared-manifest'}|{f'pair-{pair}-{arm}-{name}' for pair in range(1,4) for arm in ('stock','candidate') for name in INPUT_NAMES}
def binding_errors(entries,receipts):
 errors=[];bylabel={};bypath={}
 if type(entries) is not list:return ['Entries must be a list']
 for row in entries:
  try:
   if type(row) is not dict or set(row)!={'label','path','bytes','raw_sha256','canonical_sha256'}:raise ValueError('Wrong digest row fields')
   if type(row['label']) is not str or row['label'] in bylabel:raise ValueError('Duplicate/invalid label')
   if type(row['path']) is not str or not pathlib.Path(row['path']).is_absolute() or row['path'] in bypath:raise ValueError('Duplicate/invalid native path')
   if type(row['bytes']) is not int or row['bytes']<=0:raise ValueError('Invalid byte count')
   for key in ('raw_sha256','canonical_sha256'):
    if type(row[key]) is not str or len(row[key])!=64 or any(c not in '0123456789abcdef' for c in row[key]):raise ValueError('Invalid input digest')
   bylabel[row['label']]=row;bypath[row['path']]=row
  except (KeyError,ValueError,TypeError) as e:errors.append(str(e))
 if set(bylabel)!=expected_labels():errors.append('Exact62 input labels required')
 if type(receipts) is not dict or set(receipts)!={1,2,3}:errors.append('Three actual pair receipts required');return errors
 for pair,receipt in receipts.items():
  try:
   hashes=receipt.get('input_sha256') if type(receipt) is dict else None
   labels={f'pair-{pair}-{arm}-{name}' for arm in ('stock','candidate') for name in INPUT_NAMES}
   expected={bylabel[label]['path']:bylabel[label]['raw_sha256'] for label in labels}
   if type(hashes) is not dict or hashes!=expected:raise ValueError('Exact pair raw input hash coverage differs')
  except (KeyError,TypeError,ValueError) as e:errors.append(f'pair {pair}: {e}')
 return errors

def create_map(items,acceptances,output):
 entries=[];errors=[]
 for path,label in items:
  try:entries.append(input_record(path,label))
  except (OSError,ValueError,TypeError) as e:errors.append({'path':str(path),'error':str(e)})
 receipts={}
 for index,path in enumerate(acceptances,1):
  try:
   if pathlib.Path(path).parent.name!=f'pair-{index}':raise ValueError('Pair receipt order/path differs')
   receipts[index]=json.loads(pathlib.Path(path).read_bytes())
  except (OSError,ValueError,TypeError) as e:errors.append({'path':str(path),'error':str(e)})
 errors += [{'error':error} for error in binding_errors(entries,receipts)]
 # Frozen pair receipts hash only20 arm files. The already-hashed supervisor
 # records separately bind each prepared manifest's original path and raw bytes.
 bylabel={entry['label']:entry for entry in entries}
 for pair in range(1,4):
  for arm in ('stock','candidate'):
   try:
    supervisor=bylabel[f'pair-{pair}-{arm}-capture-supervisor'];manifest=bylabel[arm+'-prepared-manifest']
    value=json.loads(pathlib.Path(supervisor['path']).read_bytes())
    if type(value) is not dict or value.get('manifest')!=manifest['path'] or value.get('manifest_sha256')!=manifest['raw_sha256']:raise ValueError('Supervisor does not bind original prepared manifest')
   except (OSError,KeyError,ValueError,TypeError) as e:errors.append({'pair':pair,'arm':arm,'error':str(e)})
 result={'schema_version':1,'kind':'named-style-input-digests','entries':entries,'errors':errors,
         'verified':not errors,
         'scope':'Original bytes and separately canonicalized JSON; computed outside measured workload'}
 pathlib.Path(output).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 return result

TEXT_KEY='__openracket_text__'
def wrap_text(value):
 if isinstance(value,dict):
  if TEXT_KEY in value:raise ValueError('Reserved text-wrapper field')
  return {k:wrap_text(v) for k,v in value.items()}
 if isinstance(value,list):return [wrap_text(v) for v in value]
 if isinstance(value,str) and len(value)>2000:
  raw=value.encode('utf-8')
  return {TEXT_KEY:1,'characters':len(value),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
          'chunks':[{'index':i//2000,'text':value[i:i+2000]} for i in range(0,len(value),2000)]}
 return value

def restore_text(value):
 if isinstance(value,dict):
  if TEXT_KEY in value:
   if set(value)!={TEXT_KEY,'characters','bytes','sha256','chunks'} or type(value[TEXT_KEY]) is not int or value[TEXT_KEY]!=1:raise ValueError('Malformed text wrapper')
   rows=value['chunks']
   if type(rows) is not list or not rows:raise ValueError('Missing text chunks')
   for index,row in enumerate(rows):
    if type(row) is not dict or set(row)!={'index','text'} or type(row['index']) is not int or row['index']!=index or type(row['text']) is not str or not 1<=len(row['text'])<=2000:raise ValueError('Missing, duplicate, reordered or malformed text chunk')
   text=''.join(row['text'] for row in rows);raw=text.encode('utf-8')
   if type(value['characters']) is not int or type(value['bytes']) is not int or len(text)!=value['characters'] or len(raw)!=value['bytes'] or hashlib.sha256(raw).hexdigest()!=value['sha256']:raise ValueError('Text digest/length differs')
   return text
  return {k:restore_text(v) for k,v in value.items()}
 if isinstance(value,list):return [restore_text(v) for v in value]
 return value

def transport_json_copy(source,destination):
 source=pathlib.Path(source);raw=source.read_bytes();value=json.loads(raw)
 wrapped={'schema_version':1,'kind':'lossless-native-json-text-wrapper','original_raw_sha256':hashlib.sha256(raw).hexdigest(),
          'original_bytes':len(raw),'original_canonical_sha256':hashlib.sha256(canonical(value)).hexdigest(),
          'document':wrap_text(value),'scope':'Explicit outside-timing transport wrapper; original native JSON file remains unchanged'}
 if restore_text(wrapped['document'])!=value:raise ValueError('Lossless text verification failed')
 pathlib.Path(destination).write_text(json.dumps(wrapped,ensure_ascii=False,allow_nan=False)+'\n')
 return wrapped
