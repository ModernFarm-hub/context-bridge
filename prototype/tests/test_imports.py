# SPDX-License-Identifier: Apache-2.0
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from imports import import_export, import_code, project_preview, chatgpt_messages
from mcp_server import ContextService, public_result, serve
from session_manager import Sessions


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.library = self.root / 'library'

    def archive(self, conversations):
        path = self.root / 'export.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('nested/conversations.json', json.dumps(conversations))
        return path

    def service(self):
        service = ContextService(Sessions(self.library).config)
        self.addCleanup(lambda: service.bridge and service.bridge.db.close())
        return service

    def conversation(self):
        def node(mid, parent, body, role='user'):
            return {'parent': parent, 'message': {'id':mid, 'author':{'role':role}, 'content':{'content_type':'text','parts':[body]}, 'create_time':1720000000}}
        return {'id':'chat-123', 'title':'Kafka retry design', 'create_time':1720000000, 'current_node':'chosen', 'mapping':{
            'root':node('a', None, 'Kafka retries use exponential backoff'),
            'chosen':node('b', 'root', 'SELECTED842 approved retry', 'assistant'),
            'sibling':node('c', 'root', 'DISCARDED999 do not index'),
        }}

    def test_chatgpt_current_branch_metadata_citations_idempotence_and_stable_handles(self):
        conversation = self.conversation()
        archive = self.archive([conversation])
        self.assertEqual(import_export('chatgpt', archive, self.library)['messages_imported'], 2)
        service = self.service()
        hit = service.call('context_search', {'query':'SELECTED842'})['results'][0]
        self.assertEqual(hit['link'], 'https://chatgpt.com/c/chat-123')
        self.assertIn("ChatGPT · 'Kafka retry design'", hit['source_label'])
        self.assertEqual(service.call('context_search', {'query':'DISCARDED999'})['results'], [])
        import_export('chatgpt', archive, self.library)
        self.assertEqual(service.call('context_search', {'query':'SELECTED842'})['results'][0]['record_id'], hit['record_id'])
        # Removing an earlier message moves the retained message to another line.
        conversation['mapping']['root']['message'] = None
        import_export('chatgpt', self.archive([conversation]), self.library)
        record = service.call('context_read', {'record_id':hit['record_id']})['record']
        self.assertIn('SELECTED842', record['body'])
        self.assertEqual(record['record_id'], hit['record_id'])
        self.assertEqual(service.bridge.db.execute('SELECT COUNT(*) FROM records').fetchone()[0], 1)

    def test_claude_text_blocks_only_and_real_link(self):
        archive = self.archive([{'uuid':'claude-123', 'name':'Retention policy', 'created_at':'2026-10-21T10:00:00Z', 'chat_messages':[
            {'uuid':'m1', 'sender':'human', 'text':'RETENTION842 is 45 days'},
            {'uuid':'m2', 'sender':'assistant', 'content':[{'type':'thinking','text':'PRIVATE999'}, {'type':'tool_use','text':'TOOL999'}, {'type':'text','text':'RETENTION842 acknowledged'}]},
        ]}])
        self.assertEqual(import_export('claude', archive, self.library)['messages_imported'], 2)
        service = self.service()
        hit = service.call('context_search', {'query':'RETENTION842'})['results'][0]
        self.assertEqual(hit['link'], 'https://claude.ai/chat/claude-123')
        self.assertIn('2026-10-21', hit['source_label'])
        self.assertEqual(service.call('context_search', {'query':'PRIVATE999 TOOL999'})['results'], [])

    def test_code_preview_opt_in_title_and_manager_rebuild_preserves_import(self):
        base = self.root / 'projects'
        project = base / 'example-project'
        project.mkdir(parents=True)
        path = project / 'session.jsonl'
        path.write_text(json.dumps({'type':'ai-title','aiTitle':'Deployment planning'})+'\n'+json.dumps({'type':'user','uuid':'m1','sessionId':'session1','message':{'role':'user','content':'DEPLOY842 Maya approves'}})+'\n')
        preview = project_preview(base)
        self.assertEqual(list(preview), ['example-project'])
        self.assertFalse(self.library.exists())
        run = subprocess.run([sys.executable, str(Path(__file__).parents[1]/'imports.py'), 'claude-code', '--projects-root', str(base), '--directory', str(self.library)], input='', text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('Preview only', run.stdout)
        self.assertFalse(self.library.exists())
        import_code(preview, self.library)
        manager = Sessions(self.library)
        manager.create('Another session')
        hit = self.service().call('context_search', {'query':'DEPLOY842'})['results'][0]
        self.assertIn('Deployment planning', hit['source_label'])
        self.assertTrue(hit['link'].startswith('urn:context-bridge:record:'))

    def test_wire_has_no_filesystem_locators_and_accepts_only_handles(self):
        import_export('chatgpt', self.archive([self.conversation()]), self.library)
        service = self.service()
        result = public_result(service.call('context_search', {'query':'SELECTED842'}))
        serialized = json.dumps(result)
        self.assertNotIn(str(self.root), serialized)
        hit = result['results'][0]
        requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}}, {'jsonrpc':'2.0','method':'notifications/initialized'}, {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'context_read','arguments':{'record_id':hit['record_id']}}}]
        output = io.StringIO()
        serve(service, io.StringIO(''.join(json.dumps(r)+'\n' for r in requests)), output)
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertFalse(json.loads(output.getvalue().splitlines()[-1])['result']['isError'])

    def test_invalid_exports_and_cyclic_branch_are_actionable(self):
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            conversation = self.conversation()
            conversation['mapping']['root']['parent'] = 'chosen'
            chatgpt_messages(conversation)
        path = self.root/'bad.zip'
        path.write_text('not a zip')
        with self.assertRaisesRegex(ValueError, 'Invalid export'):
            import_export('chatgpt', path, self.library)
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('elsewhere.json', '[]')
        with self.assertRaisesRegex(ValueError, 'conversations.json'):
            import_export('claude', path, self.library)

    def test_removed_message_handle_cannot_read_replacement_at_same_line(self):
        conversation = self.conversation()
        import_export('chatgpt', self.archive([conversation]), self.library)
        service = self.service()
        old = service.call('context_search', {'query':'SELECTED842'})['results'][0]
        conversation['mapping']['chosen']['message']['id'] = 'new-message'
        conversation['mapping']['chosen']['message']['content']['parts'] = ['REPLACEMENT842 new fact']
        import_export('chatgpt', self.archive([conversation]), self.library)
        with self.assertRaisesRegex(ValueError, 'removed or changed'):
            service.call('context_read', {'record_id':old['record_id']})
        new = service.call('context_search', {'query':'REPLACEMENT842'})['results'][0]
        self.assertNotEqual(old['record_id'], new['record_id'])

    def test_default_mcp_starts_without_reader_config(self):
        import os
        run = subprocess.run([sys.executable, str(Path(__file__).parents[1]/'mcp_server.py')], env={**os.environ, 'CONTEXT_BRIDGE_HOME':str(self.root/'default')}, input=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})+'\n', text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('protocolVersion', run.stdout)
