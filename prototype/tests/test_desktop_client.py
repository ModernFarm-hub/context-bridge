# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from imports import import_export
from session_manager import Sessions


class DesktopClientTests(unittest.TestCase):
    def test_single_string_arguments_report_actionable_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'context_bridge').symlink_to(Path(__file__).parents[1].resolve(),target_is_directory=True)
            env = {**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'}
            for command in ('mcp --profile personal','import chatgpt export.zip','exclusions list'):
                with self.subTest(command=command):
                    run = subprocess.run([sys.executable,'-m','context_bridge',command],env=env,cwd=root,text=True,capture_output=True,timeout=10)
                    self.assertNotEqual(run.returncode,0)
                    self.assertEqual(run.stdout,'')
                    self.assertEqual(run.stderr.strip(),'Arguments were passed as one string. Use separate arguments: '+command)
                    self.assertNotIn('Unknown command',run.stderr)
            run = subprocess.run([sys.executable,'-m','context_bridge','unrecognized command'],env=env,cwd=root,text=True,capture_output=True,timeout=10)
            self.assertNotEqual(run.returncode,0)
            self.assertIn('Unknown command',run.stderr)

    def test_real_stdio_search_has_readable_source_links_and_unchanged_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = root/'library'
            archive = root/'export.zip'
            conversations = [{'id':cid,'title':'History '+cid,'create_time':1720000000,'current_node':'m','mapping':{'m':{'parent':None,'message':{'id':'m','author':{'role':'user'},'content':{'content_type':'text','parts':['DESKTOP842 finding '+cid]}}}}} for cid in ('first','second')]
            with zipfile.ZipFile(archive,'w') as out:
                out.writestr('conversations.json',json.dumps(conversations))
            import_export('chatgpt',archive,library)
            requests = [
                {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'context_search','arguments':{'query':'DESKTOP842'}}},
                {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'context_search','arguments':{'query':'NOTFOUND999'}}}]
            run = subprocess.run([sys.executable,str(Path(__file__).parents[1]/'mcp_server.py'),'--config',str(Sessions(library).config)],input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,timeout=10)
            self.assertEqual(run.returncode,0,run.stderr)
            replies = {r['id']:r for r in map(json.loads,run.stdout.splitlines())}
            content = replies[2]['result']['content']
            data = json.loads(content[0]['text'])
            self.assertEqual(len(data['results']),2)
            self.assertEqual(len(content),3)
            for hit, block in zip(data['results'],content[1:]):
                self.assertEqual(block,{'type':'text','text':'Source: '+hit['source_label']+' — '+hit['link']})
                self.assertTrue(hit['record_id'])
                self.assertTrue(hit['link'].startswith('https://chatgpt.com/c/'))
                self.assertNotIn('\n',block['text'])
            self.assertNotIn(str(root),json.dumps(replies[2]))
            self.assertEqual(len(replies[3]['result']['content']),1)
            self.assertEqual(json.loads(replies[3]['result']['content'][0]['text'])['results'],[])
