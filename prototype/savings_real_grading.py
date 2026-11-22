# SPDX-License-Identifier: Apache-2.0
"""Formatting-only deterministic grading, amended after the 2026-11-22 pilot.

No semantic aliases or fuzzy matching. Facts JSON, when present, is authoritative;
prose cannot repair an incorrect or incomplete facts object. Fallback checks exact
required values in prose, not general truth, and is reported separately.
"""
import json
import re

AMENDMENT='2026-11-22-formatting-only'
IDENTIFIER=re.compile(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\Z')
BARE_IDENTIFIER=re.compile(r'[A-Za-z_]\w*\Z')

def normalize(value):
    if isinstance(value,bool):return 'true' if value else 'false'
    if not isinstance(value,(str,int,float)):return None
    value=str(value).strip()
    while len(value)>=2 and value[0]==value[-1] and value[0] in "`\"'":value=value[1:-1].strip()
    return value.casefold()

def equal_value(actual,reference):
    actual=normalize(actual);reference=normalize(reference)
    if actual is None or reference is None:return False
    if actual==reference:return True
    return bool(BARE_IDENTIFIER.fullmatch(reference) and IDENTIFIER.fullmatch(actual) and actual.rsplit('.',1)[-1]==reference)

def facts_object(answer):
    decoder=json.JSONDecoder()
    for match in re.finditer(r'\{',answer):
        try:obj,_=decoder.raw_decode(answer[match.start():])
        except ValueError:continue
        if isinstance(obj,dict) and isinstance(obj.get('facts'),dict):return obj['facts']
    return None

def affirmative(answer,start,end):
    # Avoid treating an explicit rejection of a value as its assertion. This
    # limited syntax check is not semantic reasoning or a contradiction grader.
    before=re.split(r'[\n;!?]',answer[max(0,start-80):start])[-1]
    after=answer[end:end+40]
    rejected_before=re.search(r"\b(?:not|never|incorrect|wrong|isn't|isn’t)\b(?:[\W]+\w+){0,3}[\W]*$",before,re.I)
    rejected_after=re.match(r"[\s`'\"*]*(?:is\s+)?(?:wrong|incorrect|isn't|isn’t|is\s+not)\b",after,re.I)
    return not (rejected_before or rejected_after)

def extract_value(answer,reference):
    reference=normalize(reference)
    if reference is None:return None
    if not re.search(r'\w',reference):
        # A comma or exclamation mark used as ordinary punctuation is not a fact.
        for match in re.finditer(r"`([^`\n]+)`|\"([^\"\n]+)\"|'([^'\n]+)'",answer):
            value=next(g for g in match.groups() if g is not None)
            if equal_value(value,reference) and affirmative(answer,*match.span()):return value
        return None
    if BARE_IDENTIFIER.fullmatch(reference):
        pattern=r'(?<![\w.])(?:[A-Za-z_]\w*\.)*'+re.escape(reference)+r'(?!\w|\.[A-Za-z_]\w*)'
    else:
        pattern=r'(?<![\w.+-])'+re.escape(reference)+r'(?![\w+-]|\.\w)'
    for match in re.finditer(pattern,answer,re.I):
        if equal_value(match.group(),reference) and affirmative(answer,*match.span()):return match.group()
    return None

def explicit_assignments(answer,key):
    label=r'[ _-]+'.join(re.escape(part) for part in key.split('_'))
    value=r'(`[^`\n]+`|"[^"\n]+"|\'[^\'\n]+\'|[^\s,;]+)'
    pattern=r'(?<!\w)[`"\']?'+label+r'[`"\']?[ \t]*(?:=|:|\bis\b|\bdefaults?[ \t]+to\b)[ \t]*'+value
    return [match.group(1) for match in re.finditer(pattern,answer,re.I)]

def fallback_value(answer,key,reference):
    expected=normalize(reference)
    assignments=explicit_assignments(answer,key)
    if assignments and expected is not None and not re.search(r'\s',expected):
        # Respect explicit field/value associations: values elsewhere cannot
        # rescue swapped fields or a wrong value asserted for this field.
        for raw in assignments:
            actual=normalize(raw)
            if actual is not None:
                if raw[:1] not in ('`', '"', "'"):actual=actual.rstrip('.,;')
                if actual.endswith('()') and BARE_IDENTIFIER.fullmatch(expected):actual=actual[:-2]
            if not equal_value(actual,reference):return None
    if expected in ('true','false') and not assignments:
        # Without field labels, mixed boolean literals cannot be assigned safely.
        opposite='false' if expected=='true' else 'true'
        if re.search(r'\b'+opposite+r'\b',answer,re.I):return None
    return extract_value(answer,reference)

def grade_details(answer,reference,final=True):
    if not final:return {'correct':False,'method':'not_final','missing_facts':list(reference)}
    facts=facts_object(answer)
    method='facts_json' if facts is not None else 'text_fallback'
    if facts is None:facts={key:fallback_value(answer,key,value) for key,value in reference.items()}
    missing=[key for key,value in reference.items() if key not in facts or not equal_value(facts[key],value)]
    return {'correct':not missing,'method':method,'missing_facts':missing}

def grade(answer,reference):return grade_details(answer,reference)['correct']
