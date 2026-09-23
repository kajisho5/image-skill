# imagemagick-skill execution contract

`npx imagemagick-skill contract --json` (or `python3 scripts/_contract.py contract --json`)
prints a machine-readable description of this skill: every tool, its arguments, what its
`--json` output contains, and the rules every tool follows. This page is the same
contract for people. Its [Tools](#tools) section is generated from the JSON (see
`.github/scripts/contract_md.py`) and CI fails if the two differ, so it cannot drift from
the scripts.

## Versions

| Field | Meaning |
| --- | --- |
| `contract_version` | shape of this document (`1.0`) |
| `skill.version` | the npm / package.json version (`0.3.0`) |

`version` and `name` at the top level of the JSON repeat `skill.version` and `skill.id`;
they predate `skill` and stay for compatibility.

## Where the schemas come from

Each tool's `input_schema`, and the older `required_args` / `optional_args` lists, are
derived at run time from that script's own `build_parser()`: argument names, types,
choices, defaults, which are required, which are positional. Only what a parser cannot
state is written by hand in `TOOL_META` (`scripts/_contract.py`): the description, `role`,
`backends`, `verify`, and the `output_schema`. Adding a flag to a script therefore updates
the contract with no second edit; a script with no `TOOL_META` entry fails the tests.

## Invocation

Every tool is `python3 scripts/<tool>.py ARGS...`, run with an argv list, never through a
shell. Arguments map one-to-one from `input_schema`: a property whose `cli` is
`"positional"` is passed by position in `input_schema.positional` order; any other property
is passed with its flag (`cli` lists the spellings). Booleans are flags without a value.
`batch`'s `tool_args` go after a literal `--`.

## Result shapes

Every tool prints exactly one JSON object with `--json`.

| Case | Shape |
| --- | --- |
| success | `{"ok": true, ...}` with the keys in the tool's `output_schema` |
| failure | `{"ok": false, "reason": "..."}`, exit status 1 - including a malformed invocation (missing or invalid flags), which never falls back to argparse's usage text |
| `--dry-run` | `{"ok": true, "dry_run": true, "would_run": [argv...]}` - nothing is written |

A broken, empty or mislabeled output is a failure, never `ok: true`: tools that write a
file re-read it, and a file whose real format differs from its extension (ImageMagick can
exit 0 while writing the input's format when it has no encoder for the requested one) is
deleted and reported as `ok: false`.

## Guarantees

| Field (`execution`) | Value | Meaning |
| --- | --- | --- |
| `shell` | `false` | no command is built as a shell string |
| `network` | `false` | no tool makes a network call |
| `input_mutation` | `false` | no tool writes to its input; `-o` must differ from it |
| `arbitrary_executables` | `false` | only the named script, `magick` and (macOS) `sips` run |

Every tool also reports `mutates_input: false`. An existing output is refused unless
`--overwrite` is given. `mogrify` is never used.

## Backends

`backends` lists what can run a tool: `magick` (ImageMagick 7's `magick`, or a
compatible command) and/or `sips` (macOS). `requires_magick: true` means there is no
`sips` path. `npx imagemagick-skill doctor --json` reports, per tool, whether this machine
can run it (`tools.<name>.usable`) and which backend it would use.

## Stability

Within 0.x, tool names, argument names and the keys listed in each `output_schema` are
kept; new optional arguments and new output keys may be added. Removing or renaming any of
them is a breaking change and ships only in a deliberate, hand-made version bump - release
automation refuses to choose a major version by itself.

## Example

```json
{
  "ok": true,
  "name": "imagemagick-skill",
  "contract_version": "1.0",
  "skill": {"id": "imagemagick-skill", "version": "0.3.0", "execution_mode": "local"},
  "execution": {"shell": false, "network": false, "input_mutation": false, "arbitrary_executables": false},
  "tools": [{"name": "probe", "role": "analysis", "backends": ["magick", "sips"], "input_schema": {"...": "..."}}]
}
```

## Tools

<!-- BEGIN GENERATED: tools (python3 .github/scripts/contract_md.py --write) -->

### `probe`

Report width, height, format, colorspace, alpha, and GPS presence as JSON.

- Script: `scripts/probe.py` · role: analysis · backends: magick, sips
- Writes a file: no · `--dry-run`: yes · `--json`: yes · verify with: -

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `width` | integer | yes |  |
| `height` | integer | yes |  |
| `format` | string | yes | backend format name, e.g. JPEG, PNG, HEIC (sips reports lowercase) |
| `colorspace` | string or null | no | null on the sips backend |
| `has_alpha` | boolean or null | no | null on the sips backend |
| `has_gps` | boolean or null | no | EXIF GPSLatitude present; null on the sips backend |
| `backend` | string: `magick` \| `sips` | yes |  |
| `note` | string | no | present when a field could not be measured |

### `convert`

Convert an image to a different format (e.g. HEIC to JPEG/PNG/WebP). Input is preserved.

- Script: `scripts/convert.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; must differ from the input, extension picks the format |
| `--quality` | integer | no |  | 0-100 encoder quality for lossy formats (JPEG/WebP) |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `backend` | string: `magick` \| `sips` | yes |  |

### `resize`

Resize an image: fit (default, no distortion), fill (crop to cover), or exact (force size).

- Script: `scripts/resize.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; must differ from the input, extension picks the format |
| `--width` | integer | yes |  | target width in pixels (the box width for fit) |
| `--height` | integer | yes |  | target height in pixels (the box height for fit) |
| `--mode` | string: `fit` \| `fill` \| `exact` | no | `"fit"` | fit: inside the box, no distortion; fill: cover the box and center-crop; exact: force the size |
| `--quality` | integer | no |  | 0-100 encoder quality for lossy formats (JPEG/WebP) |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `mode` | string: `fit` \| `fill` \| `exact` | yes |  |
| `requested` | object | yes | {width, height} in pixels |
| `actual` | object | yes | {width, height} in pixels |
| `backend` | string: `magick` \| `sips` | yes |  |

### `thumb`

Create a thumbnail sized by its longest edge, preserving aspect ratio.

- Script: `scripts/thumb.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; must differ from the input, extension picks the format |
| `--long-edge` | integer | yes |  | target size of the longer side, in pixels |
| `--quality` | integer | no |  | 0-100 encoder quality for lossy formats (JPEG/WebP) |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `long_edge` | integer | yes |  |
| `actual` | object | yes | {width, height} in pixels |
| `backend` | string: `magick` \| `sips` | yes |  |

### `strip`

Remove GPS/EXIF metadata. Applies orientation before stripping. Requires ImageMagick.

- Script: `scripts/strip.py` · role: execution · backends: magick
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`, `probe`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; must differ from the input, extension picks the format |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `has_gps` | boolean | yes | always false: a result that still has GPS is a failure |
| `backend` | string: `magick` | yes |  |

### `trim`

Trim a solid-color border. Fails instead of over-trimming. Requires ImageMagick.

- Script: `scripts/trim.py` · role: execution · backends: magick
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; must differ from the input, extension picks the format |
| `--fuzz` | number | no | `2.0` | color similarity tolerance, percent (default 2.0) |
| `--max-trim-percent` | number | no | `90.0` | fail if more than this percent of the area is removed (default 90.0) |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `original` | object | yes | {width, height} in pixels |
| `trimmed` | object | yes | {width, height} in pixels |
| `removed_percent` | number | yes |  |
| `backend` | string: `magick` | yes |  |

### `check`

Verify an output file opens, matches promised dimensions/format, and didn't overwrite the input.

- Script: `scripts/check.py` · role: verification · backends: magick, sips
- Writes a file: no · `--dry-run`: no · `--json`: yes · verify with: -

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `output` (positional) | string | yes |  | the file to check |
| `--input` | string | no |  | original input path; fails if output resolves to this same path |
| `--expect-width` | integer | no |  | fail unless the width is exactly this |
| `--expect-height` | integer | no |  | fail unless the height is exactly this |
| `--expect-max-width` | integer | no |  | fail if width exceeds this (for fit-mode results) |
| `--expect-max-height` | integer | no |  | fail if height exceeds this (for fit-mode results) |
| `--expect-format` | string | no |  | expected format, e.g. WEBP, JPEG, PNG |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `output` | string | yes |  |
| `width` | integer | yes |  |
| `height` | integer | yes |  |
| `format` | string or null | yes | read only when --expect-format is given |

### `batch`

Run one of convert/resize/thumb/strip/trim over every image in a folder.

- Script: `scripts/batch.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `tool` (positional) | string: `convert` \| `resize` \| `strip` \| `thumb` \| `trim` | yes |  | tool to run on each file |
| `-i`, `--input-dir` | string | yes |  | folder of images to read (not recursive) |
| `-o`, `--output-dir` | string | yes |  | folder to write results into; must differ from --input-dir |
| `--ext` | string | no |  | output extension for convert, e.g. webp (required for convert) |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |
| `tool_args` (after `--`) | array of string | no |  | arguments forwarded to the per-file tool, e.g. ["--width", "1200", "--height", "1200"] |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `tool` | string | yes |  |
| `count` | integer | yes |  |
| `all_ok` | boolean | yes |  |
| `results` | array | yes | one {file, output, ok, result\|reason} per input file |

<!-- END GENERATED: tools -->
