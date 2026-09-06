#!/usr/bin/env python3
"""strip.py - remove GPS and personal EXIF metadata. Applies orientation first so the
image doesn't end up sideways once the orientation tag is gone.

magick only: sips has no reliable blanket metadata-strip flag, so this tool
reports ok:false with a clear reason when only sips is available (see doctor).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    ImageSkillError,
    JSONArgumentParser,
    wants_json,
    check_output_not_exists,
    check_output_not_input,
    fail,
    run,
    succeed,
    which_magick,
)


def build_parser():
    parser = JSONArgumentParser(description="Strip GPS/EXIF metadata from an image")
    parser.add_argument("input")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def run_strip(args):
    if not os.path.isfile(args.input):
        raise ImageSkillError(f"input not found: {args.input}")
    check_output_not_input(args.input, args.output)
    check_output_not_exists(args.output, allow_overwrite=args.overwrite)

    magick = which_magick()
    if not magick:
        raise ImageSkillError(
            "strip requires ImageMagick (magick); sips has no reliable blanket EXIF-strip flag"
        )

    cmd = [magick, args.input, "-auto-orient", "-strip", args.output]
    run(cmd, dry_run=args.dry_run)
    if args.dry_run:
        return {"dry_run": True, "would_run": cmd}

    if not os.path.isfile(args.output):
        raise ImageSkillError("strip reported success but output file is missing")

    gps_result = run([magick, "identify", "-format", "%[EXIF:GPSLatitude]", args.output])
    if gps_result["stdout"].strip():
        raise ImageSkillError("output still contains GPS data after strip")

    return {"input": args.input, "output": args.output, "has_gps": False, "backend": "magick"}


def main(argv=None):
    as_json = wants_json(argv)
    try:
        args = build_parser().parse_args(argv)
        payload = run_strip(args)
    except ImageSkillError as e:
        fail(str(e), as_json)
        return
    succeed(payload, args.json)


if __name__ == "__main__":
    main()
