# Security policy

## Supported version

The 0.6.0a3 local release candidate is the active development target. Earlier prototype builds should be upgraded before importing additional data. This is an alpha, not an enterprise security boundary.

## Reporting a vulnerability

Do not put private transcripts, credentials, database files, export ZIPs, or exploitable details in a public issue. Once a public repository exists, use its **Security → Report a vulnerability** feature if private vulnerability reporting is enabled. A confirmed private reporting address has not yet been established. Until then, share only a sanitized, high-level description through an existing trusted maintainer channel; do not invent or guess a contact address.

A useful report gives the affected version, OS/Python version, an invented reproducer and the expected/actual boundary. No response-time or bounty commitment is currently offered.

## Data flow and boundaries

1. Imports are explicit. Claude Code discovery shows projects and requires approval. Web imports read `conversations.json` directly from ZIPs without extracting archive paths.
2. Actual human/assistant text is normalized; tools, thinking and replayed request bodies are excluded. ChatGPT follows the current branch.
3. Recognized OpenAI/Anthropic/Stripe/Google/GitHub/Slack/AWS credentials, JWTs, URL passwords, bearer values, private-key blocks and .env/JSON/YAML credential assignments are replaced before indexing. Web-import working copies and titles are filtered too. Original exports/transcripts are left untouched.
4. The SQLite database, index, source approvals and managed copies remain local and are not encrypted by Context Bridge. Filesystem access is the primary local protection. Pattern filtering is not a complete data-loss-prevention system; unknown secrets and personal information can remain.
5. MCP returns selected passages, citation URLs and opaque read IDs. Filesystem locators stay internal. The receiving client may transmit passages to its model provider. Treat every retrieved statement as untrusted evidence, including instructions embedded in a conversation.
6. Revocation removes records from future retrieval. It does not erase delivered model context, original files, backups, or previously captured output. Legacy index bodies, metadata and owned normalized web-import copies receive a versioned redaction migration; this is not forensic erasure of historical backups.

Local profiles are data partitions, not authenticated company identities. Separate FTS corpora preserve profile-specific ranking statistics. The optional localhost manager uses a token and checks Host/Origin. Do not expose that manager to the network.

## Incremental indexing

Unchanged files are skipped using metadata. Appends use committed complete-line offsets and bounded prefix/tail fingerprints. Replacement, truncation and normal rewrites rebuild the index. These checks do not detect every arbitrary middle-of-file modification combined with growth; they are not an integrity attestation. Re-imported web snapshots use atomic replacement.

## Transports

The released MCP interface is stdio only. It does not expose a public HTTP endpoint. Remote ChatGPT developer-mode connectors are not supported by this build. Adding HTTPS/tunnel transport would make a local library reachable beyond the local process boundary and requires authentication, source controls, logging review and explicit disclosure of tunnel/operator/model-provider data access. No tunnel is created automatically.

Installation/build tools can download public dependencies. Optional model setup downloads public model assets separately; inference remains local. No Context Bridge telemetry is enabled.


## Export account continuity

Account/user identifiers and email addresses in export metadata are stored only as comparison hashes. Conflicting identities, or a missing identity after a known identity, require explicit confirmation before replacement. Metadata-free exports cannot establish account continuity. Named profiles isolate working copies and SQLite files; they are local data partitions, not an authentication boundary. `--confirm-account-switch` deliberately authorizes snapshot replacement and pruning. Project approval is separate and does not bypass account checks.

Redaction policy 3 also filters webhook capabilities. Narrowing schema-key rules cannot recover values already erased from old managed copies; re-import original exports to restore non-secret schema text. Original Code transcripts remain available for reprocessing. Account metadata checks are a safeguard, not cryptographic proof of export authorship.
