# SPDX-License-Identifier: Apache-2.0
"""Offline, disposable first-run demo. No real library or transcript is read."""
import json
from pathlib import Path
import tempfile
import zipfile
if __package__:
    from .imports import import_export,import_code,project_preview
    from .mcp_server import ContextService
    from .session_manager import Sessions
else:
    from imports import import_export,import_code,project_preview
    from mcp_server import ContextService
    from session_manager import Sessions

MCP_COMMAND='claude mcp add --transport stdio context-bridge -- uvx --from context-bridge-local context-bridge mcp'


def main():
    with tempfile.TemporaryDirectory(prefix='context-bridge-demo-') as directory:
        root=Path(directory)
        library=root/'library'
        chatgpt=[('Retention policy','Customer records must be deleted after 45 days. This is the agreed retention policy.'),
                 ('API retry budget','Retry failed API requests up to five times, then send them to a dead-letter queue.'),
                 ('Team onboarding','New teammates read the architecture guide and pair on their first issue.'),
                 ('Pricing decision','The starter plan includes three projects; annual billing gets a discount.')]
        claude=[('Release approval','Maya, the service owner, must approve production releases and cleanup-job changes.'),
                ('Rollback plan','Recover a working deployment by restoring the previous container image and its configuration.'),
                ('Backup recovery','Weekly backups are tested with a monthly restore drill.')]
        for provider,cases in [('chatgpt',chatgpt),('claude',claude)]:
            conversations=[]
            for i,(title,body) in enumerate(cases):
                cid='synthetic-'+provider+'-'+str(i)
                if provider=='chatgpt':
                    conversations.append({'id':cid,'title':title,'create_time':1792540800,'current_node':'m','mapping':{'m':{'parent':None,'message':{'id':'m','author':{'role':'user'},'content':{'content_type':'text','parts':[body]}}}}})
                else:
                    conversations.append({'uuid':cid,'name':title,'created_at':'2026-10-21T10:00:00Z','chat_messages':[{'uuid':'m','sender':'human','text':body}]})
            archive=root/(provider+'.zip')
            with zipfile.ZipFile(archive,'w') as out:
                out.writestr('conversations.json',json.dumps(conversations))
            import_export(provider,archive,library)
        project=root/'projects/demo-app'
        project.mkdir(parents=True)
        for i,(title,body) in enumerate([('Cleanup configuration','cleanup.py sets RETENTION_DAYS=45 to implement the customer records retention policy.'),('Accessible signup','The signup form supports keyboard navigation and clearly labeled validation errors.'),('Support handoff','Customer requests are triaged each morning; urgent incidents page the on-call engineer.')]):
            rows=[{'type':'ai-title','aiTitle':title},{'type':'user','uuid':'m','sessionId':'synthetic-code-'+str(i),'timestamp':'2026-10-21T11:00:00Z','message':{'role':'user','content':body}}]
            (project/(str(i)+'.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in rows))
        import_code(project_preview(root/'projects'),library)
        service=ContextService(Sessions(library).config)
        print('Context Bridge · offline demo\n10 invented conversations across ChatGPT, Claude and Claude Code.\nAll citations below are synthetic; your real library is never read or changed.')
        try:
            for query,label in [('customer retention policy','Search 1'),('Who approves production releases?','Search 2'),('How do we get back to a working deployment?','Search 3 · paraphrased question')]:
                print('\n'+label+': '+query)
                hits=service.call('context_search',{'query':query,'limit':2})['results']
                if not hits:
                    raise RuntimeError('Synthetic demo search returned no results')
                for hit in hits:
                    print('  '+hit['body'])
                    print('  Source: '+hit['source_label']+' — '+hit['link'])
        finally:
            if service.bridge:
                service.bridge.db.close()
    print('\nDemo files removed. Try your own Claude Code history (choose projects to approve):\nuvx --from context-bridge-local context-bridge import claude-code\n'+MCP_COMMAND+'\n\nStart a new Claude Code session and ask: Use context_search to find a past decision. Cite its source.')


if __name__=='__main__':
    main()
