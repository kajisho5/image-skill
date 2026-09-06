# Changelog

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
