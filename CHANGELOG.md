# Changelog

## Unreleased

Still `0.1.0` - not bumped yet; changes below are additive/fixes except where marked.

- **Breaking:** `bin/cli.js` replaced by `bin/install.js` with a new install
  UX: default target is now global (`~/.claude/skills/image-skill`), plus
  `--cursor`, `--codex`, `--all`, `--dir <parent>`, `--project`, and
  `--uninstall`. Writing `.cursor/rules/*.mdc` and appending to `AGENTS.md`
  is removed entirely in favor of real `~/.cursor/skills/` and
  `~/.codex/skills/` copies. Reinstalling now wipes the target directory
  first so no stale scripts survive an upgrade. A missing backend prints a
  warning with the same install guidance as the README.
- Fixed `resize.py`'s sips `fit` mode: it used to size only by the longer
  edge (`sips -Z`), which could overflow the other dimension on a
  non-square box. It now computes the proportional box-fit size itself and
  asks sips for that exact size, matching magick's guarantee that neither
  dimension exceeds the requested box.
- Fixed a design gap present since the initial release: a malformed
  invocation (missing/invalid flags) used to bypass the `ok:false`/`--json`
  contract entirely, printing argparse's raw usage text and exiting 2. All
  scripts (including `batch.py`'s per-file re-use of another tool's parser)
  now report this the same way as any other failure - and a bad per-file
  argument in a batch run is recorded as that one file failing instead of
  aborting the whole batch.
- `_contract.py`'s reported `version` now reads `package.json` instead of a
  second hardcoded version string, so the two can no longer drift apart.
- Doc fixes: `SKILL.md` no longer claims `check.py` supports `--dry-run`
  (it doesn't - it writes nothing).

## 0.1.0

Initial release.

- `probe`, `convert`, `resize`, `thumb`, `strip`, `trim`, `check`, `batch`
- `_contract.py` with `contract` (machine-readable tool spec) and `doctor`
  (environment check) subcommands
- ImageMagick (`magick`) as the primary backend; macOS `sips` as a partial
  fallback for `convert`/`resize`/`thumb`
- `npx image-skill` installer for Claude Code, Cursor, and Codex
- unittest suite covering overwrite protection, fit-resize aspect ratio,
  GPS stripping, border trim, and doctor's no-backend/sips-only cases
