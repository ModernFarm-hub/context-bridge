# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest.mock import patch
from accounts import AccountMismatch
from imports import import_export, code_metadata
from local_profile import profile_directory
from session_manager import Sessions


class ProjectAccountFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.base=self.root/'library'
        self.projects=self.root/'projects'
        self.code=Path(__file__).parents[1]
        self.launch_root=self.root/'source'
        self.launch_root.mkdir()
        (self.launch_root/'context_bridge').symlink_to(self.code.resolve(),target_is_directory=True)
        self.cwd=str(Path('/')/'Users'/'alice'/'code'/'my-app')
        self.project='-Users-alice-code-my-app'
        self.write_session(self.projects/self.project/'one.jsonl','FIRST842 approve deployment')
        self.write_session(self.projects/'-Users-alice-code-other'/'two.jsonl','OTHER842 hidden')

    def write_session(self,path,body):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'type':'user','uuid':'m1','sessionId':path.stem,'cwd':self.cwd,'message':{'role':'user','content':body}})+'\n')

    def cli(self,*args,input=''):
        # Exercise the real package command dispatcher, not imports.main mocks.
        env={**os.environ,'PYTHONPATH':str(self.launch_root),'PYTHONDONTWRITEBYTECODE':'1'}
        command=[sys.executable,'-m','context_bridge',*args]
        return subprocess.run(command,env=env,input=input,capture_output=True,text=True,cwd=self.root)

    def account_zip(self,path,cid,user=None,email=None,provider='chatgpt'):
        if provider=='chatgpt':
            conversations=[{'id':cid,'title':cid,'current_node':'m1','mapping':{'m1':{'parent':None,'message':{'id':'m1','author':{'role':'user'},'content':{'content_type':'text','parts':[cid+' finding']}}}}}]
        else:
            conversations=[{'uuid':cid,'name':cid,'chat_messages':[{'uuid':'m1','sender':'human','text':cid+' finding'}]}]
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('conversations.json',json.dumps(conversations))
            if user:
                archive.writestr('user.json',json.dumps({'id':user,'email':email or user+'@example.test'}))
        return path

    def test_dash_prefixed_project_works_through_real_cli(self):
        result=self.cli('import','claude-code','--projects-root',str(self.projects),'--directory',str(self.base),'--project',self.project,'--yes')
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(Sessions(self.base).config.read_text())
        self.assertEqual(len(data['sources']),1)
        self.assertEqual(next(iter(data['sources'].values()))['title'],'my-app · FIRST842 approve deployment')

    def test_numeric_and_decoded_path_selection_use_real_cli(self):
        for option,value in [('--select','1'),('--path',self.cwd)]:
            # Both fixtures use the same cwd; give the unrelated fixture its own.
            other=self.projects/'-Users-alice-code-other'/'two.jsonl'
            record=json.loads(other.read_text());record['cwd']=str(Path('/')/'Users'/'alice'/'code'/'other');other.write_text(json.dumps(record)+'\n')
            directory=self.root/option[2:]
            result=self.cli('import','claude-code','--projects-root',str(self.projects),'--directory',str(directory),option,value,'--yes')
            self.assertEqual(result.returncode,0,result.stderr)
            data=json.loads(Sessions(directory).config.read_text())
            self.assertEqual(len(data['sources']),1)
            self.assertIn(self.project,next(iter(data['sources'])))

    def test_invalid_numeric_selection_writes_no_library(self):
        result=self.cli('import','claude-code','--projects-root',str(self.projects),'--directory',str(self.base),'--select','0,99','--yes')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(self.base.exists())

    def test_interactive_number_picker_only_approves_selected_project(self):
        import imports
        argv=['context-bridge import','claude-code','--projects-root',str(self.projects),'--directory',str(self.base)]
        with patch.object(sys,'argv',argv), patch.object(sys.stdin,'isatty',return_value=True), patch('builtins.input',side_effect=['1','yes']), redirect_stdout(io.StringIO()):
            imports.main()
        data=json.loads(Sessions(self.base).config.read_text())
        self.assertEqual(len(data['sources']),1)

    def test_fallback_title_redacts_before_truncating_and_ignores_tool_bodies(self):
        path=self.projects/self.project/'fallback.jsonl'
        body='KEY=syntheticSecret842 '+'Discuss cleanup policies '*10
        self.write_session(path,body)
        metadata=code_metadata(path)
        self.assertTrue(metadata['title'].startswith('my-app · KEY=[REDACTED] '))
        self.assertNotIn('syntheticSecret842',metadata['title'])
        self.assertLessEqual(len(metadata['title'].split(' · ',1)[1]),60)
        with path.open('a') as stream:
            stream.write(json.dumps({'type':'ai-title','aiTitle':'Explicit title'})+'\n')
        self.assertEqual(code_metadata(path)['title'],'Explicit title')
        tool=path.parent/'tool.jsonl'
        tool.write_text(json.dumps({'type':'user','cwd':self.cwd,'sessionId':'tool','message':{'role':'user','content':[{'type':'tool_result','content':'NOT_A_TITLE842'}]}})+'\n'+path.read_text().splitlines()[0]+'\n')
        self.assertNotIn('NOT_A_TITLE842',code_metadata(tool)['title'])

    def test_account_change_stops_before_mutating_profile_database_or_copies(self):
        for provider in ('chatgpt','claude'):
            with self.subTest(provider=provider):
                directory=self.root/provider
                first=self.account_zip(self.root/(provider+'-one.zip'),'OLD842','account-one',provider=provider)
                import_export(provider,first,directory)
                manager=Sessions(directory)
                config_before=manager.config.read_bytes()
                data=json.loads(config_before)
                database_before=Path(data['database']).read_bytes()
                copy=Path(next(iter(data['sources'])))
                before=copy.read_bytes()
                second=self.account_zip(self.root/(provider+'-two.zip'),'NEW842','account-two',provider=provider)
                with self.assertRaises(AccountMismatch):
                    import_export(provider,second,directory)
                self.assertEqual(manager.config.read_bytes(),config_before)
                self.assertEqual(Path(data['database']).read_bytes(),database_before)
                self.assertEqual(copy.read_bytes(),before)
                self.assertNotIn('account-one@example.test',config_before.decode())
                result=import_export(provider,second,directory,confirm_account_switch=True)
                self.assertEqual(result['conversations_removed'],1)
                self.assertEqual(result['account_check'],'confirmed_switch')

    def test_same_account_email_change_and_missing_metadata(self):
        first=self.account_zip(self.root/'first.zip','OLD842','same-account','old@example.test')
        import_export('chatgpt',first,self.base)
        second=self.account_zip(self.root/'second.zip','NEW842','same-account','new@example.test')
        self.assertEqual(import_export('chatgpt',second,self.base)['account_check'],'matched')
        missing=self.account_zip(self.root/'missing.zip','UNVERIFIED842')
        with self.assertRaises(AccountMismatch):
            import_export('chatgpt',missing,self.base)

    def test_noninteractive_cli_cannot_bypass_account_check_with_yes(self):
        first=self.account_zip(self.root/'first.zip','OLD842','one')
        second=self.account_zip(self.root/'second.zip','NEW842','two')
        self.assertEqual(self.cli('import','chatgpt',str(first),'--directory',str(self.base)).returncode,0)
        blocked=self.cli('import','chatgpt',str(second),'--directory',str(self.base),'--yes')
        self.assertNotEqual(blocked.returncode,0)
        self.assertIn('--confirm-account-switch',blocked.stderr)
        self.assertEqual(self.cli('import','chatgpt',str(second),'--directory',str(self.base),'--confirm-account-switch').returncode,0)

    def test_named_profiles_isolate_import_stats_remove_and_mcp(self):
        first=self.account_zip(self.root/'first.zip','PERSONAL842','one')
        second=self.account_zip(self.root/'second.zip','WORK842','two')
        for name,path in [('personal',first),('work',second)]:
            result=self.cli('import','chatgpt',str(path),'--directory',str(self.base),'--profile',name)
            self.assertEqual(result.returncode,0,result.stderr)
            stats=self.cli('stats','--directory',str(self.base),'--profile',name)
            self.assertEqual(json.loads(stats.stdout)['conversations'],1)
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},{'jsonrpc':'2.0','method':'notifications/initialized'},{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'context_search','arguments':{'query':'WORK842'}}}]
        output=self.cli('mcp','--directory',str(self.base),'--profile','personal',input=''.join(json.dumps(m)+'\n' for m in messages))
        self.assertEqual(output.returncode,0,output.stderr)
        result=json.loads(json.loads(output.stdout.splitlines()[-1])['result']['content'][0]['text'])
        self.assertEqual(result['results'],[])
        removed=self.cli('remove','--provider','chatgpt','--directory',str(self.base),'--profile','work')
        self.assertEqual(json.loads(removed.stdout)['conversations_removed'],1)
        self.assertEqual(json.loads(self.cli('stats','--directory',str(self.base),'--profile','personal').stdout)['conversations'],1)
        with self.assertRaises(ValueError):
            profile_directory(self.base,'../escape')

    def test_interactive_account_confirmation_can_cancel_without_pruning(self):
        import imports
        first=self.account_zip(self.root/'first.zip','OLD842','one')
        second=self.account_zip(self.root/'second.zip','NEW842','two')
        import_export('chatgpt',first,self.base)
        config=Sessions(self.base).config
        before=config.read_bytes()
        argv=['context-bridge import','chatgpt',str(second),'--directory',str(self.base)]
        with patch.object(sys,'argv',argv), patch.object(sys.stdin,'isatty',return_value=True), patch('builtins.input',return_value='no'), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                imports.main()
        self.assertEqual(stopped.exception.code,1)
        self.assertEqual(before,config.read_bytes())
