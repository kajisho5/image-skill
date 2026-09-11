# Changelog

## 0.2.0

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
- Added GitHub Actions CI (`.github/workflows/test.yml`): the test suite now
  runs on every push/PR against Ubuntu with and without ImageMagick, and on
  macOS - the first time the sips-only code paths have actually executed
  anywhere rather than being validated by arithmetic/mocking alone. A
  separate job exercises every `bin/install.js` target end to end.
- Fixed a real, verified correctness bug found by testing against an actual
  HEIC photo: when the local `magick` build has no *encode* delegate for a
  target format (e.g. HEIC read-only, no libheif encoder), `magick` can exit
  0 while silently writing the *input* format's bytes under the requested
  output name - a single stderr warning, no error. `convert`/`resize`/
  `thumb`/`strip`/`trim` now verify the output's actual format matches its
  extension right after writing it, and remove + fail (`ok:false`) instead of
  reporting success for a mislabeled file.
- `doctor`'s `heic`/`webp` fields now parse ImageMagick's actual read/write
  mode flags (e.g. `r--` vs `rw+`) instead of just checking whether the
  format's name appears in `magick -list format` at all - the previous check
  couldn't tell a read-only HEIC delegate from a fully working one. Both now
  report `read`/`write` explicitly, with `fix` guidance when write is
  missing.
- New tests: a real downloaded HEIC sample (not committed - see below) was
  run through the full probe/convert/resize/thumb/strip/check pipeline by
  hand to find the bug above; a dynamically-generated HEIC round-trip test
  (`tests/test_heic_roundtrip.py`) now runs automatically wherever a real
  backend can write HEIC (e.g. macOS `sips` in CI), skipping everywhere else
  - no binary fixture is committed to the repo.

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
