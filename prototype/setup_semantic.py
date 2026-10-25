# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Download a pinned public embedding model; no conversation data is transmitted."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
FILES = {'onnx/model.onnx': ('sha256', '6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452'), 'tokenizer.json': ('git-blob', 'cb202bfe2e3c98645018a6d12f182a434c9d3e02'), 'README.md': ('git-blob', '44af2e3b0fa3a0b6239e48422972bf755f28fde0')}
SPECS = {
    'minilm': {'model': MODEL, 'revision': REVISION, 'files': FILES,
               'pooling': 'mean', 'max_length': 256, 'query_prefix': '', 'license': 'Apache-2.0'},
    'e5-small': {'model': 'intfloat/e5-small-v2',
        'revision': 'ffb93f3bd4047442299a41ebb6fa998a38507c52',
        'files': {'model.onnx': ('sha256', '4b8205be2a3c5fc53c6534d76a2012064f7309c162b806f2889c6ec8ec4fdcba'),
                  'tokenizer.json': ('git-blob', '688882a79f44442ddc1f60d70334a7ff5df0fb47'),
                  'README.md': ('git-blob', '416b071ab6645aaca3e8df01132b196ce8aff17a')},
        'graph': 'model.onnx', 'pooling': 'mean', 'max_length': 512,
        'query_prefix': 'query: ', 'passage_prefix': 'passage: ', 'license': 'MIT'},
    'bge-small': {'model': 'BAAI/bge-small-en-v1.5',
        'revision': '5c38ec7c405ec4b44b94cc5a9bb96e735b38267a',
        'files': {'onnx/model.onnx': ('sha256', '828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35'),
                  'tokenizer.json': ('git-blob', '688882a79f44442ddc1f60d70334a7ff5df0fb47'),
                  'README.md': ('git-blob', '8b8567d75ffa619486d9590cb0eb76d66ad46c49')},
        'pooling': 'cls', 'max_length': 512,
        'query_prefix': 'Represent this sentence for searching relevant passages: ', 'license': 'MIT'},
}


def model_spec(root):
    manifest = root / 'manifest.json'
    if not manifest.exists():
        return SPECS['minilm']  # legacy directories still undergo pinned hash checks
    data = json.loads(manifest.read_text())
    for spec in SPECS.values():
        if (data.get('model'), data.get('revision')) == (spec['model'], spec['revision']):
            return spec
    raise ValueError('Unknown or unpinned embedding model')


if __package__:
    from .paths import data_home
else:
    from paths import data_home

DEFAULT_MODEL = data_home() / 'models' / 'all-MiniLM-L6-v2'


def digest(data, kind):
    if kind == 'sha256':
        return hashlib.sha256(data).hexdigest()
    return hashlib.sha1(('blob %d\0' % len(data)).encode() + data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=sorted(SPECS), default='minilm')
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    spec = SPECS[args.model]
    root = (args.directory or (data_home() / 'models' / spec['model'].split('/')[-1])).resolve()
    root.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, (kind, expected) in spec['files'].items():
        path = root / name
        data = path.read_bytes() if path.exists() else b''
        if digest(data, kind) != expected:
            url = 'https://huggingface.co/' + spec['model'] + '/resolve/' + spec['revision'] + '/' + name
            print('Downloading ' + name, flush=True)
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read()
            if digest(data, kind) != expected:
                raise SystemExit('Integrity verification failed for ' + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    (root / 'manifest.json').write_text(json.dumps({'model': spec['model'], 'revision': spec['revision'], 'license': spec['license'], 'sha256': hashes}, indent=2) + '\n')
    print('Verified local model at ' + str(root))


if __name__ == '__main__':
    main()
