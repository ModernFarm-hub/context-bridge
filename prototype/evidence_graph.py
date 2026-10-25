# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
"""Conservative lexical links between original sentence spans, not a proof graph."""
import re
if __package__:
    from .retrieval import STOP_WORDS, TEMPORAL
else:
    from retrieval import STOP_WORDS, TEMPORAL

FUNCTION_WORDS = STOP_WORDS | TEMPORAL | frozenset(('only', 'also', 'then', 'than', 'each', 'every', 'any', 'no', 'not', 'before', 'after', 'during', 'between', 'through', 'without', 'within', 'under', 'over', 'until', 'into', 'onto', 'per', 'past', 'despite', 'against', 'among', 'around', 'regarding', 'above', 'below', 'beside', 'near', 'inside', 'outside'))


def sentence_spans(text):
    boundaries = [0] + [match.end() for match in re.finditer(r'(?<=[.!?])\s+|\n[ \t]*\n', text)] + [len(text)]
    spans = []
    for start, end in zip(boundaries, boundaries[1:]):
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append({'start': start, 'end': end, 'text': text[start:end]})
    return spans


def anchors(text, qualified=True):
    words = re.findall(r'\b[\w]+(?:[-_][\w]+)*\b', text.casefold())
    # Shared predicates such as "approves quarterly" must not link different
    # actors. Admit a phrase only when it leads one sentence or describes a
    # directly assigned numeric value; IDs/named tokens are handled below.
    first = next((i for i, word in enumerate(words) if word not in FUNCTION_WORDS), len(words))
    result = set()
    for i, (left, right) in enumerate(zip(words, words[1:])):
        if left in FUNCTION_WORDS or right in FUNCTION_WORDS or len(left) <= 1 or len(right) <= 1:
            continue
        numeric_assignment = False
        for position in range(i + 2, min(len(words), i + 6)):
            if re.fullmatch(r'\d+(?:\.\d+)?', words[position]):
                numeric_assignment = all(word in FUNCTION_WORDS for word in words[i + 2:position])
                break
        if not qualified or i == first or numeric_assignment:
            result.add('phrase:' + left + ' ' + right)
    for word in words:
        if re.search(r'[a-zA-Z]', word) and re.search(r'\d', word):
            result.add('identifier:' + re.sub(r'[-_]', '', word))
        elif '-' in word or '_' in word:
            result.add('named-token:' + word)
    return result


def components(text):
    spans = sentence_spans(text)
    keys = [anchors(span['text']) for span in spans]
    mentions = [anchors(span['text'], qualified=False) for span in spans]
    references, _ = subject_references(spans)
    reference_edges = {(min(link['from'], link['to']), max(link['from'], link['to'])): link for link in references}
    remaining = set(range(len(spans)))
    groups = []
    while remaining:
        first = min(remaining)
        remaining.remove(first)
        members, pending, links = {first}, [first], []
        while pending:
            current = pending.pop()
            for other in sorted(remaining):
                shared = (keys[current] & mentions[other]) | (mentions[current] & keys[other])
                reference = reference_edges.get((min(current, other), max(current, other)))
                if shared or reference:
                    remaining.remove(other)
                    members.add(other)
                    pending.append(other)
                    links.append({'from': current, 'to': other, 'shared_anchors': sorted(shared | set(reference['shared_anchors'] if reference else []))})
        ordered = sorted(members)
        groups.append({'spans': [spans[i] for i in ordered], 'links': links})
    return groups


def subject_references(spans):
    """Link a short definite subject only to one earlier qualified subject."""
    pattern = re.compile(r'^\s*(the|this|that)\s+([\w-]+(?:\s+[\w-]+){0,3}?)\s+(?:is|are|was|were|has|have|had|can|could|may|might|must|will|shall)\b', re.I)
    previous, links, ambiguous = [], [], []
    for index, span in enumerate(spans):
        match = pattern.match(span['text'])
        if not match:
            continue
        phrase = tuple(match.group(2).casefold().split())
        if any(word in FUNCTION_WORDS for word in phrase):
            continue
        if len(phrase) == 1:
            matches = [(i, words) for i, words in previous if len(words) > 1 and words[-1] == phrase[0]]
            distinct = {words for _, words in matches}
            if len(distinct) == 1:
                antecedent, words = matches[-1]
                links.append({'from': antecedent, 'to': index, 'shared_anchors': ['definite-reference:' + ' '.join(words)]})
            elif len(distinct) > 1:
                ambiguous.append({'sentence': index, 'reference': phrase[0], 'candidates': sorted(' '.join(words) for words in distinct)})
        previous.append((index, phrase))
    return links, ambiguous


def binding_risks(text):
    spans = sentence_spans(text)
    _, ambiguous = subject_references(spans)
    subjects = set()
    pattern = re.compile(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+[a-z]+s\b')
    for span in spans:
        match = pattern.match(span['text'])
        if match and match.group(1).casefold() not in FUNCTION_WORDS:
            subjects.add(match.group(1))
    return {'ambiguous_references': ambiguous, 'distinct_named_subjects': sorted(subjects)}
