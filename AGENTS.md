# For agents working on this repository

- Runtime use of the skill is documented in `SKILL.md`; this file is for agents that
  review, audit or change the repository itself.
- **Before reporting a defect, read `docs/design-decisions.md`.** It lists behaviours
  that look like bugs but are decisions, each with its rationale and the test that pins
  it. Report one of them only if the rationale no longer holds, and say which sentence is
  wrong.
- Verify a finding against the tree at the commit you are reviewing, not against a
  summary or an older release.
- The contract (`python3 scripts/_contract.py contract --json`, `docs/contract.md`) is the
  authority on tool names, flags, output keys and dry-run semantics. README and SKILL.md
  restate it and are tested against it. Never hand-edit the generated Tools section of
  `docs/contract.md`: change the script's parser or `TOOL_META`, then run
  `python3 .github/scripts/contract_md.py --write`.
- Development rules (scope, tests, PR expectations, releasing) are in `CONTRIBUTING.md`.
