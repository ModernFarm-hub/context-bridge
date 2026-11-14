# Roadmap

Last updated: 2026-11-14. Priorities come from public testing and user questions; they can change.

## 0.8: find what you meant, and include ChatGPT desktop

**Paraphrase recall.** A personal-library test of 0.7.0b2 found the intended conversation for only 1 of 6 queries that were worded differently from the original chat (for example, "tips for getting into taking pictures professionally" missed a chat titled "Starting as a Photographer"). BM25 keyword search needs the original words.

- A synthetic paraphrase benchmark (top-1, top-5, MRR), with the 0.7.0b2 baseline recorded before changes.
- Dependency-free improvements: Porter stemming in FTS5, title weighting, and only benchmark-proven expansions.
- `context_search` guidance so clients try several phrasings when the first search is weak.
- One command to enable optional offline hybrid search (BM25 plus a local embedding model), with benchmark numbers for both modes.

**ChatGPT desktop (Codex) source.** The ChatGPT desktop app stores threads locally in `~/.codex/sessions`. A `codex` provider will index user and assistant messages from approved project folders, with the same consent, discovery, exclusion and redaction rules as Claude Code. ChatGPT desktop threads will then need no export. Citations open the thread in the app.

## Later

- Better titles for untitled ("New chat") ChatGPT conversations.
- Filters: provider, date range and project.
- More local sources, such as Cursor and Gemini CLI.
- `context_save`: explicitly save a decision from the current session as a searchable, cited note.
- One-click installs: a Claude Desktop extension and Homebrew.

## Not planned

- Scraping chatgpt.com or claude.ai. Web history arrives only through official exports until providers offer a history API.
- A hosted or cloud version. Conversations stay on the user's machine.
