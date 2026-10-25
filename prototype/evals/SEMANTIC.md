# Optional local semantic retrieval

The installed alpha defaults to keyword search. Semantic mode requires the optional dependencies and the pinned public model download. No conversation content is sent during setup; only public packages and model files are downloaded.

## Install and enable

When installing from the extracted source directory:

```sh
.venv/bin/python -m pip install '.[semantic]'
.venv/bin/context-bridge download-model
.venv/bin/context-bridge semantic
```

For a wheel installation, use the wheel path with its extra, e.g. `python -m pip install '/path/to/context_bridge_local-0.5.0a1-py3-none-any.whl[semantic]'` in the same virtual environment. Open a fresh reader afterward. Existing source approvals are unchanged.

`context-bridge paths` shows the data directory. On macOS the model defaults to `~/Library/Application Support/ContextBridge/models/all-MiniLM-L6-v2`. An absolute `CONTEXT_BRIDGE_HOME` override changes this base. `download-model --directory` and `semantic --model` permit explicit model paths. Inference never downloads assets automatically.

## Evaluate

After activating your virtual environment:

```sh
context-bridge evaluate
context-bridge evaluate --semantic-model "$HOME/Library/Application Support/ContextBridge/models/all-MiniLM-L6-v2" --fail-on-threshold
```

The first command runs lexical mode. Evaluation uses only synthetic fixtures, not your manager history. Reports default to the app data directory under `reports/latest`; set `--output` to keep comparison runs separately. For a custom state home, use the model path shown by `context-bridge paths`.

Use `context-bridge evaluate --validation` for the separate bundled set, adding `--semantic-model` for hybrid mode. Source developers can also select `prototype/evals/semantic-validation.json` with `--dataset`. Installed packages include those same fixtures under the package's `evals` directory. The original 30 scenarios scored 100% Recall@5 in hybrid mode. The separate validation set scored 66.7%; its three misses are retained. No thresholds were tuned against that new set. Small synthetic scores do not establish general production accuracy.

## Disable

```sh
context-bridge semantic --disable
```

Open a fresh reader. Data approvals remain unchanged. Downloaded model files are retained. Configured interpreter/model paths must still exist; reinstalling or moving the virtual environment requires reconfiguring semantic mode.

## Implementation and limits

Model: [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, Apache-2.0 per upstream model card. Setup verifies pinned upstream file digests. Local ONNX inference uses attention-mask mean pooling and L2 normalization. Token-offset chunks prevent late passages being silently truncated. Public model files total approximately 91 MB, plus optional runtime dependencies.

The similarity threshold is 0.35, calibrated on the development subset before running separate validation. Rank fusion preserves lexical matches and admits qualified semantic matches. Exact alphanumeric IDs are guarded. No scenario-specific synonyms were added. Similarity is not a probability of truth.

SQL owner filtering precedes embedding. Conversation chunks and vectors are cached per owner instance in memory; only public model weights are shared. Changed, missing and revoked records are withdrawn before subsequent search results. This is not secure memory erasure or recall of answers already delivered. No persistent vector index, background ingestion queue or production-scale load test is implemented.

Generated reader configs set offline/telemetry flags; ONNX telemetry is disabled. Local model tests block common Python network paths. These are engineering checks, not an independent security audit. Selected tool results still enter your configured AI client, which may use a cloud model.

## Source test suite

From `prototype/`, with optional dependencies installed:

```sh
CONTEXT_BRIDGE_TEST_MODEL="/absolute/path/to/all-MiniLM-L6-v2" TOKENIZERS_PARALLELISM=false python -m unittest discover -s tests -v
```

Tests requiring model assets are explicitly skipped without that variable. The tested macOS environment passed all 46 tests with model assets enabled. Other operating systems and Python versions require separate validation. No generative answer-quality evaluation is included.
