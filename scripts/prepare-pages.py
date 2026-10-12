#!/usr/bin/env python3
"""Prepare only approved public APT assets; fail closed on source provenance."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PUBLIC_ARCHIVES = {
    'letmeblock-1.3.0-2.tar.gz': ('doimty/LetMeBlock', 'cb758751c83c76dbc438e3a81a4d9e6d68b89f2ab310e155688d2ff65c3c6908'),
    'vedette-1.1.12-2.tar.gz': ('doimty/vedette', 'ed7f51f125bef65721e41d2ba4fbcaa478bb0130ebd1746249699c56b200195a'),
    'vedette-1.1.12-3.tar.gz': ('doimty/vedette', 'a4251b45b9e5527eb369224a816dd5c8cbd95f4d839a26f0b738c2ed6073229f'),
}
ROOT_ASSETS = frozenset(('.nojekyll', 'Categories', 'CydiaIcon.png', 'Packages', 'Packages.gz', 'Packages.lzma', 'Packages.xz', 'Release', 'index.html'))
METADATA = frozenset(('.gitignore', 'README.md'))

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.repos = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key not in ('href', 'src') or not value:
                continue
            url = urlparse(value)
            if url.hostname == 'github.com':
                parts = url.path.strip('/').split('/')
                if len(parts) >= 2 and all(re.fullmatch(r'[A-Za-z0-9_.-]+', p) for p in parts[:2]):
                    self.repos.add('/'.join(parts[:2]))


def github_public(repo):
    # Anonymous API access is deliberate: private repositories must not pass.
    req = Request('https://api.github.com/repos/' + repo, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'doimty-pages-source-privacy',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    with urlopen(req, timeout=30) as response:
        data = json.load(response)
    return (data.get('private') is False and data.get('visibility') == 'public'
            and data.get('full_name', '').casefold() == repo.casefold())


def stage(root, output, lookup=github_public):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or root.is_relative_to(output):
        raise ValueError('output must not contain the source tree')
    if output.exists():
        raise ValueError('output must be new to prevent stale artifacts')
    files, sources, repositories = [], set(), set()
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if rel.parts[0] in ('.git', '__pycache__') or '__pycache__' in rel.parts:
            continue
        if path.is_symlink():
            raise ValueError('symlink rejected: ' + str(rel))
        if path.is_dir():
            continue
        name, top = str(rel), rel.parts[0]
        site = False
        if name in ROOT_ASSETS:
            site = True
        elif name in METADATA:
            continue
        elif top == '.github' and rel.parent.as_posix() == '.github/workflows' and path.suffix == '.yml':
            continue
        elif top == 'scripts' and len(rel.parts) == 2 and path.suffix in ('.py', '.sh'):
            continue
        elif top == 'debs' and len(rel.parts) == 2 and path.suffix == '.deb':
            site = True
        elif top == 'icons' and len(rel.parts) == 2 and path.suffix == '.png':
            site = True
        elif top == 'depictions' and path.suffix in ('.html', '.json', '.css', '.js', '.png', '.jpg', '.jpeg', '.webp'):
            site = True
        elif top == 'sources' and len(rel.parts) == 2 and path.name in PUBLIC_ARCHIVES:
            repo, expected = PUBLIC_ARCHIVES[path.name]
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError('source archive hash mismatch: ' + str(rel))
            sources.add(path.name)
            repositories.add(repo)
            site = True
        else:
            raise ValueError('unapproved repository file: ' + str(rel))
        if site:
            files.append(rel)
            if path.suffix == '.html':
                links = Links()
                links.feed(path.read_text(encoding='utf-8'))
                repositories.update(links.repos)
    if sources != set(PUBLIC_ARCHIVES):
        raise ValueError('public source archive inventory mismatch')
    if not ROOT_ASSETS.issubset({str(p) for p in files}):
        raise ValueError('required APT site asset missing')
    for repo in sorted(repositories):
        if lookup(repo) is not True:
            raise ValueError('source/link repository is not verifiably public: ' + repo)
    output.mkdir(parents=True)
    for rel in files:
        destination = output / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / rel, destination)
    return {'files': len(files), 'public_repositories': sorted(repositories), 'public_source_archives': sorted(sources)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.root, args.output), ensure_ascii=False, indent=2))
