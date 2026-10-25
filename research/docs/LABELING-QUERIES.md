# Label real-work questions

The blank worksheet is at `evaluation/manual-queries/labels.json`. It has 12 question slots, eight development and four reserved for validation. It contains no captured conversations and no claimed real-world results. Work through the first three development slots first; fill all slots before freezing the full dataset.

Use harmless personal examples you can review. Copy only the original conversation excerpts needed for the question, plus plausible distractors. Keep this local worksheet in the ignored `evaluation/` directory; do not commit personal excerpts to the public repository.

## Fill each slot

- `query`: a natural question you would ask in another session, written before searching for its answer.
- `records`: source excerpts, each with a unique `id`, a source session name and original `text`. Add a similar but irrelevant excerpt when possible. For multi-session questions, add multiple records.
- `expected_evidence`: IDs of all excerpts needed to answer. Use `[]` when the supplied excerpts contain no answer. An unanswered question still needs excerpts to test false matches.
- `required_text`: map each expected ID to a short, exact supporting quote from its excerpt. Do not put your explanation or labels into the source `text`.
- `origin`: `personal` for manually selected personal-work excerpts, `synthetic` for made-up examples. Test findings such as PINE963 are synthetic.
- `reviewed_by` and `reviewed`: enter your name or alias and set `reviewed` to `true` only after checking the labels against the source.

The fields `kind`, `category` and `split` can keep their defaults. Do not select a different split after viewing model results. Keep the heldout cases out of tuning. Twelve examples are a workflow pilot, not enough to claim general 90% accuracy; expand toward at least 50–100 distinct questions with substantial negative-case coverage.

A completed **synthetic example**, for illustration only:

```json
{
  "id": "H001",
  "kind": "retrieval",
  "category": "manual-workflow",
  "split": "development",
  "origin": "synthetic",
  "reviewed_by": "your-alias",
  "reviewed": true,
  "query": "Who reviews the weekly release?",
  "records": [
    {"id": "release", "session": "release planning", "text": "The weekly release is reviewed by Maya."},
    {"id": "noise", "session": "office notes", "text": "The weekly menu is reviewed by Sam."}
  ],
  "expected_evidence": ["release"],
  "required_text": {"release": "reviewed by Maya"}
}
```

Include several question types: paraphrases, evidence from two sessions, long messages, outdated decisions, near-identical project identifiers, plausible wrong-topic matches and questions with no recorded answer. An assistant acknowledgment is not independent confirmation of a user claim. Label what the transcript actually supports.

## Check and freeze

Run from the project directory:

```sh
python3 prototype/label_queries.py validate --file evaluation/manual-queries/labels.json
python3 prototype/label_queries.py freeze --file evaluation/manual-queries/labels.json --output evaluation/manual-queries/frozen-v1
```

Validation rejects unfinished review fields, missing IDs, unsupported quotes and unlabeled answers. Freezing writes a new dataset copy and a SHA-256 manifest; it refuses to overwrite an existing destination. The manifest records the number of personal versus synthetic cases. Review is self-attested, not independently certified. If you correct a label, freeze a new version and document the correction.

## Evaluate the development subset first

Using the environment containing the optional semantic dependencies:

```sh
python prototype/evaluate.py --dataset evaluation/manual-queries/frozen-v1/dataset.json --split development --semantic-model /absolute/path/to/models/all-MiniLM-L6-v2 --output evaluation/manual-queries/development-v1
```

`--semantic-model` uses the existing MiniLM settings. For an explicitly frozen alternative configuration, use `--retrieval-config /absolute/settings.json` instead. After choosing and freezing a candidate using development cases, change `--split development` to `--split heldout` and use a new report directory. Do not change settings after seeing heldout outcomes and still call that result independent validation.

This worksheet supplies retrieval cases only. Its report's full acceptance flag may be false because access/freshness controls are not included; run the bundled original benchmark separately for those checks. Repetitions measure consistency and latency, not additional independent examples. Passage support uses exact quotes; generated-answer correctness requires separate review.
