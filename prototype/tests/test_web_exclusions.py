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
from library import remove, exclusions, exclusion_hash, inspect_library
from local_profile import profile_directory
from session_manager import Sessions


class WebExclusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.library = self.root/'library'

    def archive(self, provider, ids):
        conversations = []
        for cid in ids:
            if provider=='chatgpt':
                conversations.append({'id':cid,'title':'Private work title','current_node':'m','mapping':{'m':{'parent':None,'message':{'id':'m','author':{'role':'user'},'content':{'content_type':'text','parts':['WORK842 finding']}}}}})
            else:
                conversations.append({'uuid':cid,'name':'Private work title','chat_messages':[{'uuid':'m','sender':'human','text':'WORK842 finding'}]})
        path = self.root/(provider+'.zip')
        with zipfile.ZipFile(path,'w') as out:
            out.writestr('conversations.json',json.dumps(conversations))
        return path

    def test_remove_reimport_clear_and_restore_both_providers(self):
        for provider, base in (('chatgpt','https://chatgpt.com/c/'),('claude','https://claude.ai/chat/')):
            with self.subTest(provider=provider):
                root = self.library/provider
                archive = self.archive(provider,['private-id','keep-id'])
                import_export(provider,archive,root)
                remove(root,conversation=base+'private-id')
                result = import_export(provider,archive,root)
                self.assertEqual(result['conversations_excluded'],1)
                self.assertEqual(result['conversations_imported'],1)
                self.assertEqual(result['conversations_removed'],0)
                self.assertEqual([r['conversation_id'] for r in inspect_library(root)[0]],['keep-id'])
                self.assertEqual(exclusions(root,base+'private-id')['exclusions_cleared'],1)
                self.assertEqual(import_export(provider,archive,root)['conversations_imported'],2)
                self.assertEqual(exclusions(root)['exclusions'],[])

    def test_hash_only_profile_and_provider_isolation_and_provider_remove(self):
        personal = profile_directory(self.library,'personal')
        other = profile_directory(self.library,'other')
        archive = self.archive('chatgpt',['private-id'])
        import_export('chatgpt',archive,personal)
        remove(personal,conversation='private-id')
        config_text = Sessions(personal).config.read_text()
        self.assertNotIn('private-id',config_text)
        self.assertNotIn('Private work title',config_text)
        stored = json.loads(config_text)['web_exclusions']
        self.assertEqual(stored,{'chatgpt':[exclusion_hash('chatgpt','private-id')]})
        self.assertNotIn('private-id',json.dumps(stored))
        self.assertNotIn('Private work title',json.dumps(stored))
        remove(personal,provider='chatgpt')
        self.assertEqual(import_export('chatgpt',archive,personal)['conversations_excluded'],1)
        self.assertEqual(import_export('chatgpt',archive,other)['conversations_imported'],1)
        self.assertEqual(exclusions(other)['exclusions'],[])
        self.assertEqual(import_export('claude',self.archive('claude',['private-id']),personal)['conversations_imported'],1)
        # Clearing via bare ID is intentional and works without stored plaintext IDs.
        self.assertEqual(exclusions(personal,'private-id')['exclusions_cleared'],1)

    def test_snapshot_pruning_does_not_add_exclusions_or_count_excluded_as_removed(self):
        archive = self.archive('chatgpt',['private-id','keep-id','absent-id'])
        import_export('chatgpt',archive,self.library)
        remove(self.library,conversation='private-id')
        result = import_export('chatgpt',self.archive('chatgpt',['private-id','keep-id']),self.library)
        self.assertEqual(result['conversations_removed'],1)
        self.assertEqual(result['conversations_excluded'],1)
        self.assertEqual(len(exclusions(self.library)['exclusions']),1)
        # Snapshot pruning is not a deliberate exclusion: absent chats can return.
        result = import_export('chatgpt',self.archive('chatgpt',['private-id','keep-id','absent-id']),self.library)
        self.assertEqual(result['conversations_imported'],2)
        self.assertEqual(result['conversations_excluded'],1)

    def test_real_cli_profile_remove_list_clear_and_reimport(self):
        launch = self.root/'source'
        launch.mkdir()
        (launch/'context_bridge').symlink_to(Path(__file__).parents[1].resolve(),target_is_directory=True)
        env = {**os.environ,'PYTHONPATH':str(launch),'PYTHONDONTWRITEBYTECODE':'1'}
        def cli(*args):
            run = subprocess.run([sys.executable,'-m','context_bridge',*args,'--directory',str(self.library),'--profile','personal'],cwd=self.root,env=env,text=True,capture_output=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stderr)
            return json.loads(run.stdout)
        archive = self.archive('chatgpt',['private-id'])
        cli('import','chatgpt',str(archive))
        cli('remove','--conversation','https://chatgpt.com/c/private-id')
        self.assertEqual(cli('import','chatgpt',str(archive))['conversations_excluded'],1)
        entries = cli('exclusions','list')['exclusions']
        self.assertEqual(entries,[{'provider':'chatgpt','hash':exclusion_hash('chatgpt','private-id')}])
        self.assertEqual(cli('exclusions','clear','--conversation','private-id')['exclusions_cleared'],1)
        self.assertEqual(cli('import','chatgpt',str(archive))['conversations_imported'],1)
