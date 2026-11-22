# SPDX-License-Identifier: Apache-2.0
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch
from session_manager import Sessions,atomic_write
from mcp_server import ContextService
from repeats import report,review

class RepeatTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.manager=Sessions(self.root/'library')
        data=json.loads(self.manager.config.read_text())
        cases=[('a','chatgpt','2026-01-01','How configure aurora queue retries safely?'),('b','claude','2026-01-02','How configure aurora queue retries safely?'),('c','claude-code','2026-01-03','How configure aurora queue retries safely?'),('d','claude','2026-01-04','How disable aurora queue retries safely?'),('e','chatgpt','2026-01-05','How prepare a sourdough starter?'),('f','chatgpt',None,'How configure aurora queue retries safely?')]
        for cid,provider,created,question in cases:
            path=self.root/(cid+'.jsonl')
            rows=[{'type':'user','uuid':'q','sessionId':cid,'timestamp':created,'message':{'role':'user','content':question}}, {'type':'assistant','uuid':'a','sessionId':cid,'timestamp':created,'message':{'id':'a','role':'assistant','content':'SECRET_BODY_MARKER '+('Production deployment needs review.' if cid=='c' else 'Settled answer.'),**({'usage':{'input_tokens':2,'output_tokens':136,'cache_creation_input_tokens':12121,'cache_read_input_tokens':24840}} if cid=='c' else {})}}]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            data['approved_transcripts'].append(str(path));data.setdefault('sources',{})[str(path)]={'provider':provider,'conversation_id':cid,'title':'Topic '+cid,'created_at':created}
        path=self.root/'g.jsonl'
        rows=[{'type':'session_meta','timestamp':'2026-01-06','payload':{'id':'g'}},{'type':'response_item','timestamp':'2026-01-06','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'How configure aurora queue retries safely?'}]}},{'type':'response_item','timestamp':'2026-01-06','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'SECRET_BODY_MARKER settled answer.'}]}},{'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':1000,'cached_input_tokens':400,'output_tokens':150}}}}]
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        data['approved_transcripts'].append(str(path));data['sources'][str(path)]={'provider':'codex','conversation_id':'g','title':'Topic g','created_at':'2026-01-06'}
        atomic_write(self.manager.config,data);self.service=ContextService(self.manager.config);self.service.refresh()
        self.addCleanup(lambda:self.service.bridge.db.close())

    def test_pairs_chains_cross_provider_cost_and_title_only(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('offline')):r=report(self.service.bridge)
        self.assertEqual(r['conversations'],7);self.assertEqual(r['conversations_with_earlier_similar'],3)
        self.assertEqual(r['repeat_rate'],3/7);self.assertEqual(r['conversations_without_dates'],1)
        self.assertEqual(r['top_topics'][0]['conversation_titles'],['Topic a','Topic b','Topic c','Topic g'])
        pairs={(s['earlier']['title'],s['later']['title']) for s in r['sample_pairs']}
        self.assertEqual(pairs,{('Topic a','Topic b'),('Topic b','Topic c'),('Topic c','Topic g')})
        self.assertEqual(r['providers']['claude-code']['conservative_research_tokens'],136)
        self.assertIn('visible-text-estimate',r['providers']['claude']['cost_methods'])
        self.assertEqual(r['providers']['codex']['conservative_research_tokens'],150)
        self.assertEqual(r['likely_redo']['share'],1/3)
        wire=json.dumps(r)
        for forbidden in ('SECRET_BODY_MARKER','configure aurora',str(self.root),'question','body'):
            # Method description legitimately says questions; no exact source text leaks.
            if forbidden=='question':continue
            self.assertNotIn(forbidden,wire)

    def test_review_hashes_precision_profile_isolation_and_threshold(self):
        r=report(self.service.bridge)
        with redirect_stderr(io.StringIO()):review(self.service.bridge,r,confirm=iter(['y','n','s']).__next__)
        checked=report(self.service.bridge)
        self.assertEqual(checked['review_precision']['precision'],.5)
        rows=self.service.bridge.db.execute('SELECT pair_id,is_repeat FROM repeat_reviews').fetchall()
        self.assertEqual(len(rows),2);self.assertTrue(all(len(row[0])==64 for row in rows))
        self.service.bridge.db.execute("INSERT INTO repeat_reviews VALUES ('other','other','opaque',1,'2026-01-01')")
        self.assertEqual(report(self.service.bridge)['review_precision']['labelled_current_pairs'],2)
        for threshold in (-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):report(self.service.bridge,threshold)
        self.assertEqual(report(self.service.bridge,1)['conversations_with_earlier_similar'],3)

    def test_real_cli_title_only_and_noninteractive_review(self):
        cmd=[sys.executable,'-c','from prototype.cli import main; main()','repeats','--directory',str(self.manager.root),'--json']
        run=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr);self.assertEqual(json.loads(run.stdout)['conversations_with_earlier_similar'],3)
        self.assertNotIn('SECRET_BODY_MARKER',run.stdout);self.assertNotIn(str(self.root),run.stdout)
        other=subprocess.run(cmd+['--profile','separate'],capture_output=True,text=True)
        self.assertEqual(other.returncode,0,other.stderr)
        self.assertEqual(json.loads(other.stdout)['conversations'],0)
        run=subprocess.run(cmd+['--review'],input='',capture_output=True,text=True)
        self.assertNotEqual(run.returncode,0);self.assertIn('interactive terminal',run.stderr);self.assertNotIn('Traceback',run.stderr)

    def test_hybrid_uses_local_question_vectors_not_answer_matches(self):
        # Small deterministic local-vector stand-in; no dependency install or network.
        class Vector:
            def __init__(self,i):self.i=i
            def __matmul__(self,other):return 1.0 if self.i<3 and other.i<3 else 0
        class Embedder:
            def encode(self,texts):
                self_seen.extend(texts);return [Vector(0 if t=='How configure aurora queue retries safely?' else 3) for t in texts]
        self_seen=[]
        self.service.bridge.retrieval_settings={'mode':'hybrid','model_directory':'synthetic-no-download'}
        with patch('semantic.model',return_value=Embedder()),patch('urllib.request.urlopen',side_effect=AssertionError('offline')):
            r=report(self.service.bridge)
        self.assertEqual(r['mode'],'hybrid');self.assertEqual(r['min_similarity'],.78)
        self.assertEqual(r['conversations_with_earlier_similar'],3)
        self.assertFalse(any('SECRET_BODY_MARKER' in t for t in self_seen))


    def test_interactive_cli_review_persists_only_pair_hashes(self):
        import pty
        master,slave=pty.openpty()
        try:
            cmd=[sys.executable,'-c','from prototype.cli import main; main()','repeats','--directory',str(self.manager.root),'--json','--review']
            process=subprocess.Popen(cmd,stdin=slave,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            os.close(slave);slave=None
            os.write(master,b'y\nn\ns\n')
            output,error=process.communicate(timeout=10)
            self.assertEqual(process.returncode,0,error)
            self.assertEqual(json.loads(output)['review_precision']['precision'],.5)
            self.assertNotIn('SECRET_BODY_MARKER',output+error)
            for pair in json.loads(output)['sample_pairs']:
                self.assertEqual(set(pair),{'earlier','later'})
                self.assertEqual(set(pair['earlier']),{'title','date'})
        finally:
            os.close(master)
            if slave is not None:os.close(slave)

    def test_sensitivity_review_calibrates_below_default_without_text_leaks(self):
        from datetime import datetime,timezone
        from repeats import digest
        from contextlib import redirect_stderr
        items=[]
        for i in range(5):
            when=datetime(2026,1,i+1,tzinfo=timezone.utc)
            items.append({'key':digest(['fixture',i]),'provider':'claude','title':'Calibration '+str(i),'date':when.isoformat(),'when':when,'question':'PRIVATE_CALIBRATION_TEXT','terms':{'research','topic','task'},'cost':10,'cost_method':'fixture','likely_redo':False})
        scores=[0,.45,.55,.65,.75]
        class Vector:
            def __init__(self,i):self.i=i
            def __matmul__(self,other):return (scores[self.i]-.15)/.85 if other.i==0 else 0
        class Embedder:
            def encode(self,texts):return [Vector(i) for i in range(len(texts))]
        bridge=self.service.bridge;bridge.retrieval_settings={'mode':'hybrid','model_directory':'fixture'}
        with patch('repeats.conversations',return_value=items),patch('semantic.model',return_value=Embedder()) as model,patch('urllib.request.urlopen',side_effect=AssertionError('offline')):
            result=report(bridge)
            self.assertEqual(model.call_count,1)
            self.assertEqual(result['conversations_with_earlier_similar'],0)
            self.assertEqual([r['repeats'] for r in result['sensitivity']],[4,3,2,1,0])
            self.assertTrue(all(r['precision'] is None for r in result['sensitivity']))
            # Even with zero at default, review offers lower-score candidates.
            with redirect_stderr(io.StringIO()) as stderr:review(bridge,result,confirm=iter(['y','y','n','n']).__next__)
            calibrated=report(bridge)
        table={r['threshold']:r for r in calibrated['sensitivity']}
        self.assertEqual(table[.4]['precision'],.5)
        self.assertEqual(table[.5]['precision'],2/3)
        self.assertEqual(table[.6]['precision'],1)
        self.assertEqual(table[.7]['precision'],1)
        self.assertIsNone(table[.78]['precision'])
        self.assertEqual(table[.4]['review_coverage'],1)
        self.assertIn('library-dependent',calibrated['calibration'])
        self.assertNotIn('PRIVATE_CALIBRATION_TEXT',json.dumps(calibrated)+stderr.getvalue())

    def test_sensitivity_synthetic_positive_negative_defaults_and_cli_table(self):
        # The original fixture includes exact positive chains and a negated
        # lookalike. This is a sanity check, not real embedding calibration.
        result=report(self.service.bridge)
        self.assertEqual(result['min_similarity'],.85)
        self.assertEqual([r['repeats'] for r in result['sensitivity']],[3,3,3,3,3])
        cmd=[sys.executable,'-c','from prototype.cli import main; main()','repeats','--directory',str(self.manager.root)]
        run=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        for text in ('Threshold | Repeats','--review','0.4','0.7','library-dependent'):self.assertIn(text,run.stdout)
        self.assertNotIn('SECRET_BODY_MARKER',run.stdout)
