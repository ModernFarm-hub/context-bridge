# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import unittest
from retrieval import rank


def row(name, body, timestamp=None):
    return {'session': name, 'source': name + '.jsonl', 'line': 1, 'role': 'user', 'timestamp': timestamp, 'body': body}


class RankingTests(unittest.TestCase):
    def test_common_words_do_not_produce_results(self):
        rows = [row('noise', 'The dashboard is green and the build is passing.')]
        self.assertEqual(rank(rows, 'What is the password rotation policy?', 5), [])
        self.assertEqual(rank(rows, 'the is what', 5), [])

    def test_passage_retains_original_text_and_support_near_end(self):
        body = 'Unrelated background. ' * 400 + 'LOTUS817 needs approval by Friday.'
        hit = rank([row('long', body)], 'LOTUS817', 5)[0]
        self.assertIn('LOTUS817 needs approval by Friday.', hit['body'])
        self.assertEqual(hit['body'], body[hit['passage_start']:hit['passage_end']])
        self.assertLessEqual(len(hit['body']), 4000)

    def test_recency_requires_subject_coverage_and_valid_timestamp(self):
        rows = [row('old', 'Maple access requires two reviewers.', '2026-10-21T09:00:00Z'), row('new', 'Maple access requires three reviewers.', '2026-10-22T09:00:00Z'), row('unrelated', 'Lunch reviewers menu.', '2026-10-23T09:00:00Z'), row('unknown', 'Maple access reviewers.', 'not-a-time')]
        hits = rank(rows, 'Latest Maple access reviewers', 5)
        self.assertEqual(hits[0]['session'], 'new')
        self.assertLess(next(i for i,h in enumerate(hits) if h['session']=='old'), next(i for i,h in enumerate(hits) if h['session']=='unknown'))

    def test_infrequent_terms_and_plurals(self):
        rows = [row('relevant', 'Permission checks enforce least privilege.'), row('noise', 'Meeting checks include snacks and drinks.')]
        self.assertEqual(rank(rows, 'permissions', 5)[0]['session'], 'relevant')

    def test_exact_identifiers_are_not_semantic_substitutes(self):
        self.assertEqual(rank([row('near', 'LOTUS818 approved.')], 'LOTUS817', 5), [])
