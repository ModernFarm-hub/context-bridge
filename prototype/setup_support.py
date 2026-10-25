# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Download a pinned experimental local natural-language-inference model."""
import argparse
import json
from pathlib import Path
import urllib.request
if __package__:
    from .setup_semantic import digest
else:
    from setup_semantic import digest

MODEL = 'cross-encoder/nli-MiniLM2-L6-H768'
REVISION = 'b95119ce93d3e065de6214e38cd4a97b0f2f2c6d'
FILES = {
    'onnx/model.onnx': ('sha256', '807d33fffefd95ad60e2a91f54eed50a92aa53c077945a6842bb587a49a3fdf3'),
    'tokenizer.json': ('git-blob', '8df0092a08e1d459f60ec541e08cd35a16362bfe'),
    'config.json': ('git-blob', 'f3d2c8b047a34c20737866987ba16ea6114c7b53'),
    'README.md': ('git-blob', 'c424f2537691c27718354d28794160ba0c6175ec'),
}


SPECS = {
    'minilm': {'model': MODEL, 'revision': REVISION, 'files': FILES},
    'deberta': {'model': 'cross-encoder/nli-deberta-v3-base',
        'revision': '6c749ce3425cd33b46d187e45b92bbf96ee12ec7',
        'files': {'onnx/model.onnx': ('sha256', '369ebf04fce8206c83b8fd62e9dc860144f10351a7f885ed3076beb17b7c6dda'),
                  'tokenizer.json': ('git-blob', '12cc2e86bad0e731393847b017b32a7405ebd4f8'),
                  'config.json': ('git-blob', 'f421929530a688a116ac1f95911e6aa06bd4820d'),
                  'README.md': ('git-blob', 'c38ae8fb13e12d744661486bf343f99e1c623065')}},
}


def model_spec(root):
    manifest = root / 'manifest.json'
    if not manifest.exists():
        return SPECS['minilm']
    data = json.loads(manifest.read_text())
    for spec in SPECS.values():
        if (data.get('model'), data.get('revision')) == (spec['model'], spec['revision']):
            return spec
    raise ValueError('Unknown or unpinned claim-support model')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', choices=sorted(SPECS), default='minilm')
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    spec = SPECS[args.variant]
    root = args.directory.resolve()
    for name, (kind, expected) in spec['files'].items():
        path = root / name
        data = path.read_bytes() if path.exists() else b''
        if digest(data, kind) != expected:
            print('Downloading ' + name, flush=True)
            with urllib.request.urlopen(f"https://huggingface.co/{spec['model']}/resolve/{spec['revision']}/{name}", timeout=120) as response:
                data = response.read()
            if digest(data, kind) != expected:
                raise ValueError('Support model integrity verification failed')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    (root / 'manifest.json').write_text(json.dumps({'model': spec['model'], 'revision': spec['revision'], 'license': 'Apache-2.0'}, indent=2) + '\n')
    print('Verified local support model: ' + str(root))


if __name__ == '__main__':
    main()
