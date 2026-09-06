---
name: image-skill
description: Local image editing (probe, convert, resize, thumbnail, EXIF/GPS strip, trim) for files that land in a repo - iPhone HEIC/JPEG, screenshots, OG images, README assets. Use when asked to convert, resize, thumbnail, make a WebP/OG image, strip GPS/EXIF, trim a border, or check an image's format/dimensions. Not for video, GIF animation, frame extraction, face recognition, generative AI, or RAW/ICC color work.
---

# image-skill

Local, deterministic image editing for a coding agent. No CLI is invented
here - every operation goes through the scripts in `scripts/`, each of which
speaks JSON and never overwrites its input.

## When to use this

- A HEIC/JPEG photo (often from an iPhone) needs converting or resizing
- A screenshot needs a thumbnail or format change
- An OG/social image needs a specific size (e.g. 1200x630) as WebP
- A README image needs a smaller or converted copy
- GPS or personal EXIF data needs to be removed before an image goes public
- You need to confirm an image's actual width/height/format before deciding what to do

## When NOT to use this

- Video, GIF animation, or extracting frames from video - use a
  video/FFmpeg-based skill instead, not this one
- Face recognition, background removal, generative/AI image editing
- RAW development, print-grade ICC color management
- PDF conversion (out of scope for v0.1)

## Rules (do not deviate)

1. **Never write a raw `magick`, `convert`, `mogrify`, or `sips` command
   yourself.** Only call the scripts in `scripts/`. `mogrify` is banned
   everywhere in this skill because it overwrites in place.
2. **Never overwrite the input.** Every tool that writes a file requires
   `-o/--output` and refuses to run if it resolves to the same path as the
   input, or if the output already exists (unless `--overwrite` is passed).
3. **Probe first, check last.** Run `probe.py` on the input before editing to
   know what you're actually working with (format, size, alpha, GPS). After
   writing an output, run `check.py` to confirm it opened correctly, matches
   what you promised (size/format), and didn't clobber the input.
4. **You don't choose sizes.** Target dimensions, formats, and quality come
   from the user or the calling task - this skill executes, it doesn't
   design. If no size was given for a resize/thumbnail, ask instead of
   guessing.
5. **Check the environment before relying on a format.** Run
   `python3 scripts/_contract.py doctor --json` once per session before
   using `convert`/`resize`/`thumb` for HEIC or WebP, or before `strip`/
   `trim` at all (magick-only, see doctor's `tools` and `heic`/`webp` fields).
6. **Every script supports `--json` and `--dry-run`.** Use `--dry-run` to see
   the exact command that would run without executing it. Either run the
   command for real via the script, or don't - don't reconstruct it yourself
   from the dry-run output.

## Typical flow

```bash
# 1. Know what you have
python3 scripts/probe.py hero.heic --json

# 2. Convert to a web format, resize to an exact OG box, then strip metadata
python3 scripts/convert.py hero.heic -o hero.jpg --json
python3 scripts/resize.py hero.jpg -o hero-og.jpg --width 1200 --height 630 --mode fill --json
python3 scripts/strip.py hero-og.jpg -o hero-og-clean.jpg --json

# 3. Confirm the result
python3 scripts/check.py hero-og-clean.jpg --input hero.heic \
  --expect-width 1200 --expect-height 630 --json
```

`hero.heic` is never touched by any of these steps - every output is a new file.

## Tools

See `python3 scripts/_contract.py contract --json` for the full
machine-readable spec (required/optional args per tool).

| Script | Purpose |
| --- | --- |
| `probe.py` | Width, height, format, colorspace, alpha, GPS presence |
| `convert.py` | Change format (HEIC->JPEG/PNG/WebP, PNG->WebP, ...) |
| `resize.py` | `fit` (default, no distortion), `fill` (cover+crop), `exact` (forced) |
| `thumb.py` | Thumbnail by long edge, aspect preserved, never upscales |
| `strip.py` | Remove GPS/EXIF, applying orientation first (magick only) |
| `trim.py` | Trim a solid-color border, fails instead of over-trimming (magick only) |
| `check.py` | Verify an output: opens, matches size/format, didn't overwrite input |
| `batch.py` | Run one of the above over every image in a folder |
| `_contract.py` | `contract` (tool spec) / `doctor` (environment check) |

Backend: ImageMagick `magick` first; macOS `sips` covers a reduced subset of
`convert`/`resize`/`thumb` when `magick` isn't installed. `strip` and `trim`
always require `magick`. No cloud calls, no API keys, no pip dependencies -
Python 3.9 standard library plus whichever binary is already on the machine.
