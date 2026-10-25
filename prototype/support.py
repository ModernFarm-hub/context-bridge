# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Experimental local claim-to-passage inference; never verifies external truth."""
from functools import lru_cache
from pathlib import Path
import re
if __package__:
    from .setup_support import digest, model_spec
    from .evidence_graph import components, binding_risks, sentence_spans
else:
    from setup_support import digest, model_spec
    from evidence_graph import components, binding_risks, sentence_spans

NOTICE = 'Experimental model judgment about the supplied passage only. Not independent fact verification or proof of permissions. Neutral means not established, not necessarily false.'


class SupportChecker:
    def __init__(self, directory, threshold=.90):
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not .5 <= threshold <= .99:
            raise ValueError('Support cutoff must be between 0.50 and 0.99')
        self.threshold = threshold
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        root = Path(directory).resolve(strict=True)
        spec = model_spec(root)
        for name, (kind, expected) in spec['files'].items():
            if digest((root / name).read_bytes(), kind) != expected:
                raise ValueError('Support model integrity check failed')
        import json
        labels = json.loads((root / 'config.json').read_text()).get('id2label', {})
        normalized = {str(key): str(value).casefold() for key, value in labels.items()}
        if normalized != {'0': 'contradiction', '1': 'entailment', '2': 'neutral'}:
            raise ValueError('Unexpected support classifier label order')
        self.np = np
        self.model_id = spec['model'] + '@' + spec['revision']
        self.inference_calls = 0
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(root / 'onnx/model.onnx'), options, providers=['CPUExecutionProvider'])
        self.tokenizer = Tokenizer.from_file(str(root / 'tokenizer.json'))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()

    def _score_passage(self, passage, claim):
        if not isinstance(passage, str) or not passage.strip() or len(passage) > 12000:
            raise ValueError('Supply a passage of 1–12000 characters')
        if not isinstance(claim, str) or not claim.strip() or len(claim) > 2000:
            raise ValueError('Supply one claim of 1–2000 characters')
        base = {'notice': NOTICE, 'model': self.model_id, 'threshold': self.threshold}
        encoded = self.tokenizer.encode(passage, claim)
        if len(encoded.ids) > 512:
            return {**base, 'status': 'needs_review', 'reason': 'Input exceeds model window; no silent truncation or inferred verdict.', 'scores': None}
        np = self.np
        batch = {'input_ids': np.asarray([encoded.ids], dtype=np.int64), 'attention_mask': np.asarray([encoded.attention_mask], dtype=np.int64), 'token_type_ids': np.asarray([encoded.type_ids], dtype=np.int64)}
        inputs = {item.name for item in self.session.get_inputs()}
        self.inference_calls += 1
        logits = self.session.run(None, {k: v for k, v in batch.items() if k in inputs})[0][0]
        if logits.shape != (3,) or not np.isfinite(logits).all():
            raise ValueError('Invalid support model output')
        probabilities = np.exp(logits - logits.max())
        probabilities /= probabilities.sum()
        # Order pinned by upstream model card: contradiction, entailment, neutral.
        scores = dict(zip(('contradiction', 'entailment', 'neutral'), map(float, probabilities)))
        label = max(scores, key=scores.get)
        # Unsupported new numeric assertions require review, including arithmetic.
        numbers = lambda text: set(re.findall(r'\b\d+(?:\.\d+)?\b', text))
        identifiers = lambda text: {re.sub(r'[-_]', '', value.casefold()) for value in re.findall(r'\b[a-zA-Z]+[-_]?\d+\b', text)}
        if identifiers(claim) - identifiers(passage):
            status, reason = 'needs_review', 'Claim introduces an identifier absent from the passage.'
        elif numbers(claim) - numbers(passage):
            status, reason = 'needs_review', 'Claim introduces a number absent from the passage.'
        elif scores[label] < self.threshold:
            status, reason = 'needs_review', 'No relation reaches the fixed experimental cutoff.'
        elif label == 'entailment':
            status, reason = 'model_supported', 'Model predicts that this passage supports the claim.'
        else:
            status, reason = 'not_supported', 'Model predicts contradiction or insufficient information; do not present this passage as support.'
        result = {**base, 'status': status, 'reason': reason, 'scores': scores, 'predicted_relation': label}
        return result

    def check(self, passage, claim):
        # Validate and score the complete context first. Long inputs still abstain
        # instead of silently selecting a convenient subset.
        full = self._score_passage(passage, claim)
        if full['scores'] is None:
            return full
        groups = components(passage)
        risks = binding_risks(passage)
        all_spans = sentence_spans(passage)
        ambiguous_starts = {all_spans[item['sentence']]['start'] for item in risks['ambiguous_references']}
        if len(groups) == 1:
            # A linked component may span messages. Shared anchors connect
            # evidence, but never replace the model's support decision.
            full['evidence_components'] = groups
            if full['status'] == 'model_supported' and ambiguous_starts:
                return {**full, 'status': 'needs_review', 'reason': 'A short subject reference has multiple possible antecedents.', 'binding_risks': risks}
            if full['status'] == 'model_supported':
                full['supporting_spans'] = groups[0]['spans']
                full['support_method'] = 'linked_component' if len(groups[0]['spans']) > 1 else 'single_sentence'
            return full
        if len(groups) > 32:
            return {**full, 'status': 'needs_review', 'reason': 'Too many unrelated evidence components for bounded checking.'}
        supported = []
        trace = []
        for group in groups:
            premise = '\n\n'.join(span['text'] for span in group['spans'])
            verdict = self._score_passage(premise, claim)
            if verdict['status'] == 'model_supported' and any(span['start'] in ambiguous_starts for span in group['spans']):
                verdict = {**verdict, 'status': 'needs_review', 'reason': 'Ambiguous subject reference cannot establish the proposed binding.'}
            trace.append({'spans': group['spans'], 'links': group['links'], 'status': verdict['status'], 'scores': verdict['scores']})
            if verdict['status'] == 'model_supported':
                supported.append((group, verdict))
        if supported:
            # Do not rescue a local statement against a confident whole-context
            # rejection; scope, negation or supersession may live elsewhere.
            scores = full['scores']
            if max(scores['contradiction'], scores['neutral']) >= self.threshold:
                return {**full, 'status': 'needs_review', 'reason': 'Local support conflicts with a confident whole-context rejection.', 'component_checks': trace}
            group, verdict = supported[0]
            return {**full, 'status': 'model_supported', 'reason': 'A source-bound evidence component supports the claim at the fixed cutoff.',
                    'support_scores': verdict['scores'], 'supporting_spans': group['spans'], 'support_method': 'linked_component' if len(group['spans']) > 1 else 'single_sentence', 'component_checks': trace}
        return {**full, 'status': 'needs_review' if full['status'] == 'model_supported' else full['status'],
                'reason': 'No individually linked evidence component supports the claim.' if full['status'] == 'model_supported' else full['reason'], 'component_checks': trace}



@lru_cache(maxsize=1)
def checker(directory, threshold=.90):
    # Only verified public weights are shared; no passage/query cache.
    return SupportChecker(directory, threshold)


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--threshold', type=float, default=.90)
    parser.add_argument('--input', type=Path, required=True, help='JSON containing passage and one atomic claim')
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    if not isinstance(data, dict) or set(data) != {'passage', 'claim'}:
        parser.error('Input must contain only passage and claim')
    result = checker(str(args.model.resolve()), args.threshold).check(data['passage'], data['claim'])
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
