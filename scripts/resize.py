#!/usr/bin/env python3
"""resize.py - resize an image using fit (default, no distortion), fill (crop to
cover), or exact (force size, may distort). Verifies the output dimensions against
what was promised before reporting success."""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    ImageSkillError,
    check_output_not_exists,
    check_output_not_input,
    identify_dims,
    fail,
    run,
    succeed,
    which_magick,
    which_sips,
)


def build_parser():
    parser = argparse.ArgumentParser(description="Resize an image (fit, fill, or exact)")
    parser.add_argument("input")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--mode", choices=["fit", "fill", "exact"], default="fit")
    parser.add_argument("--quality", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _build_cmd(backend, backend_bin, input_path, output_path, width, height, mode, quality):
    box = f"{width}x{height}"

    if backend == "magick":
        cmd = [backend_bin, input_path, "-auto-orient"]
        if mode == "fit":
            cmd += ["-resize", box]
        elif mode == "fill":
            cmd += ["-resize", f"{box}^", "-gravity", "center", "-extent", box]
        else:  # exact
            cmd += ["-resize", f"{box}!"]
        if quality is not None:
            cmd += ["-quality", str(quality)]
        cmd.append(output_path)
        return cmd

    # sips
    if mode != "fit":
        raise ImageSkillError(
            f"sips backend only supports resize mode 'fit' (got '{mode}'); install ImageMagick for fill/exact"
        )
    return [backend_bin, "-Z", str(max(width, height)), input_path, "--out", output_path]


def _verify_dims(output_path, width, height, mode):
    out_w, out_h = identify_dims(output_path)
    if out_w is None or out_h is None:
        raise ImageSkillError("could not read dimensions of the output file")

    if mode in ("fill", "exact"):
        if (out_w, out_h) != (width, height):
            raise ImageSkillError(
                f"{mode} resize did not produce {width}x{height}, got {out_w}x{out_h}"
            )
    else:  # fit
        if out_w > width or out_h > height:
            raise ImageSkillError(
                f"fit resize exceeded {width}x{height} box, got {out_w}x{out_h}"
            )

    return out_w, out_h


def run_resize(args):
    if not os.path.isfile(args.input):
        raise ImageSkillError(f"input not found: {args.input}")
    if args.width <= 0 or args.height <= 0:
        raise ImageSkillError("--width and --height must be positive")
    check_output_not_input(args.input, args.output)
    check_output_not_exists(args.output, allow_overwrite=args.overwrite)

    magick = which_magick()
    sips = which_sips()
    if magick:
        backend, backend_bin = "magick", magick
    elif sips:
        backend, backend_bin = "sips", sips
    else:
        raise ImageSkillError("no usable backend: install ImageMagick (magick) or, on macOS, use sips")

    cmd = _build_cmd(backend, backend_bin, args.input, args.output, args.width, args.height, args.mode, args.quality)
    run(cmd, dry_run=args.dry_run)
    if args.dry_run:
        return {"dry_run": True, "would_run": cmd}

    if not os.path.isfile(args.output):
        raise ImageSkillError("resize reported success but output file is missing")

    out_w, out_h = _verify_dims(args.output, args.width, args.height, args.mode)

    return {
        "input": args.input,
        "output": args.output,
        "mode": args.mode,
        "requested": {"width": args.width, "height": args.height},
        "actual": {"width": out_w, "height": out_h},
        "backend": backend,
    }


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        payload = run_resize(args)
    except ImageSkillError as e:
        fail(str(e), args.json)
        return
    succeed(payload, args.json)


if __name__ == "__main__":
    main()
