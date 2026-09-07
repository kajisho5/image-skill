#!/usr/bin/env python3
"""_contract.py - machine-readable description of the toolset (contract) and a live
environment check (doctor). Both are JSON-first: an agent should read `contract`
instead of guessing flags, and run `doctor` before assuming a format/tool works."""
import json
import re
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    ImageSkillError,
    JSONArgumentParser,
    fail,
    wants_json,
    which_magick,
    which_sips,
)


def _read_version():
    """Single source of truth is package.json (copied alongside scripts/ by the
    installer into every target) - avoids a hardcoded version string here drifting
    out of sync with it."""
    pkg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "package.json")
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            return json.load(f).get("version", "0.0.0")
    except (OSError, ValueError):
        return "0.0.0"


VERSION = _read_version()

TOOLS = [
    {
        "name": "probe",
        "script": "probe.py",
        "description": "Report width, height, format, colorspace, alpha, and GPS presence as JSON.",
        "writes_output": False,
        "required_args": ["input"],
        "optional_args": ["--json", "--dry-run"],
    },
    {
        "name": "convert",
        "script": "convert.py",
        "description": "Convert an image to a different format (e.g. HEIC to JPEG/PNG/WebP). Input is preserved.",
        "writes_output": True,
        "required_args": ["input", "-o/--output"],
        "optional_args": ["--quality", "--overwrite", "--json", "--dry-run"],
    },
    {
        "name": "resize",
        "script": "resize.py",
        "description": "Resize an image: fit (default, no distortion), fill (crop to cover), or exact (force size).",
        "writes_output": True,
        "required_args": ["input", "-o/--output", "--width", "--height"],
        "optional_args": ["--mode", "--quality", "--overwrite", "--json", "--dry-run"],
    },
    {
        "name": "thumb",
        "script": "thumb.py",
        "description": "Create a thumbnail sized by its longest edge, preserving aspect ratio.",
        "writes_output": True,
        "required_args": ["input", "-o/--output", "--long-edge"],
        "optional_args": ["--quality", "--overwrite", "--json", "--dry-run"],
    },
    {
        "name": "strip",
        "script": "strip.py",
        "description": "Remove GPS/EXIF metadata. Applies orientation before stripping. Requires ImageMagick.",
        "writes_output": True,
        "required_args": ["input", "-o/--output"],
        "optional_args": ["--overwrite", "--json", "--dry-run"],
    },
    {
        "name": "trim",
        "script": "trim.py",
        "description": "Trim a solid-color border. Fails instead of over-trimming. Requires ImageMagick.",
        "writes_output": True,
        "required_args": ["input", "-o/--output"],
        "optional_args": ["--fuzz", "--max-trim-percent", "--overwrite", "--json", "--dry-run"],
    },
    {
        "name": "check",
        "script": "check.py",
        "description": "Verify an output file opens, matches promised dimensions/format, and didn't overwrite the input.",
        "writes_output": False,
        "required_args": ["output"],
        "optional_args": [
            "--input",
            "--expect-width",
            "--expect-height",
            "--expect-max-width",
            "--expect-max-height",
            "--expect-format",
            "--json",
        ],
    },
    {
        "name": "batch",
        "script": "batch.py",
        "description": "Run one of convert/resize/thumb/strip/trim over every image in a folder.",
        "writes_output": True,
        "required_args": ["tool", "-i/--input-dir", "-o/--output-dir"],
        "optional_args": ["--ext", "--json", "--dry-run"],
    },
]

RULES = [
    "Never overwrite the input: -o/--output is required and must differ from the input path.",
    "Every tool supports --json for machine-readable output; every tool that writes a file also supports --dry-run to preview the command without running it (check.py writes nothing, so it has no --dry-run).",
    "Failures - including a malformed invocation with missing or invalid flags - return ok:false with a human-readable 'reason'; a broken or empty output is never reported as success.",
    "Call probe.py before editing and check.py after, to confirm the result matches what was promised.",
    "Tools never invoke mogrify (which overwrites in place) and never build a magick command from caller-supplied strings.",
]


def build_contract_payload():
    return {"ok": True, "version": VERSION, "tools": TOOLS, "rules": RULES}


_FORMAT_MODE_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\*?(?:\s+\S+)?\s+([r-][w-][+-])\s", re.MULTILINE)


def _format_capabilities(formats_out):
    """Map format name (upper) -> (can_read, can_write), parsed from the Mode
    column of `magick -list format` (e.g. 'rw+', 'r--', '-w-').

    A format name appearing in the list at all does NOT mean both directions
    work: a read-only delegate (mode 'r--') still lets `magick in.png
    out.heic` exit 0, silently writing the wrong format under the requested
    name instead of failing (see verify_output_format in _common.py) - so
    doctor has to check the actual mode flags, not just presence of the name.
    """
    caps = {}
    for name, mode in _FORMAT_MODE_RE.findall(formats_out):
        caps[name.upper()] = (mode[0] == "r", mode[1] == "w")
    return caps


def _magick_lists(magick):
    formats = subprocess.run([magick, "-list", "format"], capture_output=True, text=True, timeout=30)
    policy = subprocess.run([magick, "-list", "policy"], capture_output=True, text=True, timeout=30)
    version = subprocess.run([magick, "-version"], capture_output=True, text=True, timeout=30)
    return formats.stdout, policy.stdout, version.stdout


def _tool_status(magick, sips, needs_magick_only=False):
    if magick:
        return {"usable": True, "backend": "magick"}
    if sips and not needs_magick_only:
        return {"usable": True, "backend": "sips", "note": "reduced feature set via sips"}
    if needs_magick_only:
        return {"usable": False, "backend": None, "fix": "install ImageMagick: `brew install imagemagick`"}
    return {
        "usable": False,
        "backend": None,
        "fix": "install ImageMagick or, on macOS, ensure sips is on PATH",
    }


def build_doctor_payload():
    magick = which_magick()
    sips = which_sips()
    is_mac = sys.platform == "darwin"

    backends = {
        "magick": {"found": bool(magick), "path": magick},
        "sips": {"found": bool(sips), "path": sips},
    }

    heic = {"usable": False, "read": False, "write": False, "backend": None, "fix": None}
    webp = {"usable": False, "read": False, "write": False, "backend": None, "fix": None}
    pdf_policy = None
    magick_version = None

    if magick:
        try:
            formats_out, policy_out, version_out = _magick_lists(magick)
            magick_version = version_out.strip().splitlines()[0] if version_out.strip() else None
            caps = _format_capabilities(formats_out)
            heic_read, heic_write = caps.get("HEIC", (False, False))
            webp_read, webp_write = caps.get("WEBP", (False, False))

            # "usable" tracks the workflow this skill actually documents: HEIC is
            # read FROM (iPhone photos in, something else out); WebP is written TO
            # (an OG/thumb asset out). Both directions are still reported so an
            # agent doesn't get burned assuming the other direction also works.
            if heic_read:
                heic = {
                    "usable": True,
                    "read": True,
                    "write": heic_write,
                    "backend": "magick",
                    "fix": None
                    if heic_write
                    else "read-only HEIC on this build (no encode delegate) - can convert FROM HEIC but not "
                    "create it; reinstall ImageMagick with libheif's encoder for write support, e.g. "
                    "`brew reinstall imagemagick`, or use sips on macOS to write HEIC",
                }
            elif is_mac and sips:
                heic = {
                    "usable": True,
                    "read": True,
                    "write": True,
                    "backend": "sips",
                    "fix": None,
                    "note": "magick has no HEIC read delegate here; falling back to sips for HEIC",
                }
            else:
                heic = {
                    "usable": False,
                    "read": False,
                    "write": False,
                    "backend": None,
                    "fix": "reinstall ImageMagick with HEIC support, e.g. `brew reinstall imagemagick` "
                    "(needs libheif), or run on macOS to use sips instead",
                }

            if webp_write:
                webp = {"usable": True, "read": webp_read, "write": True, "backend": "magick", "fix": None}
            else:
                webp = {
                    "usable": False,
                    "read": webp_read,
                    "write": False,
                    "backend": None,
                    "fix": "reinstall ImageMagick with WebP write support, e.g. `brew reinstall imagemagick` "
                    "(needs libwebp)",
                }

            pdf_disabled = "PDF" in policy_out.upper() and 'rights="none"' in policy_out.lower()
            pdf_policy = {
                "enabled": not pdf_disabled,
                "note": (
                    "PDF read/write is blocked by ImageMagick's policy.xml on this system"
                    if pdf_disabled
                    else "not detected as blocked here; PDF conversion is out of scope for image-skill v0.1 regardless"
                ),
            }
        except (subprocess.TimeoutExpired, OSError) as e:
            heic = {"usable": False, "read": False, "write": False, "backend": None, "fix": f"could not query magick: {e}"}
    elif is_mac and sips:
        heic = {"usable": True, "read": True, "write": True, "backend": "sips", "fix": None}
        webp = {
            "usable": False,
            "read": False,
            "write": False,
            "backend": None,
            "fix": "sips cannot write WebP; install ImageMagick: `brew install imagemagick`",
        }
    else:
        heic = {
            "usable": False,
            "read": False,
            "write": False,
            "backend": None,
            "fix": "install ImageMagick (`brew install imagemagick` / your package manager) or run on macOS for sips",
        }
        webp = {
            "usable": False,
            "read": False,
            "write": False,
            "backend": None,
            "fix": "install ImageMagick: `brew install imagemagick`",
        }

    tools = {
        "probe": _tool_status(magick, sips),
        "convert": _tool_status(magick, sips),
        "resize": _tool_status(magick, sips),
        "thumb": _tool_status(magick, sips),
        "strip": _tool_status(magick, sips, needs_magick_only=True),
        "trim": _tool_status(magick, sips, needs_magick_only=True),
        "check": _tool_status(magick, sips),
        "batch": _tool_status(magick, sips),
    }

    overall_ok = magick is not None or sips is not None

    payload = {
        "ok": overall_ok,
        "platform": sys.platform,
        "backends": backends,
        "magick_version": magick_version,
        "heic": heic,
        "webp": webp,
        "pdf_policy": pdf_policy,
        "tools": tools,
    }
    if not overall_ok:
        payload["reason"] = (
            "no usable backend found: install ImageMagick (`brew install imagemagick`, `apt install imagemagick`, "
            "or https://imagemagick.org) or run on macOS for the sips fallback"
        )
    return payload


def cmd_contract(args):
    payload = build_contract_payload()
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))


def cmd_doctor(args):
    payload = build_doctor_payload()
    print(json.dumps(payload, ensure_ascii=False, indent=None if args.json else 2))


def build_parser():
    parser = JSONArgumentParser(description="image-skill contract/doctor")
    sub = parser.add_subparsers(dest="command", required=True)

    contract_p = sub.add_parser("contract", help="describe the available tools as JSON")
    contract_p.add_argument("--json", action="store_true")
    contract_p.set_defaults(func=cmd_contract)

    doctor_p = sub.add_parser("doctor", help="check the local environment for usable backends")
    doctor_p.add_argument("--json", action="store_true")
    doctor_p.set_defaults(func=cmd_doctor)

    return parser


def main(argv=None):
    as_json = wants_json(argv)
    try:
        args = build_parser().parse_args(argv)
    except ImageSkillError as e:
        fail(str(e), as_json)
        return
    args.func(args)


if __name__ == "__main__":
    main()
