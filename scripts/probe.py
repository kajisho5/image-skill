#!/usr/bin/env python3
"""probe.py - inspect an image and report width, height, format, colorspace, alpha,
and GPS presence as JSON.

magick is the primary backend and reports every field. sips (macOS) can only
report width/height/format; colorspace/has_alpha/has_gps come back as null
with a note.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    ImageSkillError,
    JSONArgumentParser,
    wants_json,
    fail,
    run,
    succeed,
    which_magick,
    which_sips,
)


def build_parser():
    parser = JSONArgumentParser(
        description="Probe an image: dimensions, format, colorspace, alpha, GPS presence"
    )
    parser.add_argument("input")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _probe_with_magick(magick, path, dry_run):
    cmd = [magick, "identify", "-format", "%w|%h|%m|%[colorspace]|%A\n", path]
    if dry_run:
        return {"dry_run": True, "command": cmd}

    result = run(cmd)
    line = result["stdout"].strip().splitlines()[0]
    width, height, fmt, colorspace, alpha = line.split("|")

    gps_result = run([magick, "identify", "-format", "%[EXIF:GPSLatitude]", path])
    has_gps = bool(gps_result["stdout"].strip())

    return {
        "width": int(width),
        "height": int(height),
        "format": fmt,
        "colorspace": colorspace,
        "has_alpha": alpha.strip() == "True",
        "has_gps": has_gps,
        "backend": "magick",
    }


def _probe_with_sips(sips, path, dry_run):
    cmd = [sips, "-g", "pixelWidth", "-g", "pixelHeight", "-g", "format", path]
    if dry_run:
        return {"dry_run": True, "command": cmd}

    result = run(cmd)
    width = height = fmt = None
    for line in result["stdout"].splitlines():
        line = line.strip()
        if line.startswith("pixelWidth:"):
            width = int(line.split(":", 1)[1].strip())
        elif line.startswith("pixelHeight:"):
            height = int(line.split(":", 1)[1].strip())
        elif line.startswith("format:"):
            fmt = line.split(":", 1)[1].strip()

    return {
        "width": width,
        "height": height,
        "format": fmt,
        "colorspace": None,
        "has_alpha": None,
        "has_gps": None,
        "backend": "sips",
        "note": "sips backend: colorspace/has_alpha/has_gps are unavailable; install ImageMagick for full probe",
    }


def run_probe(args):
    if not os.path.isfile(args.input):
        raise ImageSkillError(f"input not found: {args.input}")

    magick = which_magick()
    sips = which_sips()

    if magick:
        payload = _probe_with_magick(magick, args.input, args.dry_run)
    elif sips:
        payload = _probe_with_sips(sips, args.input, args.dry_run)
    else:
        raise ImageSkillError("no usable backend: install ImageMagick (magick) or, on macOS, use sips")

    if args.dry_run:
        return {"dry_run": True, "would_run": payload["command"]}

    payload["input"] = args.input
    return payload


def main(argv=None):
    as_json = wants_json(argv)
    try:
        args = build_parser().parse_args(argv)
        payload = run_probe(args)
    except ImageSkillError as e:
        fail(str(e), as_json)
        return
    succeed(payload, args.json)


if __name__ == "__main__":
    main()
