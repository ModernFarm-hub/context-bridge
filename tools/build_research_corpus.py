# SPDX-License-Identifier: Apache-2.0
"""Rebuild the public corpus from two locally supplied official source archives."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ARCHIVES={'3.13.1':'1513925a9f255ef0793dbf2f78bb4533c9f184bdd0ad19763fd7f47a400a7c55','3.14.0':'88d2da4eed42fa9a5f42ff58a8bc8988881bd6c547e297e46682c2687638a851'}
CHANGED={'argparse.rst','concurrent.futures.rst','pathlib.rst','functools.rst','multiprocessing.rst','os.rst','threading.rst','uuid.rst','heapq.rst','annotationlib.rst'}
EXCLUDED={'tutorial/venv.rst','whatsnew/3.2.rst','library/shutil.rst','library/sysconfig.rst'}
DESCRIPTION='v2 overlays ten Python 3.14 module documents on the frozen 3.13.1 corpus; version refers to each document, not a runnable Python distribution. No invented facts.'

def build(archives,root):
    root=Path(root);manifest=[]
    for archive,(release,expected) in zip(archives,ARCHIVES.items()):
        if hashlib.sha256(Path(archive).read_bytes()).hexdigest()!=expected:raise ValueError('Archive SHA-256 mismatch: '+release)
    for archive,release in zip(archives,ARCHIVES):
        version='v1' if release=='3.13.1' else 'v2'
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                prefix='Python-'+release+'/Doc/'
                if not member.isfile() or not member.name.startswith(prefix) or not member.name.endswith('.rst'):continue
                relative=member.name[len(prefix):]
                if '..' in Path(relative).parts or Path(relative).is_absolute():raise ValueError('Unsafe archive member')
                # Omit four unrelated docs whose upstream example user paths trip
                # the package's unchanged private-state payload scanner.
                if relative in EXCLUDED:continue
                if version=='v2' and Path(relative).name not in CHANGED:continue
                path=root/'corpus'/version/relative;path.parent.mkdir(parents=True,exist_ok=True)
                data=tar.extractfile(member).read();path.write_bytes(data)
                manifest.append({'path':str(path.relative_to(root)),'version':release,'source_url':'https://github.com/python/cpython/blob/v'+release+'/Doc/'+relative,'license':'PSF-2.0','license_file':'licenses/Python-'+release+'.txt','sha256':hashlib.sha256(data).hexdigest()})
            path=root/'licenses'/('Python-'+release+'.txt');path.parent.mkdir(exist_ok=True);path.write_bytes(tar.extractfile('Python-'+release+'/LICENSE').read())
    (root/'manifest.json').write_text(json.dumps({'v2_fallback':'v1','description':DESCRIPTION,'files':manifest},indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('archives',nargs=2,type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();build(args.archives,args.output)
