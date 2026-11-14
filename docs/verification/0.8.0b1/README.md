# 0.8.0b1 verification

The original 30-conversation/30-query fixture in `prototype/evals/paraphrases.json` was created before changing retrieval. At independent review request, the first query was replaced with a fresh paraphrase (it previously duplicated the public roadmap). The other 29 queries and all target conversations remain unchanged. All three modes below were re-measured on this revised fixture; each JSON report includes its SHA-256 digest. Every target has one indexed message. Queries deliberately paraphrase the title/body; they are not passed to the index or used as synonyms. Results score unique conversation IDs. Top-1 and top-5 are fractions; MRR@20 assigns zero when absent from the first 20 results.

The baseline was recomputed using 0.7.0b2 revision `4f898b8`'s implementation copied into a disposable directory with the revised fixture and benchmark harness. No active checkout or history was reset. `baseline-0.7.0b2.json` records the revision and per-query ranks. The fixture is synthetic and small; it does not establish performance on real user chats, multilingual data, long conversations, or held-out queries. No synonym list was tuned to it.

| Mode | Top-1 | Top-5 | MRR@20 |
| --- | ---: | ---: | ---: |
| 0.7.0b2 baseline | 0.0333 | 0.0333 | 0.0333 |
| 0.8 BM25 (Porter + weighted title) | 0.0333 | 0.0667 | 0.0444 |
| 0.8 hybrid (same BM25 + verified MiniLM) | 0.8667 | 0.9000 | 0.8833 |

The latest 5,000-file run indexed 104,876 messages. Historical grouping p95 was 258.91 ms; a fresh before-run measured **293.32 ms**, and the optimized run measured **132.42 ms**. Initial query was 301.48 ms and append visibility was 40.37 ms; the 300 ms target applies to steady-state p95. Exact integer match counts are now computed only for returned conversations. The FTS5 rank cursor supplies the best distinct conversations without grouping every hit through metadata JSON. These measurements cover lexical search plus refresh, not large-library vector search.

The isolated grouped-query CPU profile fell from **221 ms** to **96 ms**; post-change returned-conversation counting accounts for approximately **6 ms**. See `grouping-query-before.txt` and `grouping-query-after.txt`. The profiled query is separate from the timed latency samples.

## Codex discovery scale

200 synthetic rollout files × 5,242,880 bytes each (1,048,576,000 bytes total); five approved, 195 unapproved. Each file has real header/message shapes and a large excluded tool-output tail. The same synthetic web-library query is timed before and after approving a project:

| Measurement | Time |
| --- | ---: |
| No-Codex search p95 | 0.129 ms |
| First refresh, including classification and five-file ingestion | 108.577 ms |
| Steady-state Codex search p95 | 2.065 ms |
| Increase over baseline | **1.936 ms** |

The increase passes the +10 ms target. Steady-state performs directory/stat checks but does not open unchanged rejected files. The negative cache persists in the profile database and stores only paths, stat signatures and approval/exclusion hashes. Regression tests cover restart reuse, appends, failed and unreadable classifications, changed approvals, new approved threads and incremental ingestion. Previews use the same classifier; the JSON decoder is never called for chat lines during classification.

Reproduce from the repository root (no real chats are read):

```sh
python3 prototype/benchmark.py --codex-scale --runs 30 --output /tmp/codex-scale.json
python3 prototype/benchmark.py --files 5000 --runs 30 --output /tmp/scale.json --profile-query /tmp/grouped-query.txt
```

The Codex benchmark temporarily writes about 1 GiB of synthetic files and removes them on completion. Actual latency varies with hardware/filesystem caches.

Semantic mode remains opt-in because setup needs model/package downloads and local compute/storage. This fixture supports offering an easy semantic upgrade, not forcing it on every user. The model files total roughly 90 MB; setup prints the actual byte count. Vectors/chunks are stored only in the profile's local database. Subsequent search does not call a remote API.

From an installed source checkout:

```sh
context-bridge benchmark --paraphrases --output /tmp/bm25.json
context-bridge semantic enable --profile personal
context-bridge benchmark --paraphrases --model /absolute/path/to/all-MiniLM-L6-v2 --output /tmp/hybrid.json
context-bridge benchmark --files 5000 --runs 30 --output /tmp/scale.json
```

Each benchmark creates a disposable synthetic library, never reading personal conversations. `--model` must point to a checksum-verified MiniLM directory; it does not download models. The baseline can be rerun by using the frozen fixture/benchmark harness with revision `4f898b8`'s retrieval implementation in a disposable checkout, without changing the active checkout.

Run regression tests from the repository root:

```sh
PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
# With the optional runtime installed and local models available:
CONTEXT_BRIDGE_TEST_MODEL=/absolute/path/to/all-MiniLM-L6-v2 \
  PYTHONPATH=prototype python3 -m unittest discover -s prototype/tests -v
```

The new Codex tests create synthetic rollout files and exercise real CLI import plus real stdio search. The semantic tests check offline setup using already-verified weights, persistent backfill reuse, removal, and paraphrase recall. Dependency installation is tested with mocked installers; no new environment or internet connection is created by the default test suite.

Final local verification: **178 tests passed** with both existing local model suites enabled; the zero-dependency run passed with 27 optional model tests skipped. The installed wheel smoke test and official MCP v1 client smoke test passed, including real stdio search/read, removal and snapshot pruning. Wheel/sdist payload checks passed. These are local macOS results; no GitHub CI run, tag, push or publication was performed.

Conversation grouping does not change the benchmark scoring: it already deduplicates conversation IDs before computing ranks. The new crowding regression uses ten matching records in one conversation plus four other conversations, and separately checks 260 matches, temporal queries, hybrid fusion, real stdio Source lines and retrieval-mode reporting. Installer failures are simulated without accessing PyPI; explicit source recovery and the pip upgrade order are tested.
