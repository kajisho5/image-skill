# image-skill

Give your coding agent a local image editor that does not overwrite originals.

```bash
npx image-skill                 # installs into ~/.claude/skills/image-skill (default)
npx image-skill --cursor        # ~/.cursor/skills/image-skill
npx image-skill --codex         # ~/.codex/skills/image-skill
npx image-skill --all           # all three of the above
npx image-skill --dir <parent>  # <parent>/image-skill
npx image-skill --project       # ./.claude/skills/image-skill (this project only)
npx image-skill --uninstall     # remove the installed target(s)
npx image-skill doctor [--json] # check for magick/sips and what's actually usable
npx image-skill contract --json # machine-readable tool spec
npx image-skill --help
```

Already installed? Re-running replaces the copy with whatever version you run - reinstall anytime to update.

## Example

> "hero.heic を 1200x630 の OG WebP にして GPS を落とせ。元は残す"

```bash
python3 scripts/convert.py hero.heic -o hero.png --json
python3 scripts/resize.py hero.png -o hero-og.png --width 1200 --height 630 --mode fill --json
python3 scripts/convert.py hero-og.png -o hero-og.webp --json
python3 scripts/strip.py hero-og.webp -o hero-og-final.webp --json
python3 scripts/check.py hero-og-final.webp --input hero.heic --expect-width 1200 --expect-height 630 --json
```

`hero.heic` is never touched - every intermediate file is a new path.

## What this is (and isn't)

- **Is**: conversion, resize (fit/fill/exact), thumbnails, WebP, EXIF/GPS
  strip, border trim, and format/size verification for images that land in a
  repo - iPhone HEIC/JPEG, screenshots, OG images, README assets.
- **Isn't video editing.** No FFmpeg, no frame extraction, no GIF animation -
  use a separate video skill for that. No face recognition, generative AI,
  cloud background removal, RAW development, or print ICC color management.

## Install

Everything runs on Python 3.9+ standard library plus a system image tool -
no pip packages, no API keys, no network calls.

**macOS**
```bash
brew install imagemagick
```
Whether that build includes HEIC/WebP support depends on the Homebrew
formula's linked libraries at install time - don't assume, run `doctor`.
`sips` ships with macOS and works as a fallback for `convert`/`resize`/
`thumb` even without ImageMagick, but `strip` and `trim` need `magick`.

**Debian/Ubuntu**
```bash
sudo apt install imagemagick
```
Whether the packaged build includes a HEIC (libheif) delegate varies by
distro and version - run `doctor` and check the `heic` field rather than
assuming.

**Windows**
Install ImageMagick from https://imagemagick.org/script/download.php#windows
and make sure `magick` is on PATH. There is no `sips` fallback on Windows.

Whatever the platform, the source of truth is:
```bash
npx image-skill doctor
```
It reports exactly which backend is present and which formats/tools are
actually usable on this machine - don't take this README's word for it.

## Tools

`probe`, `convert`, `resize`, `thumb`, `strip`, `trim`, `check`, `batch`. See
[SKILL.md](./SKILL.md) for the rules an agent follows, and
`python3 scripts/_contract.py contract --json` for the full machine-readable
spec.

## Not a video skill

This repo does not touch video, GIF animation, or frame extraction. Use a
dedicated FFmpeg-based skill for that.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests that need ImageMagick or sips are skipped automatically when neither
is on PATH.

## License

MIT
