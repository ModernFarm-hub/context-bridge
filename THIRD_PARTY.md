# Third-party components

The Apache-2.0 declaration covers original Context Bridge source. It does not relicense dependencies, model weights, client software, or provider services.

| Component | Use | Upstream license / source |
| --- | --- | --- |
| ONNX Runtime | Optional local model inference | MIT; https://github.com/microsoft/onnxruntime |
| Hugging Face Tokenizers | Optional local tokenization | Apache-2.0; https://github.com/huggingface/tokenizers |
| NumPy | Optional local vector operations | BSD-3-Clause; https://github.com/numpy/numpy |
| nli-deberta-v3-base | Optional experimental local claim-support inference | Apache-2.0 per upstream model card; https://huggingface.co/cross-encoder/nli-deberta-v3-base |
| nli-MiniLM2-L6-H768 | Experimental local claim-support inference | Apache-2.0 per upstream model card; https://huggingface.co/cross-encoder/nli-MiniLM2-L6-H768 |
| e5-small-v2 | Optional comparison model | MIT per upstream model card; https://huggingface.co/intfloat/e5-small-v2 |
| bge-small-en-v1.5 | Optional comparison model | MIT per upstream model card; https://huggingface.co/BAAI/bge-small-en-v1.5 |
| all-MiniLM-L6-v2 | Optional downloaded embedding model | Apache-2.0 per upstream model card; https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 |

`prototype/requirements-semantic-lock.txt` records the tested optional environment, including transitive packages. Each retains its own license. Model downloads are pinned and verified by `setup_semantic.py`; the upstream model card is retained beside downloaded weights. Model files and the virtual environment are local setup assets, not included in the intended source distribution.

No competitor implementation was vendored into the prototype. Code snapshots under the ignored evaluation directory are earlier versions of this project's own implementation. Before distributing binary installers or bundling model/dependency assets, produce the corresponding complete dependency notice/license inventory; this source-preparation note is not that audit.

Claude Code and any other configured AI client are external software with their own terms and billing. An MCP connection does not transfer ownership of their code or change their data-handling policies. No endorsement by these vendors is implied.
