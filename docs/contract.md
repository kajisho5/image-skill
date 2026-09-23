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

### `look`

Make a labelled preview sheet (or a before/after pair) of images so the agent can look at them.

- Script: `scripts/look.py` · role: verification · backends: magick
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: -

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `inputs` (positional) | array of string | yes |  | images to preview (only read; first frame of multi-frame files) |
| `-o`, `--output` | string | yes |  | sheet to write (e.g. look.png); must not be one of the inputs |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |
| `--tile` | string | no | `320` | longest side of each preview tile in pixels (default 320) |
| `--cols` | string | no |  | tiles per row (default: up to 4) |
| `--pair` | boolean | no |  | exactly two inputs shown side by side as before / after |
| `--no-labels` | boolean | no |  | omit the file name / size / format caption under each tile |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `output` | string | yes |  |
| `mode` | string: `grid` \| `pair` | yes |  |
| `inputs` | array | yes | per input: {path, width, height, format, has_alpha} |
| `tile` | integer | yes |  |
| `cols` | integer | yes |  |
| `rows` | integer | yes |  |
| `labels` | boolean | yes |  |
| `actual` | object | yes | {width, height} in pixels |
| `backend` | string: `magick` | yes |  |
| `note` | string | no | present when labels were dropped (no font) |

### `compare`

Measure the difference between two same-size images (SSIM, PSNR, changed pixels), optionally write a heatmap, optionally fail below an SSIM threshold.

- Script: `scripts/compare.py` · role: verification · backends: magick
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `look`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `a` (positional) | string | yes |  | first image, e.g. the original or the expected result (only read) |
| `b` (positional) | string | yes |  | second image, e.g. the edited or the actual result (only read) |
| `-o`, `--output` | string | no |  | optional: write a difference heatmap here (dimmed first image, changes from blue to yellow) |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |
| `--fuzz` | number | no |  | percent of full scale a channel may differ by and still count as unchanged in diff_ratio (default 0: exact) |
| `--fail-below` | number | no |  | report ok:false (exit 1) when SSIM is below this value (0-1), metrics still included |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `a` | string | yes |  |
| `b` | string | yes |  |
| `width` | integer | yes |  |
| `height` | integer | yes |  |
| `identical` | boolean | yes |  |
| `ssim` | number | yes | 0-1, 1 = identical; luma, 7x7 window, after downsampling by ssim_scale |
| `ssim_scale` | integer | yes | downsampling factor applied before SSIM (shorter side ~256) |
| `psnr_db` | number or null | yes | null when the images are identical |
| `diff_ratio` | number | yes | share of pixels whose largest channel difference exceeds --fuzz |
| `diff_pixels` | integer | yes |  |
| `fuzz` | number | yes |  |
| `output` | string | no | the heatmap, when -o was given |
| `fail_below` | number | no |  |
| `passed` | boolean | no |  |
| `backend` | string: `magick` | yes |  |

### `optimize`

Re-encode an image to fit a file-size budget (--max-kb) without changing its dimensions; fails with the smallest size reached when it cannot.

- Script: `scripts/optimize.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`, `look`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; its extension picks the format (jpg, webp, avif, heic, png) |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |
| `--max-kb` | number | yes |  | size budget in kilobytes (1 KB = 1000 bytes) |
| `--min-quality` | integer | no | `40` | lowest quality the search may use, 1-100 (default 40) |
| `--max-quality` | integer | no | `95` | highest quality the search may use, 1-100 (default 95) |
| `--strip` | boolean | no |  | also drop metadata (EXIF/GPS/ICC comments) to save bytes; magick only |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `format` | string | yes |  |
| `max_kb` | number | yes |  |
| `bytes` | integer | yes |  |
| `kb` | number | yes |  |
| `original_bytes` | integer | yes |  |
| `quality` | integer or null | yes | null for PNG and for webp:target-size |
| `method` | string: `quality-search` \| `webp:target-size` \| `lossless` | yes |  |
| `attempts` | array | yes | every encode tried: {quality\|target_bytes, bytes} |
| `stripped` | boolean | yes |  |
| `actual` | object | yes | {width, height} in pixels |
| `backend` | string: `magick` \| `sips` | yes |  |

### `crop`

Crop to an exact pixel rectangle, or to the largest region of an aspect ratio placed by gravity. Never clips a rectangle silently.

- Script: `scripts/crop.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`, `look`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; must differ from the input, extension picks the format |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |
| `--x` | string | no |  | rectangle: left edge in pixels (with --y --width --height) |
| `--y` | string | no |  | rectangle: top edge in pixels |
| `--width` | string | no |  | rectangle: width in pixels |
| `--height` | string | no |  | rectangle: height in pixels |
| `--aspect` | string | no |  | crop the largest W:H region instead of a rectangle, e.g. 1:1 or 16:9 |
| `--gravity` | string: `northwest` \| `north` \| `northeast` \| `west` \| `center` \| `east` \| `southwest` \| `south` \| `southeast` | no | `"center"` | where the --aspect region sits (default center) |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `mode` | string: `rect` \| `aspect` | yes |  |
| `box` | object | yes | {x, y, width, height} cut from the image as displayed |
| `original` | object | yes | {width, height} in pixels |
| `actual` | object | yes | {width, height} in pixels |
| `backend` | string: `magick` \| `sips` | yes |  |

### `pad`

Pad to an aspect ratio or exact canvas with a given colour (or transparency), never scaling or cropping the image.

- Script: `scripts/pad.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`, `look`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; must differ from the input, extension picks the format |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |
| `--aspect` | string | no |  | pad to the smallest W:H canvas that holds the image, e.g. 1:1 or 16:9 |
| `--width` | string | no |  | exact canvas width in pixels (with --height) |
| `--height` | string | no |  | exact canvas height in pixels (with --width) |
| `--color` | string | yes |  | fill colour: a name (white), #RRGGBB, #RRGGBBAA, rgb()/rgba(), or none for transparent |
| `--gravity` | string: `northwest` \| `north` \| `northeast` \| `west` \| `center` \| `east` \| `southwest` \| `south` \| `southeast` | no | `"center"` | where the image sits on the canvas (default center) |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `mode` | string: `aspect` \| `canvas` | yes |  |
| `color` | string | yes |  |
| `original` | object | yes | {width, height} in pixels |
| `offset` | object or null | yes | {x, y} of the image on the canvas; null on sips |
| `actual` | object | yes | {width, height} in pixels |
| `backend` | string: `magick` \| `sips` | yes |  |

### `rotate`

Rotate clockwise, mirror, or just bake EXIF orientation into the pixels.

- Script: `scripts/rotate.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`, `look`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `input` (positional) | string | yes |  | image file to read (never modified) |
| `-o`, `--output` | string | yes |  | file to write; must differ from the input, extension picks the format |
| `--overwrite` | boolean | no |  | allow replacing an existing output file |
| `--json` | boolean | no |  | print one JSON object (ok:true/false) instead of text |
| `--dry-run` | boolean | no |  | print the backend command that would run, write nothing |
| `--degrees` | number | no |  | clockwise rotation in degrees (default 0) |
| `--flip-horizontal` | boolean | no |  | mirror left-right (after rotating) |
| `--flip-vertical` | boolean | no |  | mirror top-bottom (after rotating) |
| `--background` | string | no |  | fill for the corners a non-multiple-of-90 rotation exposes (required then), or none |

Output of `--json` on success (`ok: true`):

| Key | Type | Always present | Description |
| --- | --- | --- | --- |
| `ok` | boolean | yes | `true` |
| `input` | string | yes |  |
| `output` | string | yes |  |
| `degrees` | number | yes |  |
| `flip_horizontal` | boolean | yes |  |
| `flip_vertical` | boolean | yes |  |
| `orientation_before` | string or null | yes | EXIF orientation of the input (magick), e.g. RightTop |
| `original` | object | yes | {width, height} in pixels |
| `actual` | object | yes | {width, height} in pixels |
| `backend` | string: `magick` \| `sips` | yes |  |

### `batch`

Run one of convert/resize/thumb/strip/trim over every image in a folder.

- Script: `scripts/batch.py` · role: execution · backends: magick, sips
- Writes a file: yes · `--dry-run`: yes · `--json`: yes · verify with: `check`

| Argument | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `tool` (positional) | string: `compare` \| `convert` \| `crop` \| `look` \| `optimize` \| `pad` \| `resize` \| `rotate` \| `strip` \| `thumb` \| `trim` | yes |  | tool to run on each file |
| `-i`, `--input-dir` | string | yes |  | folder of images to read (not recursive) |
| `-o`, `--output-dir` | string | yes |  | folder to write results into; must differ from --input-dir |
| `--ext` | string | no |  | output extension, e.g. webp: required for convert, optional for the other tools |
| `--against` | string | no |  | compare only: folder holding the second image of each pair (matched by file name) |
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
