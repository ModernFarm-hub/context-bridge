# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
import imports
from imports import import_export, import_code, project_preview
from library import remove, main as library_main
from mcp_server import ContextService, TOOLS
from session_manager import Sessions, atomic_write


class IndependentRetestFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.library=self.root/'library'

    def export(self,provider,ids):
        import zipfile
        data=[]
        for cid in ids:
            if provider=='chatgpt':
                data.append({'id':cid,'title':'Title '+cid,'create_time':1792540800,'current_node':'m1','mapping':{'m1':{'parent':None,'message':{'id':'m1','author':{'role':'user'},'content':{'content_type':'text','parts':[cid+' decision']}}}}})
            else:
                data.append({'uuid':cid,'name':'Title '+cid,'created_at':'2026-10-21T10:00:00Z','chat_messages':[{'uuid':'m1','sender':'human','text':cid+' decision'}]})
        path=self.root/(provider+'.zip')
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('conversations.json',json.dumps(data))
        return path

    def service(self):
        service=ContextService(Sessions(self.library).config)
        self.addCleanup(lambda:service.bridge and service.bridge.db.close())
        return service

    def write_code(self,path,cid,body):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'type':'ai-title','aiTitle':'Named '+cid})+'\n'+json.dumps({'type':'user','uuid':cid,'sessionId':cid,'message':{'role':'user','content':body}})+'\n')

    def test_provider_snapshot_removes_absent_conversations_everywhere(self):
        for provider in ['chatgpt','claude']:
            with self.subTest(provider=provider):
                ids=[provider+'KEEP842',provider+'DROP842']
                import_export(provider,self.export(provider,ids),self.library)
                service=self.service()
                hit=service.call('context_search',{'query':ids[1]})['results'][0]
                path=Path(hit['source'])
                result=import_export(provider,self.export(provider,[ids[0]]),self.library)
                self.assertEqual(result['conversations_removed'],1)
                self.assertFalse(path.exists())
                self.assertEqual(service.call('context_search',{'query':ids[1]})['results'],[])
                for table in ['records','source_metadata','record_handles','ingestion_state']:
                    self.assertEqual(service.bridge.db.execute(f'SELECT COUNT(*) FROM {table} WHERE source=?',(str(path),)).fetchone()[0],0)
                self.assertEqual(service.bridge.db.execute(f'SELECT COUNT(*) FROM {service.bridge.fts} WHERE {service.bridge.fts} MATCH ?',('"'+ids[1].lower()+'"',)).fetchone()[0],0)
                with self.assertRaises(ValueError):
                    service.call('context_read',{'record_id':hit['record_id']})
                self.assertTrue(service.call('context_search',{'query':ids[0]})['results'])

    def test_empty_snapshot_removes_only_that_provider(self):
        for provider in ['chatgpt','claude']:
            import_export(provider,self.export(provider,[provider+'842']),self.library)
        result=import_export('chatgpt',self.export('chatgpt',[]),self.library)
        self.assertEqual(result['conversations_removed'],1)
        service=self.service()
        self.assertEqual(service.call('context_search',{'query':'chatgpt842'})['results'],[])
        self.assertTrue(service.call('context_search',{'query':'claude842'})['results'])

    def test_remove_id_link_and_provider_and_original_export_preserved(self):
        archive=self.export('chatgpt',['REMOVE842','LINK842','PROVIDER842'])
        import_export('chatgpt',archive,self.library)
        config=json.loads(Sessions(self.library).config.read_text())
        paths=list(config['sources'])
        self.assertEqual(remove(self.library,conversation='REMOVE842')['conversations_removed'],1)
        self.assertEqual(remove(self.library,conversation='https://chatgpt.com/c/LINK842')['conversations_removed'],1)
        self.assertEqual(remove(self.library,provider='chatgpt')['conversations_removed'],1)
        self.assertTrue(archive.exists())
        self.assertTrue(all(not Path(path).exists() for path in paths))
        config=json.loads(Sessions(self.library).config.read_text())
        self.assertEqual(config['sources'],{})
        self.assertEqual(config['approved_transcripts'],[])

    def test_list_stats_and_remove_cli_report_provider_title_date_counts(self):
        import_export('claude',self.export('claude',['CLAUDE842']),self.library)
        for command in ['list','stats']:
            out=io.StringIO()
            with redirect_stdout(out):
                library_main([command,'--directory',str(self.library)])
            data=json.loads(out.getvalue())
            if command=='list':
                entry=data['conversations'][0]
                self.assertEqual((entry['provider'],entry['title'],entry['date'],entry['message_count']),('claude','Title CLAUDE842','2026-10-21',1))
            else:
                self.assertEqual(data['providers']['claude'],{'conversations':1,'messages':1})
        with redirect_stdout(io.StringIO()) as out:
            library_main(['remove','--conversation','https://claude.ai/chat/CLAUDE842','--directory',str(self.library)])
        self.assertEqual(json.loads(out.getvalue())['conversations_removed'],1)

    def test_import_uses_one_connection_transaction_config_write_and_reports_progress(self):
        Sessions(self.library)
        archive=self.export('chatgpt',[f'BATCH{i}' for i in range(202)])
        real_bridge=imports.Bridge
        statements=[]
        def opened(*args,**kwargs):
            bridge=real_bridge(*args,**kwargs)
            bridge.db.set_trace_callback(statements.append)
            return bridge
        updates=[]
        with patch.object(imports,'Bridge',side_effect=opened) as connection, patch.object(imports,'atomic_write',wraps=atomic_write) as write:
            result=import_export('chatgpt',archive,self.library,progress=lambda current,total:updates.append((current,total)))
        self.assertEqual(connection.call_count,1)
        self.assertEqual(write.call_count,1)
        self.assertEqual(statements.count('COMMIT'),1)
        self.assertEqual(result['conversations_imported'],202)
        self.assertEqual(updates[0],(1,202))
        self.assertEqual(updates[-1],(202,202))
        config=json.loads(Sessions(self.library).config.read_text())
        before={p:os.stat(p).st_mtime_ns for p in config['sources']}
        import_export('chatgpt',archive,self.library)
        self.assertEqual(before,{p:os.stat(p).st_mtime_ns for p in config['sources']})

    def test_warm_refresh_does_not_reread_profile_resolve_paths_or_write_metadata(self):
        import_export('chatgpt',self.export('chatgpt',['CACHE842']),self.library)
        service=self.service()
        service.call('context_search',{'query':'CACHE842'})
        statements=[]
        service.bridge.db.set_trace_callback(statements.append)
        with patch.object(Path,'read_text',side_effect=AssertionError('profile reread')), patch.object(Path,'resolve',side_effect=AssertionError('path re-resolved')), patch.object(service.bridge,'set_source',side_effect=AssertionError('metadata rewritten')):
            self.assertTrue(service.call('context_search',{'query':'CACHE842'})['results'])
        self.assertFalse(any(sql.startswith('INSERT') or sql.startswith('UPDATE') for sql in statements))
        self.assertLessEqual(statements.count('COMMIT'),1)

    def test_changed_metadata_is_written_once_and_revocation_invalidates_cache(self):
        import_export('claude',self.export('claude',['META842']),self.library)
        service=self.service()
        hit=service.call('context_search',{'query':'META842'})['results'][0]
        data=json.loads(service.config.read_text())
        data['sources'][hit['source']]['title']='Updated title'
        atomic_write(service.config,data)
        statements=[]
        service.bridge.db.set_trace_callback(statements.append)
        updated=service.call('context_search',{'query':'META842'})['results'][0]
        self.assertIn('Updated title',updated['source_label'])
        self.assertEqual(sum(sql.startswith('INSERT OR REPLACE INTO source_metadata') for sql in statements),1)
        old_info=service.config.stat()
        data['approved_transcripts']=[]
        atomic_write(service.config,data)
        os.utime(service.config,ns=(old_info.st_atime_ns,old_info.st_mtime_ns))
        self.assertEqual(service.call('context_search',{'query':'META842'})['results'],[])

    def test_multiple_changed_files_refresh_in_one_transaction(self):
        import_export('claude',self.export('claude',['APPEND1','APPEND2']),self.library)
        service=self.service()
        service.call('context_search',{'query':'decision'})
        data=json.loads(service.config.read_text())
        for i,path in enumerate(data['approved_transcripts']):
            with Path(path).open('a') as stream:
                stream.write(json.dumps({'type':'user','uuid':'fresh','sessionId':str(i),'message':{'role':'user','content':'NEWFRESH842'}})+'\n')
        statements=[]
        service.bridge.db.set_trace_callback(statements.append)
        self.assertEqual(len(service.call('context_search',{'query':'NEWFRESH842'})['results']),2)
        self.assertEqual(statements.count('COMMIT'),1)

    def test_new_sessions_discovered_only_inside_approved_project(self):
        projects=self.root/'projects'
        self.write_code(projects/'approved/subagents/first.jsonl','first','FIRST842 finding')
        self.write_code(projects/'unapproved/hidden.jsonl','hidden','HIDDEN842 finding')
        preview=project_preview(projects)
        del preview['unapproved']
        import_code(preview,self.library)
        service=self.service()
        service.call('context_search',{'query':'FIRST842'})
        self.write_code(projects/'approved/new.jsonl','new','NEWSESSION842 finding')
        self.assertTrue(service.call('context_search',{'query':'NEWSESSION842'})['results'])
        self.assertEqual(service.call('context_search',{'query':'HIDDEN842'})['results'],[])
        data=json.loads(service.config.read_text())
        self.assertEqual(len(data['sources']),2)

    def test_remove_code_keeps_original_and_prevents_rediscovery(self):
        project=self.root/'projects/approved'
        self.write_code(project/'first.jsonl','first','FIRST842 finding')
        import_code(project_preview(project.parent),self.library)
        service=self.service()
        self.assertTrue(service.call('context_search',{'query':'FIRST842'})['results'])
        remove(self.library,conversation='first')
        self.assertTrue((project/'first.jsonl').exists())
        self.assertEqual(service.call('context_search',{'query':'FIRST842'})['results'],[])
        remove(self.library,provider='claude-code')
        self.write_code(project/'new.jsonl','new','AFTERREMOVE842 finding')
        self.assertEqual(service.call('context_search',{'query':'AFTERREMOVE842'})['results'],[])

    def test_mcp_descriptions_name_providers_and_citation_fields(self):
        for tool in TOOLS:
            description=tool['description'].casefold()
            for phrase in ['chatgpt','claude','claude code','source_label','record_id','cite the link']:
                self.assertIn(phrase,description)

    def test_readme_upgrades_pip_before_source_install(self):
        readme=(Path(__file__).parents[2]/'README.md').read_text()
        self.assertIn('Python 3.9',readme)
        self.assertLess(readme.index('pip install -U pip'),readme.index('pip install .'))

    def test_provider_link_cannot_remove_another_provider_with_same_id(self):
        project=self.root/'projects/approved'
        self.write_code(project/'first.jsonl','first','FIRST842 finding')
        import_code(project_preview(project.parent),self.library)
        result=remove(self.library,conversation='https://chatgpt.com/c/first')
        self.assertEqual(result['conversations_removed'],0)
        self.assertTrue(self.service().call('context_search',{'query':'FIRST842'})['results'])

    def test_malformed_unidentified_export_does_not_prune_existing_data(self):
        import zipfile
        archive=self.export('chatgpt',['KEEP842'])
        import_export('chatgpt',archive,self.library)
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('conversations.json',json.dumps([{'title':'no id'}]))
        result=import_export('chatgpt',archive,self.library)
        self.assertTrue(result['pruning_skipped'])
        self.assertEqual(result['conversations_removed'],0)
        self.assertTrue(self.service().call('context_search',{'query':'KEEP842'})['results'])

    def test_existing_managed_copies_and_titles_receive_redaction_upgrade(self):
        import_export('chatgpt',self.export('chatgpt',['UPGRADE842']),self.library)
        manager=Sessions(self.library)
        data=json.loads(manager.config.read_text())
        source=next(iter(data['sources']))
        path=Path(source)
        record=json.loads(path.read_text())
        record['message']['content']='UPGRADE842 sk_live_'+'a'*24
        path.write_text(json.dumps(record)+'\n')
        data['sources'][source]['title']='api_key: oldTitleSecret842'
        data['redaction_version']=1
        atomic_write(manager.config,data)
        service=self.service()
        hit=service.call('context_search',{'query':'UPGRADE842'})['results'][0]
        self.assertNotIn('sk_live_',hit['body'])
        self.assertNotIn('sk_live_',path.read_text())
        self.assertNotIn('oldTitleSecret842',manager.config.read_text())
        from privacy import REDACTION_VERSION
        self.assertEqual(json.loads(manager.config.read_text())['redaction_version'],REDACTION_VERSION)
