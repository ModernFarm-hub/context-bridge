# SPDX-License-Identifier: Apache-2.0
"""Fill local publication metadata; never uploads or authenticates."""
import argparse
import json
from pathlib import Path
import re


def prepare(root,repository):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+',repository):
        raise ValueError('Supply the intended GitHub owner/repository')
    owner,repo=repository.split('/')
    template=(root/'registry/server.template.json').read_text()
    server=json.loads(template.replace('GITHUB_OWNER',owner).replace('GITHUB_REPO',repo))
    readme=root/'README.md'
    body=re.sub(r'\n?<!-- mcp-name: .*? -->\n?', '\n',readme.read_text())
    body+='\n<!-- mcp-name: '+server['name']+' -->\n'
    body=re.sub(r'(!\[Synthetic import, search and citation demo\])\([^)]*\)', lambda m: m[1]+'(https://raw.githubusercontent.com/'+repository+'/main/docs/assets/demo.gif)', body)
    readme.write_text(body)
    config=root/'pyproject.toml'
    metadata=config.read_text()
    metadata=re.sub(r'\n\[project.urls\][\s\S]*?(?=\n\[|\Z)','',metadata)
    metadata+='\n[project.urls]\nRepository = "https://github.com/'+repository+'"\nIssues = "https://github.com/'+repository+'/issues"\n'
    config.write_text(metadata)
    (root/'server.json').write_text(json.dumps(server,indent=2)+'\n')
    return server['name']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository',help='GitHub owner/repository')
    args=parser.parse_args()
    try:
        print('Prepared '+prepare(Path(__file__).resolve().parents[1],args.repository)+'. No upload performed.')
    except ValueError as exc:
        parser.error(str(exc))
