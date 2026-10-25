# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
from evaluate import Fixture


class PassageReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = Fixture(Path(self.tmp.name))
        self.addCleanup(self.fixture.close)
        self.body = ('Ordinary context with no relevant evidence. ' * 700) + 'DAHLIA621 needs two approvals before deployment.'
        self.fixture.load([self.fixture.record('long', self.body)])
        self.source = str(self.fixture.root / 'long.jsonl')

    def read(self, **extra):
        return self.fixture.service.call('context_read', {'source': self.source, 'line': 1, **extra})['record']

    def test_focused_passage_finds_late_evidence(self):
        result = self.read(query='DAHLIA621 approval', max_chars=600)
        self.assertIn('DAHLIA621 needs two approvals', result['body'])
        self.assertEqual(result['body'], self.body[result['passage_start']:result['passage_end']])
        self.assertLessEqual(len(result['body']),600)
        self.assertEqual(result['read_mode'], 'question_focused')

    def test_all_pages_reassemble_original_without_loss(self):
        result = self.read(max_chars=4000)
        body, sha = result['body'], result['record_sha256']
        pages = 1
        while result['has_more']:
            result = self.read(start=result['next_start'],max_chars=4000,expected_sha256=sha)
            body += result['body']; pages += 1
        self.assertGreater(pages, 3)
        self.assertEqual(body, self.body)
        self.assertIsNone(result['next_start'])

    def test_changed_record_cannot_be_mixed_with_previous_page(self):
        result = self.read(max_chars=4000)
        path = Path(self.source)
        data = json.loads(path.read_text())
        data['message']['content'] = 'Changed evidence. ' + self.body
        path.write_text(json.dumps(data)+'\n')
        with self.assertRaises(ValueError):
            self.read(start=4000, expected_sha256=result['record_sha256'])

    def test_revocation_blocks_paging(self):
        result = self.read()
        self.fixture.data['approved_transcripts'] = []
        self.fixture.flush()
        with self.assertRaises(ValueError):
            self.read(start=result['next_start'], expected_sha256=result['record_sha256'])

    def test_invalid_bounds_and_ambiguous_mode_are_rejected(self):
        for extra in ({'start':-1},{'start':True},{'max_chars':255},{'max_chars':12001},{'start':len(self.body)+1},{'query':'DAHLIA621','start':0},{'query':''},{'expected_sha256':'invalid'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.read(**extra)

    def test_unrelated_question_does_not_return_arbitrary_prefix(self):
        with self.assertRaises(ValueError):
            self.read(query='QUARTZ900')
