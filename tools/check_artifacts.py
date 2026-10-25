# SPDX-License-Identifier: Apache-2.0
"""Check wheel/sdist payloads for private state and accidental generated output."""
import argparse
import re
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def check(path):
    if path.suffix=='.whl':
        with zipfile.ZipFile(path) as archive:
            members=[(info.filename,archive.read(info)) for info in archive.infolist() if not info.is_dir()]
    else:
        with tarfile.open(path,'r:gz') as archive:
            members=[(info.name,archive.extractfile(info).read()) for info in archive.getmembers() if info.isfile()]
    for name,body in members:
        parts=PurePosixPath(name).parts
        if any(part in {'evaluation','research','releases','work','__pycache__','.venv'} for part in parts) or name.endswith(('.jsonl','.db','.log','.pyc')) or PurePosixPath(name).name in {'profile.json','enrollment.json','.env'}:
            raise ValueError('Unexpected private/generated artifact member: '+name)
        if re.search(rb'/Users/[A-Za-z0-9_.-]+/',body):
            raise ValueError('Personal workspace path in artifact: '+name)
    if path.suffix=='.whl':
        for required in ['context_bridge/imports.py','context_bridge/privacy.py','context_bridge/mcp_server.py','context_bridge/__main__.py']:
            if required not in {name for name,_ in members}:
                raise ValueError('Missing runtime module: '+required)
    print(path.name+': payload check passed')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    paths=sorted(args.directory.glob('*.whl'))+sorted(args.directory.glob('*.tar.gz'))
    if not paths:
        parser.error('No wheel or source archive found')
    for path in paths:
        check(path)
