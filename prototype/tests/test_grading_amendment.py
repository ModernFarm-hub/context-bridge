# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from savings_real_grading import grade,grade_details,equal_value
from savings_real import DATA,benchmark
from savings_real_analysis import analyze
from savings_real_regrade import regrade
from reuse_policy import parse_decision

class FormattingAmendmentTests(unittest.TestCase):
    def test_real_pilot_fixtures_and_labelled_prose_excerpts(self):
        fixtures=json.loads((DATA/'grading-formatting-fixtures.json').read_text())
        for f in fixtures:
            with self.subTest(f['id']):
                result=grade_details(f['answer'],f['reference'])
                self.assertEqual(result['correct'],f['correct']);self.assertEqual(result['method'],f['method'])
        self.assertIn('saved full answer also contains JSON',fixtures[1]['source'])

    def test_normalization_accepts_formatting_but_not_wrong_names_or_values(self):
        for actual in ('ssl.create_default_context','SSL.CREATE_DEFAULT_CONTEXT','`ssl.create_default_context`',"'ssl.create_default_context'",'"CREATE_DEFAULT_CONTEXT"'):
            self.assertTrue(equal_value(actual,'create_default_context'),actual)
        self.assertTrue(grade('{"facts":{"x":true,"y":false}}',{'x':'true','y':'false'}))
        for actual,reference in [('urlparse','urlsplit'),('urllib.parse.urlparse','urlsplit'),('urlsplit_extra','urlsplit'),('myurlsplit','urlsplit'),('ssl.create_default_context_bad','create_default_context'),('other.urlsplit','urllib.parse.urlsplit'),(False,'true'),(1,'true'),('not false','false'),('13.14','3.14')]:
            self.assertFalse(equal_value(actual,reference),(actual,reference))

    def test_prose_boundaries_negation_and_structured_facts_authority(self):
        self.assertTrue(grade('The result is `28`; the function is `JSON.LOADS`.',{'n':'28','method':'loads'}))
        for text in ('Use urlparse instead.','Use urlparse, not urlsplit.','urlsplit is incorrect; use urlparse.','myurlsplit returns data.'):
            self.assertFalse(grade(text,{'method':'urlsplit'}),text)
        self.assertFalse(grade('not 28',{'n':'28'}))
        self.assertFalse(grade('split is urlunsplit; join is urlsplit.',{'split':'urlsplit','join':'urlunsplit'}))
        self.assertFalse(grade('available is True; default is False.',{'available':'true','default':'true'}))
        self.assertTrue(grade('available is True; default is False.',{'available':'true','default':'false'}))
        self.assertFalse(grade('Use a stream, with punctuation.',{'delimiter':','}))
        self.assertTrue(grade('The delimiter is `,`.',{'delimiter':','}))
        self.assertFalse(grade('{"facts":{"method":"urlparse"}} Correct name: urlsplit.',{'method':'urlsplit'}))
        self.assertFalse(grade('{"facts":{"method":"urlsplit"}} Other value: 28.',{'method':'urlsplit','n':'28'}))
        self.assertEqual(grade_details('urlsplit',{'method':'urlsplit'},final=False)['method'],'not_final')
        self.assertFalse(grade_details('urlsplit',{'method':'urlsplit'},final=False)['correct'])

    def test_decision_separators_case_inline_and_ambiguity(self):
        for text,choice in [('Reuse decision: REUSE: an earlier conversation…','REUSE'),('Answer. reuse decision: check - verify','CHECK'),('REUSE DECISION: redo — high stakes','REDO'),('Reuse decision: CHECK\nSources follow','CHECK'),('prefix Reuse decision: REDO','REDO'),('Reuse decision: REUSE – existing separator','REUSE')]:
            self.assertEqual(parse_decision(text),choice,text)
        for text in ('Reuse decision: REUSED: nope','Reuse decision: MAYBE - nope','Reuse decision: REUSE. earlier note','Reuse decision: REUSE: yes\nReuse decision: REDO - no'):
            self.assertIsNone(parse_decision(text),text)

    def test_fallback_share_and_compliance_do_not_change_token_metric(self):
        definitions=[{'id':'t','variant':'same','expected_decision':'REUSE'}]
        rows=[]
        for arm in ('baseline','reuse'):
            for rep in range(3):rows.append({'phase':'B','task_id':'t','arm':arm,'repetition':rep,'usage':{'input_tokens':100 if arm=='baseline' else 120,'output_tokens':10},'correct':True,'decision':'CHECK' if arm=='reuse' else None,'grading_method':'text_fallback' if rep==0 else 'facts_json'})
        before=analyze(rows,definitions);changed=copy.deepcopy(rows)
        for r in changed:r['correct']=False;r['grading_method']='facts_json'
        after=analyze(changed,definitions)
        self.assertEqual(before['overall']['mean_paired_ratio'],after['overall']['mean_paired_ratio'])
        self.assertEqual(before['overall']['ratio_95_interval'],after['overall']['ratio_95_interval'])
        self.assertEqual(before['fallback_grading']['overall']['fallback_share'],1/3)
        self.assertEqual(before['decision_compliance']['compliance_rate'],1)
        self.assertEqual(before['overall']['decision_accuracy'],0)
        rows[0]['grading_method']='not_final'
        report=analyze(rows,definitions)['fallback_grading']['overall']
        self.assertEqual(report['graded_final_answers'],5);self.assertEqual(report['fallback_sessions'],1)

    def test_offline_regrade_preserves_sources_and_primary_token_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pilot=root/'pilot'
            with redirect_stdout(io.StringIO()),patch('urllib.request.urlopen',side_effect=AssertionError('No network')):
                benchmark(pilot,fake=True,pilot=True)
            original={str(p.relative_to(pilot)):hashlib.sha256(p.read_bytes()).hexdigest() for p in pilot.rglob('*') if p.is_file()}
            with patch('urllib.request.urlopen',side_effect=AssertionError('No network')),patch('savings_real.Provider',side_effect=AssertionError('No provider')),patch('savings_real.make_library',side_effect=AssertionError('No library')):
                result=regrade(pilot,DATA,root/'sidecars')
            after={str(p.relative_to(pilot)):hashlib.sha256(p.read_bytes()).hexdigest() for p in pilot.rglob('*') if p.is_file()}
            self.assertEqual(original,after);self.assertEqual(len(result['sessions']),15)
            self.assertEqual(result['before']['paired_tasks'],result['after']['paired_tasks'])
            self.assertFalse(result['claim_eligible']);self.assertTrue(result['no_new_api_calls'])
            text=(root/'sidecars/regrade.json').read_text()+(root/'sidecars/regrade.md').read_text()
            self.assertNotIn(str(root),text)
            self.assertIn('Correct before',(root/'sidecars/regrade.md').read_text())
            rows=[json.loads(x) for x in (pilot/'results.jsonl').read_text().splitlines()]
            rows[0]['answer']='edited, no longer matches saved response'
            (pilot/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'does not match raw'):regrade(pilot,DATA,root/'bad-sidecars')
