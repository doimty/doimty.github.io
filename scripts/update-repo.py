#!/usr/bin/env python3
import hashlib, os, pathlib, subprocess, tarfile, io, lzma, gzip, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
DEBS = ROOT / 'debs'
PKG = ROOT / 'Packages'

def ar_members(data: bytes):
    if not data.startswith(b'!<arch>\n'):
        return
    pos = 8
    while pos + 60 <= len(data):
        header = data[pos:pos+60]
        name = header[:16].rstrip(b' ').rstrip(b'/').decode('utf-8', 'replace')
        size = int(header[48:58].strip() or b'0')
        pos += 60
        content = data[pos:pos+size]
        yield name, content
        pos += size + (size % 2)

def control_from_deb(path: pathlib.Path) -> str:
    data = path.read_bytes()
    for name, content in ar_members(data) or []:
        if name.startswith('control.tar'):
            with tarfile.open(fileobj=io.BytesIO(content)) as tf:
                for member in ('./control', 'control'):
                    try:
                        f = tf.extractfile(member)
                    except KeyError:
                        f = None
                    if f:
                        return f.read().decode('utf-8', 'replace')
    raise RuntimeError(f'cannot read control: {path}')

def digest(data: bytes, name: str) -> str:
    h = getattr(hashlib, name)(); h.update(data); return h.hexdigest()

entries = []
for deb in sorted(DEBS.glob('*.deb')):
    data = deb.read_bytes()
    control = control_from_deb(deb).rstrip('\n')
    rel = deb.relative_to(ROOT).as_posix()
    entry = control + '\n'
    entry += f'Filename: {rel}\n'
    entry += f'Size: {len(data)}\n'
    entry += f'MD5sum: {digest(data, "md5")}\n'
    entry += f'SHA1: {digest(data, "sha1")}\n'
    entry += f'SHA256: {digest(data, "sha256")}\n\n'
    entries.append(entry)
PKG.write_text(''.join(entries), encoding='utf-8')
raw = PKG.read_bytes()
(ROOT / 'Packages.gz').write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
(ROOT / 'Packages.xz').write_bytes(lzma.compress(raw, preset=9, format=lzma.FORMAT_XZ))
(ROOT / 'Packages.lzma').write_bytes(lzma.compress(raw, preset=9, format=lzma.FORMAT_ALONE))

def h(path: pathlib.Path, algo: str) -> str:
    return digest(path.read_bytes(), algo)
def sz(path: pathlib.Path) -> int:
    return path.stat().st_size
files = ['Packages', 'Packages.gz', 'Packages.xz', 'Packages.lzma']
date = time.strftime('%a, %d %b %Y %H:%M:%S +0800', time.gmtime(time.time()+8*3600))
release = f'''Origin: Doimty Repo\nLabel: Doimty Repo\nSuite: stable\nVersion: 1.0\nCodename: ios\nArchitectures: iphoneos-arm64 iphoneos-arm64e\nComponents: main\nDescription: Doimty Repo jailbreak packages\nDate: {date}\nNotAutomatic: No\n\n'''
for algo, title in [('md5','MD5Sum'),('sha1','SHA1'),('sha256','SHA256')]:
    release += title + ':\n'
    for f in files:
        p = ROOT / f
        release += f' {h(p, algo)} {sz(p)} {f}\n'
(ROOT / 'Release').write_text(release, encoding='utf-8')
print(f'Updated repo: {len(entries)} packages')
