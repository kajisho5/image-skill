# Roadmap

The released version today is **0.6.0** (notes in CHANGELOG.md); **0.3.0** — the package is `imagemagick-skill` on npm (renamed
from `image-skill`, a name that belongs to another author), with a migration that removes
an old copy of this project only when it is provably ours, and `--codex` installing where
Codex actually reads skills.

"On the roadmap" does not mean "in the released package": each theme below is marked
**shipped** (in a release), or **planned**. `docs/contract.md` and `contract --json` are
the authority on what exists today.

| Version | Theme | State |
| --- | --- | --- |
| 0.1.0 | probe, convert, resize, thumb, strip, trim, check, batch; contract and doctor | shipped |
| 0.2.x | installer UX, JSON errors for bad flags, silent-format-mismatch guard, CI on Linux and macOS | shipped |
| 0.3.0 | rename to `imagemagick-skill`, legacy-install migration, Codex path | shipped |
| next | repository and release operations aligned with ffmpeg-skill: label-driven releases, argparse-derived contract, generated `docs/contract.md`, plugin manifest, evals | planned |
| next | agent-facing tools: look, compare, optimize, crop, pad, rotate, overlay, montage, adjust, icons, preset | planned |
| next | stdio MCP server derived from the contract | planned |
| next | README with reproducible demos | planned |
