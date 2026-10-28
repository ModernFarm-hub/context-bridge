# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from imports import import_export, import_code, project_preview
from library import remove
from mcp_server import ContextService
from session_manager import Sessions


class ConversationWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.library = self.root / 'library'

    def export(self, bodies):
        mapping = {}
        parent = None
        for i, body in enumerate(bodies):
            mid = str(i)
            mapping[mid] = {'parent':parent, 'message':{'id':mid, 'author':{'role':'user' if i % 2 == 0 else 'assistant'}, 'create_time':1720000000+i, 'content':{'content_type':'text','parts':[body]}}}
            parent = mid
        mapping['inactive'] = {'parent':'0','message':{'id':'inactive','author':{'role':'assistant'},'content':{'content_type':'text','parts':['INACTIVE999']}}}
        # Deliberately reverse mapping insertion order: current-branch order wins.
        conversation = {'id':'window-chat','title':'Window test','current_node':parent,'mapping':dict(reversed(list(mapping.items())))}
        archive = self.root / 'export.zip'
        with zipfile.ZipFile(archive,'w') as out:
            out.writestr('conversations.json',json.dumps([conversation]))
        import_export('chatgpt',archive,self.library)

    def service(self):
        service = ContextService(Sessions(self.library).config)
        self.addCleanup(lambda: service.bridge and service.bridge.db.close())
        return service

    def hit(self, service, query):
        return service.call('context_search',{'query':query})['results'][0]['record_id']

    def read(self, service, rid, **kwargs):
        return service.call('context_read',dict(record_id=rid,**kwargs))['record']

    def test_branch_order_endpoints_and_target_metadata(self):
        self.export(['FIRST842','SECOND842','TARGET842','FOURTH842','LAST842'])
        service = self.service()
        result = self.read(service,self.hit(service,'TARGET842'))
        self.assertEqual([result['body'][m['page_start']:m['page_end']] for m in result['messages']],['FIRST842','SECOND842','TARGET842','FOURTH842','LAST842'])
        self.assertEqual([m['is_target'] for m in result['messages']],[False,False,True,False,False])
        self.assertNotIn('INACTIVE999',json.dumps(result))
        for message in result['messages']:
            for field in ('record_id','role','timestamp'):
                self.assertTrue(message[field])
        self.assertEqual(self.read(service,self.hit(service,'FIRST842'))['message_count'],3)
        self.assertEqual(self.read(service,self.hit(service,'LAST842'))['message_count'],3)
        self.assertEqual(self.read(service,self.hit(service,'TARGET842'),context=0)['body'],'TARGET842')

    def test_maximum_and_invalid_windows(self):
        self.export(['TURN%03d' % i for i in range(30)])
        service = self.service()
        rid = self.hit(service,'TURN015')
        result = self.read(service,rid,context=10)
        self.assertEqual(result['message_count'],21)
        for i in range(5,26):
            self.assertEqual(json.dumps(result).count('TURN%03d' % i),1)
        self.assertTrue(all('body' not in message for message in result['messages']))
        self.assertEqual(result['body'][result['messages'][0]['page_start']:result['messages'][0]['page_end']],'TURN005')
        self.assertEqual(result['body'][result['messages'][-1]['page_start']:result['messages'][-1]['page_end']],'TURN025')
        for value in (-1,11,True,2.5,'2'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.read(service,rid,context=value)

    def test_redacted_neighbors_combined_pagination_and_changed_neighbor(self):
        self.export(['api_key: "sensitive-example-value" '+ 'a'*400,'TARGET842 '+ 'b'*400,'last '+ 'c'*400])
        service = self.service()
        rid = self.hit(service,'TARGET842')
        full = self.read(service,rid,max_chars=12000)
        self.assertNotIn('sensitive-example-value',json.dumps(full))
        page = self.read(service,rid,max_chars=256)
        fingerprint = page['record_sha256']
        pieces = []
        while True:
            pieces.append(page['body'])
            self.assertLessEqual(len(page['body']),256)
            for message in page['messages']:
                if message['in_page']:
                    self.assertEqual(page['body'][message['page_start']:message['page_end']],full['body'][max(page['passage_start'],message['message_start']):min(page['passage_end'],message['message_end'])])
                self.assertNotIn('body',message)
            if not page['has_more']:
                break
            page = self.read(service,rid,start=page['next_start'],max_chars=256,expected_sha256=fingerprint)
        self.assertEqual(''.join(pieces),full['body'])
        self.export(['changed neighbor','TARGET842 '+ 'b'*400,'last '+ 'c'*400])
        with self.assertRaisesRegex(ValueError,'changed'):
            self.read(service,rid,expected_sha256=fingerprint)

    def test_pruned_and_removed_conversations_have_no_window(self):
        self.export(['FIRST842','TARGET842','LAST842'])
        service = self.service()
        rid = self.hit(service,'TARGET842')
        remove(self.library,conversation='window-chat')
        with self.assertRaises(ValueError):
            self.read(service,rid)
        self.export(['FIRST842','TARGET842'])
        rid = self.hit(service,'TARGET842')
        archive = self.root / 'empty.zip'
        with zipfile.ZipFile(archive,'w') as out:
            out.writestr('conversations.json','[]')
        import_export('chatgpt',archive,self.library)
        with self.assertRaises(ValueError):
            self.read(service,rid)

    def test_code_skips_nonindexed_lines_and_revocation(self):
        base = self.root / 'projects'
        project = base / '-Users-test-app'
        project.mkdir(parents=True)
        rows = [
            {'type':'user','message':{'role':'user','content':'FIRST842'}},
            {'type':'user','message':{'role':'user','content':[{'type':'tool_result','content':'TOOL999'}]}},
            {'type':'api-request-blob','message':{'role':'user','content':'BLOB999'}},
            {'type':'assistant','message':{'role':'assistant','content':[{'type':'thinking','thinking':'THINK999'}]}},
            {'type':'system','message':{'role':'system','content':'SYSTEM999'}},
            {'type':'assistant','message':{'role':'assistant','content':'TARGET842'}},
            {'type':'user','message':{'role':'user','content':'LAST842'}}]
        for i,row in enumerate(rows):
            row.update(sessionId='code-session',uuid=str(i))
        (project/'code.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        import_code(project_preview(base),self.library)
        service = self.service()
        rid = self.hit(service,'TARGET842')
        result = self.read(service,rid)
        self.assertEqual([result['body'][m['page_start']:m['page_end']] for m in result['messages']],['FIRST842','TARGET842','LAST842'])
        self.assertEqual([m['line'] for m in result['messages']],[1,6,7])
        remove(self.library,provider='claude-code')
        with self.assertRaises(ValueError):
            self.read(service,rid)

    def test_real_stdio_window_and_path_free_output(self):
        self.export(['FIRST842','TARGET842','LAST842'])
        service = self.service()
        rid = self.hit(service,'TARGET842')
        fingerprint = self.read(service,rid)['record_sha256']
        requests = [
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'context_read','arguments':{'record_id':rid,'context':2}}},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'context_read','arguments':{'record_id':rid,'context':11}}},
            {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'context_read','arguments':{'record_id':rid,'context':2,'start':5,'expected_sha256':fingerprint}}}]
        run = subprocess.run([sys.executable,str(Path(__file__).parents[1]/'mcp_server.py'),'--config',str(Sessions(self.library).config)],input=''.join(json.dumps(r)+'\n' for r in requests),text=True,capture_output=True,timeout=20)
        self.assertEqual(run.returncode,0,run.stderr)
        response = [json.loads(line) for line in run.stdout.splitlines() if json.loads(line).get('id')==2][0]
        self.assertNotIn(str(self.root),json.dumps(response))
        result = json.loads(response['result']['content'][0]['text'])['record']
        self.assertEqual([result['body'][m['page_start']:m['page_end']] for m in result['messages']],['FIRST842','TARGET842','LAST842'])
        self.assertTrue(result['messages'][1]['is_target'])
        for text in ('FIRST842','TARGET842','LAST842'):
            self.assertEqual(json.dumps(response).count(text),1)
        self.assertTrue(all('body' not in message for message in result['messages']))
        self.assertNotIn('INACTIVE999',json.dumps(response))
        responses = {r['id']:r for r in map(json.loads,run.stdout.splitlines())}
        self.assertTrue(responses[3]['result']['isError'])
        page = json.loads(responses[4]['result']['content'][0]['text'])['record']
        self.assertEqual(page['body'],result['body'][5:])
        self.assertEqual(page['record_sha256'],fingerprint)
