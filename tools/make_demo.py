# SPDX-License-Identifier: Apache-2.0
"""Render a synthetic walkthrough from actual local import/search output.

Development-only renderer: requires Pillow; never reads real conversations.
"""
import json
from pathlib import Path
import sys
import tempfile
import zipfile
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'prototype'))
from imports import import_export
from mcp_server import ContextService, public_result
from session_manager import Sessions


def make_demo(destination):
    with tempfile.TemporaryDirectory(prefix='context-bridge-demo-art-') as tmp:
        root=Path(tmp)
        chatgpt=[{'id':'synthetic-kafka','title':'Kafka retry design','create_time':1792540800,'current_node':'m1','mapping':{'m1':{'parent':None,'message':{'id':'m1','author':{'role':'user'},'create_time':1792540800,'content':{'content_type':'text','parts':['Kafka retries use exponential backoff, with a budget of five attempts.']}}}}}]
        claude=[{'uuid':'synthetic-approval','name':'Deployment planning','created_at':'2026-10-21T09:00:00Z','chat_messages':[{'uuid':'m2','sender':'human','text':'Maya must approve changes to the Kafka retry budget before deployment.'}]}]
        results=[]
        for provider,data in [('chatgpt',chatgpt),('claude',claude)]:
            archive=root/(provider+'.zip')
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('conversations.json',json.dumps(data))
            results.append(import_export(provider,archive,root/'library'))
        service=ContextService(Sessions(root/'library').config)
        try:
            hits=public_result(service.call('context_search',{'query':'Kafka retry budget'}))['results']
            hit=next(h for h in hits if h['link'].startswith('https://chatgpt.com/'))
            passage=public_result(service.call('context_read',{'record_id':hit['record_id']}))['record']
        finally:
            service.bridge.db.close()
    slides=[
        ('1 / 4   Import your exports',[
            '$ context-bridge import chatgpt export.zip',
            f"  {results[0]['conversations_imported']} conversation imported locally",
            '', '$ context-bridge import claude export.zip',
            f"  {results[1]['conversations_imported']} conversation imported locally",
            '', 'Original ZIPs stay unchanged. No cloud indexing.'
        ]),
        ('2 / 4   Connect your MCP client',[
            '$ context-bridge mcp', '',
            'Claude Code / Claude Desktop / Cursor',
            '  context_search  ·  context_read', '',
            'One local library. No required source/reader split.'
        ]),
        ('3 / 4   Ask across your conversations',[
            'context_search(query="Kafka retry budget")', '',
            'Recorded passages found in both providers:',
            '  ChatGPT · Kafka retry design',
            '  Claude · Deployment planning', '',
            'Exact message IDs stay local; citation handles go to the client.'
        ]),
        ('4 / 4   Read the evidence and cite it',[
            passage['body'], '', hit['source_label'], hit['link'], '',
            'Read larger passages with context_read(record_id=...).',
            'Recorded statements are evidence, not verified facts.'
        ])
    ]
    font=ImageFont.load_default(size=22)
    titlefont=ImageFont.load_default(size=34)
    small=ImageFont.load_default(size=17)
    frames=[]
    for heading,lines in slides:
        frame=Image.new('RGB',(1120,630),'#0b1220')
        draw=ImageDraw.Draw(frame)
        draw.text((44,28),'CONTEXT BRIDGE',font=small,fill='#69ddbd')
        draw.text((44,62),'Find the conversation. Keep the citation.',font=titlefont,fill='#f1f5f9')
        draw.rounded_rectangle((32,127,1088,554),radius=16,fill='#172235',outline='#31435c',width=2)
        draw.text((58,150),heading,font=font,fill='#69ddbd')
        y=205
        import textwrap
        for line in lines:
            for wrapped in textwrap.wrap(line,width=79) or ['']:
                draw.text((58,y),wrapped,font=font,fill='#e3eaf5')
                y+=35
        draw.text((44,586),'SYNTHETIC WALKTHROUGH · ACTUAL LOCAL IMPORT / MCP TOOL OUTPUT',font=small,fill='#9cacbf')
        frames.append(frame)
    destination.parent.mkdir(parents=True,exist_ok=True)
    frames[0].save(destination,save_all=True,append_images=frames[1:],duration=[2200,2200,2600,4200],loop=0,optimize=True)
    frames[-1].save(destination.with_suffix('.preview.png'))
    print('Created '+str(destination))


if __name__=='__main__':
    make_demo(ROOT/'docs/assets/demo.gif')
