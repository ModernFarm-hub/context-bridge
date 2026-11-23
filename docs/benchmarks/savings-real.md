# Does reusing past AI research save tokens?

**Short answer: not for quick documentation lookups.** In a pre-registered benchmark, reusing past sessions used **84% more tokens** than researching again, with **no loss in accuracy** and safe handling of outdated answers.

## Result

Forty frozen tasks over public Python 3.13/3.14 documentation; three repetitions per arm; claude-sonnet-5-5; run 2026-11-22. A task "loses" when reuse used more tokens than fresh research.

| Group | Tasks | Fewer tokens with reuse (95% interval) | Accuracy: fresh research | Accuracy: reuse | Decision accuracy |
|---|---:|---|---:|---:|---:|
| **Overall** | 40 | **−84% (−108% to −64%)** | 93.3% | 97.5% | 4% |
| Same question | 10 | −43% (−56% to −26%) | 90% | 100% | 0% |
| Paraphrase | 10 | −89% (−158% to −42%) | 100% | 100% | 0% |
| Related question | 10 | −87% (−117% to −54%) | 83% | 90% | 17% |
| Stale answer | 10 | −119% (−160% to −81%) | 100% | 100% | 0% |

Negative values mean reuse used more tokens. Pre-registered checks: accuracy non-inferiority (5-point margin) **passed**; stale-answer safety **passed**; the savings hypothesis **failed**, so no savings claim is made. All 40 tasks completed with no errors, refusals, truncation or call-cap hits. The agent guide's decision line appeared in 55% of reuse answers.

**Why reuse lost:** fresh research was cheap: a median of 2 model calls and about 5,400 tokens per session (range 2–6 calls). Searching and reading past sessions, plus the guide's instructions, cost more than simply looking the answer up again. This benchmark says nothing about long, expensive research, which remains untested.

## How it was run

- **Pre-registration:** [PREREGISTRATION.md](../../prototype/evals/savings-real/PREREGISTRATION.md), frozen in commit `8f23796` before any paid run. Two dated amendments were added before the confirmatory results were seen: formatting-only grading fixes found by the pilot (commit `0d0bec6`), and an outcome-blind transport amendment after a network timeout interrupted the run (commit `5729cb9`). Tasks, labels, corpus, arms and analysis never changed.
- **Interruption:** one request timed out after being sent. It was abandoned on the record, its reserved $0.07 stays charged, and it was re-sent once; the run then resumed from its journal.
- **Cost:** $5.14 for the confirmatory run (cap $10), $0.29 for the pilot. Personal API account; no employer, client or private data.
- **Protocol and limits:** [savings-real-guide.md](savings-real-guide.md).

## Data

- [Confirmatory run: generated report, summary, per-session results, every recorded call, transcripts and logs](savings-real-full-2026-11-22/)
- [Pilot (5 tasks)](savings-real-pilot-2026-11-22/) and [its formatting-only re-grade](savings-real-pilot-2026-11-22-regrade/)
- [Fake-provider verification report](savings-real-fake.md), which is harness testing only, not a result

The disposable search library each run builds is not published because it contains local file paths; it can be rebuilt from the published transcripts.

## Earlier small runs

Three earlier live runs (5 synthetic tasks each) showed the same pattern with the original guide: reuse cost 13–31% more when the model re-verified everything, and a trusted reuse saved 74–82% in a few cases. See [savings.md](savings.md).
