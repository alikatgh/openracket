"""Strict deterministic source-only framing. No archive links or special entries.

This is deliberately not tar/zip: one exact manifest followed by its regular-file
bytes in order. A decoder admits only this grammar, one XZ stream, exact EOF,
exact closure, hashes, sizes and original modes. No extractall or path rewriting.
"""
from pathlib import Path, PurePosixPath
import hashlib,json,lzma,os,re,stat,struct
MAGIC=b'ORCOCOASOURCE\x00\x01'
MAX_FILES=1200;MAX_FILE=5*1024*1024;MAX_TOTAL=24*1024*1024;MAX_COMPRESSED=12*1024*1024;MAX_MANIFEST=512*1024

def packed(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode('ascii')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def members(manifest):
    rows=manifest['files'];seen=set();casefold=set();total=0
    if not 1<=len(rows)<=MAX_FILES:raise ValueError('Source member count bound')
    for row in rows:
        if set(row)!={'path','bytes','sha256','mode'}:raise ValueError('Unexpected member fields')
        name=row['path'];parts=name.split('/')
        if not name or len(name)>512 or any(not re.fullmatch(r'[A-Za-z0-9_.+@-]{1,128}',x) or x in {'.','..'} or x.endswith('.') for x in parts):raise ValueError('Unsafe source member name')
        if str(PurePosixPath(name))!=name or name in seen or name.casefold() in casefold:raise ValueError('Duplicate/casefold source member')
        if type(row['bytes']) is not int or not 0<=row['bytes']<=MAX_FILE:raise ValueError('Source file size bound')
        if type(row['mode']) is not int or row['mode'] not in (0o444,0o555):raise ValueError('Unexpected source mode')
        if not re.fullmatch(r'[0-9a-f]{64}',row['sha256']):raise ValueError('Source hash encoding')
        seen.add(name);casefold.add(name.casefold());total+=row['bytes']
    if total>MAX_TOTAL:raise ValueError('Source aggregate bound')
    if rows!=sorted(rows,key=lambda r:r['path']):raise ValueError('Source member order')
    return rows

def build(source,manifest,output):
    rows=members(manifest);metadata=packed({'schema':'openracket-source-only-frame/v1','files':rows})
    if len(metadata)>MAX_MANIFEST:raise ValueError('Source manifest bound')
    output=Path(output)
    with output.open('xb') as out:
        encoder=lzma.LZMACompressor(format=lzma.FORMAT_XZ,check=lzma.CHECK_SHA256,preset=6)
        out.write(encoder.compress(MAGIC+struct.pack('>I',len(metadata))+metadata))
        for row in rows:
            path=Path(source)/row['path']
            if path.is_symlink() or not path.is_file():raise ValueError('Only regular source files permitted')
            raw=path.read_bytes()
            if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Source member differs')
            out.write(encoder.compress(raw))
        out.write(encoder.flush());out.flush();os.fsync(out.fileno())
    if output.stat().st_size>MAX_COMPRESSED:raise ValueError('Compressed source bound')
    return {'schema':'openracket-source-only-bundle/v1','format':'ORCOCOASOURCE-v1+xz','sha256':sha(output.read_bytes()),'bytes':output.stat().st_size,'members':len(rows),'raw_file_bytes':sum(r['bytes'] for r in rows)}

def extract(bundle,manifest,pin,destination):
    rows=members(manifest);bundle=Path(bundle);destination=Path(destination)
    if bundle.is_symlink() or not bundle.is_file() or bundle.stat().st_size!=pin['bytes'] or not 0<pin['bytes']<=MAX_COMPRESSED:raise ValueError('Pinned bundle size/type')
    raw=bundle.read_bytes()
    if sha(raw)!=pin['sha256']:raise ValueError('Bundle SHA mismatch')
    decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=64*1024*1024)
    limit=len(MAGIC)+4+MAX_MANIFEST+MAX_TOTAL
    data=decoder.decompress(raw,max_length=limit+1)
    if len(data)>limit or not decoder.eof or decoder.unused_data:raise ValueError('Truncated, concatenated, trailing or oversize source stream')
    if not data.startswith(MAGIC):raise ValueError('Source framing magic')
    offset=len(MAGIC)
    if len(data)<offset+4:raise ValueError('Truncated source header')
    count=struct.unpack('>I',data[offset:offset+4])[0];offset+=4
    if not 0<count<=MAX_MANIFEST:raise ValueError('Source manifest size')
    expected=packed({'schema':'openracket-source-only-frame/v1','files':rows})
    if data[offset:offset+count]!=expected:raise ValueError('Exact source member map/mode mismatch')
    offset+=count
    if len(data)!=offset+sum(r['bytes'] for r in rows):raise ValueError('Source payload closure/size mismatch')
    # Validate all bytes before writing the first member.
    start=offset
    for row in rows:
        end=offset+row['bytes']
        if sha(data[offset:end])!=row['sha256']:raise ValueError('Source payload member hash mismatch')
        offset=end
    if not destination.is_absolute() or destination.parent.resolve(strict=True)!=destination.parent or destination.exists() or destination.is_symlink():raise ValueError('Fresh physical destination required')
    destination.mkdir(mode=0o700);offset=start
    for row in rows:
        path=destination/row['path'];path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        # Fresh mode-exclusive regular files. No archive metadata is executed.
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,row['mode'])
        with os.fdopen(fd,'wb') as out:out.write(data[offset:offset+row['bytes']]);out.flush();os.fsync(out.fileno())
        os.chmod(path,row['mode']);offset+=row['bytes']
    for directory in sorted((p for p in destination.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):directory.chmod(0o555)
    destination.chmod(0o555)
    return {'members':len(rows),'bundle_sha256':pin['sha256'],'source_bytes':sum(r['bytes'] for r in rows),'materialized_readonly':True}

def read_parts(directory,part_map):
    """Strict publication part closure, sizes, order and whole-envelope binding."""
    directory=Path(directory)
    if directory.is_symlink() or directory.resolve(strict=True)!=directory:raise ValueError('Physical source part directory required')
    if set(part_map)!={'schema','bytes','sha256','parts'} or part_map['schema']!='openracket-source-parts/v1':raise ValueError('Part map shape')
    parts=part_map['parts']
    if not isinstance(parts,list) or not 1<=len(parts)<=24:raise ValueError('Part count bound')
    names=[r.get('path') for r in parts]
    if names!=['source-%03d.bin'%i for i in range(len(parts))]:raise ValueError('Parts missing, duplicate or reordered')
    if {p.name for p in directory.iterdir()}!=set(names):raise ValueError('Unexpected/missing source part')
    data=bytearray()
    for index,row in enumerate(parts):
        if set(row)!={'path','bytes','sha256'} or type(row['bytes']) is not int or not 1<=row['bytes']<=512*1024:raise ValueError('Part member shape/size')
        if index<len(parts)-1 and row['bytes']!=512*1024:raise ValueError('Nonfinal source chunk size')
        path=directory/row['path']
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=row['bytes']:raise ValueError('Part type/size mismatch')
        raw=path.read_bytes()
        if sha(raw)!=row['sha256']:raise ValueError('Part SHA mismatch')
        data.extend(raw)
        if len(data)>MAX_COMPRESSED:raise ValueError('Whole part aggregate bound')
    if len(data)!=part_map['bytes'] or sha(data)!=part_map['sha256']:raise ValueError('Whole source envelope mismatch')
    return bytes(data)

def extract_parts(directory,part_map,manifest,pin,destination,spool):
    raw=read_parts(directory,part_map)
    if len(raw)!=pin['bytes'] or sha(raw)!=pin['sha256']:raise ValueError('Part map differs from envelope pin')
    spool=Path(spool)
    if spool.parent.resolve(strict=True)!=spool.parent:raise ValueError('Physical source spool parent required')
    with spool.open('xb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
    return extract(spool,manifest,pin,destination)
