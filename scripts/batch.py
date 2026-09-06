#!/usr/bin/env python3
"""batch.py - run one image-skill tool (convert/resize/thumb/strip/trim) over every
image in a folder, writing to a separate output folder. Never overwrites inputs or
existing outputs; a single bad file is recorded as a failure and the rest of the
batch still runs."""
import glob
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import ImageSkillError, JSONArgumentParser, fail, succeed, wants_json  # noqa: E402

TOOL_MODULES = {
    "convert": "convert",
    "resize": "resize",
    "thumb": "thumb",
    "strip": "strip",
    "trim": "trim",
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".webp", ".gif"}


def build_parser():
    parser = JSONArgumentParser(
        description="Run an image-skill tool over every image in a folder",
        epilog="Extra args after -- are forwarded to the tool, e.g.: "
        "batch.py resize -i ./photos -o ./out --json -- --width 1200 --height 1200 --mode fit",
    )
    parser.add_argument("tool", choices=sorted(TOOL_MODULES))
    parser.add_argument("-i", "--input-dir", required=True)
    parser.add_argument("-o", "--output-dir", required=True)
    parser.add_argument("--ext", default=None, help="output extension for convert, e.g. webp (required for convert)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def parse_args(argv=None):
    """Split argv on a literal '--' so per-file tool flags (e.g. --width) can't be
    confused with batch's own flags; argparse.REMAINDER does not do this reliably
    when optionals are interspersed before the '--'."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        idx = argv.index("--")
        own_args, tool_args = argv[:idx], argv[idx + 1 :]
    else:
        own_args, tool_args = argv, []
    args = build_parser().parse_args(own_args)
    args.tool_args = tool_args
    return args


def run_batch(args):
    tool_args = args.tool_args

    in_dir = os.path.realpath(args.input_dir)
    out_dir = os.path.realpath(args.output_dir)
    if not os.path.isdir(in_dir):
        raise ImageSkillError(f"input dir not found: {args.input_dir}")
    if in_dir == out_dir:
        raise ImageSkillError("output dir must differ from input dir")
    if args.tool == "convert" and not args.ext:
        raise ImageSkillError("--ext is required for batch convert (e.g. --ext webp)")

    os.makedirs(out_dir, exist_ok=True)

    module = importlib.import_module(TOOL_MODULES[args.tool])
    parser = module.build_parser()

    files = sorted(
        f
        for f in glob.glob(os.path.join(in_dir, "*"))
        if os.path.isfile(f) and os.path.splitext(f)[1].lower() in IMAGE_EXTS
    )

    results = []
    for src in files:
        base = os.path.splitext(os.path.basename(src))[0]
        dest = os.path.join(out_dir, f"{base}.{args.ext}") if args.tool == "convert" else os.path.join(
            out_dir, os.path.basename(src)
        )

        per_file_args = [src, "-o", dest] + (["--dry-run"] if args.dry_run else []) + tool_args
        try:
            parsed = parser.parse_args(per_file_args)
            run_fn = getattr(module, f"run_{args.tool}")
            file_payload = run_fn(parsed)
            results.append({"file": src, "output": dest, "ok": True, "result": file_payload})
        except ImageSkillError as e:
            results.append({"file": src, "output": dest, "ok": False, "reason": str(e)})

    all_ok = all(r["ok"] for r in results)
    return {"tool": args.tool, "count": len(results), "all_ok": all_ok, "results": results}


def main(argv=None):
    as_json = wants_json(argv)
    try:
        args = parse_args(argv)
        payload = run_batch(args)
    except ImageSkillError as e:
        fail(str(e), as_json)
        return
    succeed(payload, args.json)


if __name__ == "__main__":
    main()
