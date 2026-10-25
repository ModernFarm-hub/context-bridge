# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Context Bridge contributors.
import json
import hashlib
from pathlib import Path
from datetime import datetime,timezone
import argparse
if __package__:
    from .evaluate import run, render
else:
    from evaluate import run, render

parser = argparse.ArgumentParser(description='Compare pinned local models on development data, freeze a candidate, then validate it.')
parser.add_argument('--models-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--sentence-chunks', action='store_true', help='Add intact sentences and adjacent pairs to token windows')
parser.add_argument('--bge-only', action='store_true')
parser.add_argument('--e5-only', action='store_true', help='Compare the additional E5 model after the first two-model experiment')
parser.add_argument('--gate-lexical', action='store_true')
args = parser.parse_args()
source = Path(__file__).resolve().parent
out = args.output.resolve()
if out.exists() and any(out.iterdir()):
    parser.error('Choose an empty output directory to preserve earlier results')
out.mkdir(parents=True, exist_ok=True)
dev = json.loads((source / 'evals/model-selection-dev.json').read_text())
results=[]
grid = [('e5-small-v2', [.76, .80, .84])] if args.e5_only else [('all-MiniLM-L6-v2',[.25,.30,.35]),('bge-small-en-v1.5',[.40,.50,.60])]
if args.bge_only:
 grid = [('bge-small-en-v1.5', [.40, .50, .60])]
for name,thresholds in grid:
 for window in [64,200]:
  for threshold in thresholds:
   tag=f'{name}-w{window}-t{threshold}'
   settings=dict(mode='hybrid',model_directory=str(args.models_root.resolve()/name),token_window=window,minimum_similarity=threshold,gate_lexical=args.gate_lexical,sentence_chunks=args.sentence_chunks)
   report=run(dev,repetitions=1,retrieval_settings=settings)
   (out/(tag+'.json')).write_text(json.dumps(report,indent=2)+'\n')
   item=dict(tag=tag,settings=settings,summary=report['summary'],passing_cases=report['passing_cases'], controls_pass=report['acceptance_checks']['all_controls_pass'])
   results.append(item)
   print(json.dumps(item),flush=True)
(out/'development-grid.json').write_text(json.dumps(results,indent=2)+'\n')
# Selection fixed before validation: negative cases and controls first, then
# minimum retrieval/read recall, precision, and smaller token window as tie-break.
def score(r):
 s=r['summary']
 return (r['controls_pass'] and s['negative_case_pass_rate']==1 and s['read_span_validity']==1 and s['provenance_locator_validity']==1 and s['read_errors']==0,
         min(s['macro_recall_at_5'] or 0,s['reading_recall_at_5'] or 0),s['macro_precision_at_5'] or 0,-r['settings']['token_window'])
best=max(results,key=score)
if not score(best)[0] or score(best)[1] < .90:
 (out/'selection.json').write_text(json.dumps({'status': 'no_qualifying_candidate', 'validation_run': False, 'best': best, 'reason': 'Candidate must pass all controls and negatives, preserve source spans, and reach 90% retrieval and read recall.'}, indent=2)+'\n')
 print('NO QUALIFYING DEVELOPMENT CANDIDATE; validation not run',flush=True)
 raise SystemExit(1)
freeze={'created_at':datetime.now(timezone.utc).isoformat(),'selection_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'selection_rule':'controls and negatives, minimum retrieval/read recall, precision, smaller window','development_sha256':hashlib.sha256(json.dumps(dev,sort_keys=True).encode()).hexdigest(),'candidate':best,'validation_datasets':{name:hashlib.sha256((source/'evals'/name).read_bytes()).hexdigest() for name in ['scenarios.json','semantic-validation.json']}}
(out/'candidate-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
(out/'selected-settings.json').write_text(json.dumps(best['settings'],indent=2)+'\n')
print('FROZEN '+best['tag'],flush=True)
for name,filename in [('original','scenarios.json'),('validation','semantic-validation.json')]:
 report=run(json.loads((source/'evals'/filename).read_text()),repetitions=3,retrieval_settings=best['settings'])
 folder=out/name;folder.mkdir(exist_ok=True)
 (folder/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 (folder/'report.html').write_text(render(report))
 print(name+' '+json.dumps(report['summary']),flush=True)
