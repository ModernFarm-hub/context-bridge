# Retrieval and evidence-reading workstream

Updated October 24, 2026. Alpha packaging and outside-user testing do not replace this workstream. Commercial/enterprise features remain deferred.

## Current evidence

- Original benchmark: hybrid retrieval Recall@5 100%; all 30 scenarios pass.
- Separate harder validation: Recall@5 66.7%; 13/16 scenarios pass. General accuracy above 90% has not been established.
- Development passage reading supports a question, explicit character-offset pages and record hashes. It can reject changed or revoked records while keeping original source references.
- The evaluator now follows every retrieved candidate with the same question and scores exact annotated support in the returned read passage. Failed/missing searches remain in its denominator. This is not a generative answer-quality score.

## October 24 comparison

Completed a 52-case development set and comparisons of MiniLM, BGE small and E5 small with two token-window sizes. BGE reached 100% development recall but failed negative-query rejection. E5 also failed that gate. A passage-reranker experiment was rejected for recall loss. No candidate qualified for promotion or a new frozen-validation run. See [comparison details and reproduction](MODEL-COMPARISON.md).

## Sentence-aware follow-up

Added intact sentences and adjacent sentence pairs alongside token windows. At the BGE 0.60 cutoff with 64-token windows, development retrieval and passage-support recall improved from 68.4% to 86.8%; negative-query rejection stayed 85.7%. No candidate met all gates, so validation and promotion did not proceed. A [manual labeling workflow](LABELING-QUERIES.md) now prepares reviewed personal/synthetic cases, checks exact support quotes, and freezes versioned datasets. Real-work labels remain pending user review; no private chats were collected.

## Claim-support experiment

A separate local entailment experiment now checks proposed claims against supplied source passages. It accepts 7/8 supported claims and no unsupported claims among 12 synthetic negatives after adding sentence consistency. It remains below acceptance and is not exposed in MCP or the alpha. See [claim-support methods and limits](CLAIM-SUPPORT.md). Retrieval and generated-answer evaluations remain separate.

## Acceptance remains above 90% on harder evidence

Keep the existing datasets and thresholds frozen. Do not remove hard questions or lower acceptance targets to claim success. Preserve lexical, hybrid and development reports separately. The new target includes both retrieval recall and follow-up passage-support recall at or above 90%, valid original source spans, negative-query behavior and no isolation/revocation regressions in the tested probes.

## Next engineering sequence

1. Collect a distinct development set covering paraphrases, incident escalation, rollback, long mixed-topic documents and plausible wrong-project distractors. Existing validation failures stay reserved regression checks.
2. Compare stronger local retrieval-trained embeddings and multi-scale sentence/paragraph chunks using that development set. Record each model/revision, threshold and latency. Do not calibrate thresholds on the frozen validation set.
3. Freeze the candidate, rerun both existing sets, then check an additional independently authored acceptance set. Report all results, including failures and run history; repeated reuse makes a test set less independent.
4. Add retrieval-to-read passage coverage and surrounding-message context checks. Maintain hashes/offsets so citation consistency is testable.
5. Add opt-in answer-level evaluation for claim support, completeness, conflict handling and abstention. Human-review errors and a sample of passes. No automatic paid model use or private data collection is included in this plan.

## Release separation

The downloadable 0.5.0a1 alpha remains unchanged. Passage-reading changes are in development source 0.5.1.dev1, not silently substituted into that alpha. Validate and explicitly package a new build before asking alpha users to upgrade.
