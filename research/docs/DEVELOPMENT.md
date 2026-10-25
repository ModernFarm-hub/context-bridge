# Dated development record

Recorded October 24, 2026. Dates below follow the user's America/Chicago calendar context.

## October 23, 2026

- Defined the cross-session context retrieval problem and created the project brief.
- Built original local Python/SQLite capture and retrieval code with synthetic fixtures.
- Added an MCP interface, explicit session approval and revocation, source references and a local manager prototype.
- User-run Claude Code smoke tests recovered manually seeded findings from approved sessions and demonstrated revocation.
- Created an author-generated synthetic retrieval/control benchmark and preserved the lexical baseline.

## October 24, 2026

- Added owner-scoped lexical ranking and passage selection, then local ONNX embedding retrieval with pinned public model assets.
- Original synthetic benchmark reached 30/30 scenarios; a separately authored 16-scenario set passed 13/16 and remains below its recall target.
- Ran 42 engineering tests with optional model tests enabled.
- Selected Apache-2.0 for original project source, prepared license/notice files, and narrowed the public README to the local MVP.
- No public GitHub repository, registry submission, social post, or employer notice was created by these preparation steps.

## Methods and boundaries

Implementation was developed collaboratively with an AI assistant using this workspace. Evaluation cases are invented, checked into `prototype/evals/`, and do not require private conversations or API credentials. Public documentation informed model and protocol integration; original project code is kept separate from downloaded dependencies and model files.

This is a development log, not evidence of who owns the hardware/accounts, whether development occurred outside employment hours, or whether an employer has approved outside activities. Those facts were not independently established. The benchmark does not audit all user-selected live conversations.

The current source tree is an unpublished workspace prototype. Portable state storage, distribution packaging and a clean outside-user installation remain release work. Local identity filters are test mechanisms, not enterprise identity controls.

## Portable alpha preparation — October 24, 2026

The project direction is now open source first; commercialization is deferred until adoption demonstrates demand. The user stated that no employer notice is needed; none was sent.

Added an installable Python package and `context-bridge` command, predictable per-user state paths, optional local semantic dependencies, and explicit same-computer state migration. The original workspace state is not migrated automatically. Built source/wheel artifacts and tested installation outside the checkout. Earlier notes about lack of packaging describe the preceding prototype stage, not the current alpha. Publication, signed installation, cross-platform validation and independent outside-user testing remain pending.


## Passage-reading development — October 24, 2026

Resumed the interrupted edits and verified question-focused passage selection, paginated original text, changed-record detection and revocation during paging. Added a separate follow-up read-support metric without changing the frozen scenario data or original retrieval-success definition. Fifty-five engineering tests pass with the local model enabled. This is development source 0.5.1.dev1; existing 0.5.0a1 release files were not replaced. The harder validation remains below target, so distribution work does not close the retrieval roadmap.
