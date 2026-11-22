# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from mcp_server import ContextService

class EmptyApprovalTests(unittest.TestCase):
    def test_empty_existing_folders_are_approved_for_future_threads(self):
        for provider in ('codex','claude-code'):
            with self.subTest(provider=provider),tempfile.TemporaryDirectory() as directory:
                root=Path(directory).resolve();project=root/'my_empty-project';project.mkdir()
                state=root/'provider';state.mkdir();library=root/'library'
                command=[sys.executable,str(Path(__file__).parents[1]/'imports.py'),provider,'--path',str(project),'--yes','--directory',str(library)]
                command+=['--codex-home' if provider=='codex' else '--projects-root',str(state)]
                env={**os.environ,'HOME':str(root),'CODEX_HOME':str(state)}
                result=subprocess.run(command,capture_output=True,text=True,env=env)
                self.assertEqual(result.returncode,0,result.stderr)
                data=json.loads((library/'profile.json').read_text())
                entries=data['approved_codex_projects' if provider=='codex' else 'approved_projects']
                self.assertEqual(len(entries),1)
                if provider=='codex':self.assertEqual(entries[0]['path'],str(project))
                else:self.assertEqual(Path(entries[0]['path']).parent,state)
                self.assertEqual(data['approved_transcripts'],[])
                if provider=='codex':
                    folder=state/'sessions';folder.mkdir()
                    transcript=folder/'rollout-first.jsonl'
                    rows=[{'type':'session_meta','payload':{'id':'first'}},{'type':'turn_context','payload':{'cwd':str(project)}},{'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'FIRST_CAPTURE_472'}]}}]
                else:
                    folder=Path(entries[0]['path']);folder.mkdir(parents=True)
                    transcript=folder/'first.jsonl'
                    rows=[{'type':'user','sessionId':'first','uuid':'q','cwd':str(project),'message':{'role':'user','content':'FIRST_CAPTURE_472'}}]
                transcript.write_text(''.join(json.dumps(r)+'\n' for r in rows))
                service=ContextService(library/'profile.json')
                try:self.assertTrue(service.call('context_search',{'query':'FIRST_CAPTURE_472'},log=False)['results'])
                finally:
                    if service.bridge:service.bridge.db.close()
                # A nonexistent original folder must never be pre-approved.
                command[command.index(str(project))]=str(root/'missing')
                rejected=subprocess.run(command,capture_output=True,text=True,env=env)
                self.assertNotEqual(rejected.returncode,0)
