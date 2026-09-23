#!/usr/bin/env python3
"""_contract.py - machine-readable description of the toolset (contract) and a live
environment check (doctor). Both are JSON-first: an agent should read `contract`
instead of guessing flags, and run `doctor` before assuming a format/tool works.

Each tool's input_schema (and the legacy required_args/optional_args lists) is
derived from that script's own build_parser(); only facts a parser cannot state
(role, backends, output shape) are written by hand in TOOL_META."""
import argparse
import importlib.util
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
SKILL_ID = "imagemagick-skill"

CONTRACT_VERSION = "1.0"
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Output shapes shared by every tool. A tool's own output_schema lists only what
# an ok:true, non-dry-run --json result carries.
FAILURE_SCHEMA = {
    "ok": {"type": "boolean", "description": "always false"},
    "reason": {"type": "string", "description": "human-readable cause, including argument errors"},
}
DRY_RUN_SCHEMA = {
    "ok": {"type": "boolean", "description": "always true"},
    "dry_run": {"type": "boolean", "description": "always true"},
    "would_run": {"type": "array", "description": "argv of the backend command that would run (never a shell string)"},
}

_WH = {"type": "object", "description": "{width, height} in pixels"}

# Hand-written facts a parser cannot express. Everything about arguments (names,
# types, choices, defaults, required/positional) is derived from each script's own
# build_parser() in tool_spec(), so the contract cannot drift from the CLI.
TOOL_META = {
    "probe": dict(
        description="Report width, height, format, colorspace, alpha, and GPS presence as JSON.",
        role="analysis",
        backends=["magick", "sips"],
        verify=[],
        output_schema={
            "input": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "format": {"type": "string", "description": "backend format name, e.g. JPEG, PNG, HEIC (sips reports lowercase)"},
            "colorspace": {"type": ["string", "null"], "description": "null on the sips backend"},
            "has_alpha": {"type": ["boolean", "null"], "description": "null on the sips backend"},
            "has_gps": {"type": ["boolean", "null"], "description": "EXIF GPSLatitude present; null on the sips backend"},
            "backend": {"type": "string", "enum": ["magick", "sips"]},
            "note": {"type": "string", "description": "present when a field could not be measured"},
        },
        output_required=["input", "width", "height", "format", "backend"],
    ),
    "convert": dict(
        description="Convert an image to a different format (e.g. HEIC to JPEG/PNG/WebP). Input is preserved.",
        role="execution",
        backends=["magick", "sips"],
        verify=["check"],
        output_schema={
            "input": {"type": "string"},
            "output": {"type": "string"},
            "backend": {"type": "string", "enum": ["magick", "sips"]},
        },
        output_required=["input", "output", "backend"],
    ),
    "resize": dict(
        description="Resize an image: fit (default, no distortion), fill (crop to cover), or exact (force size).",
        role="execution",
        backends=["magick", "sips"],
        verify=["check"],
        output_schema={
            "input": {"type": "string"},
            "output": {"type": "string"},
            "mode": {"type": "string", "enum": ["fit", "fill", "exact"]},
            "requested": _WH,
            "actual": _WH,
            "backend": {"type": "string", "enum": ["magick", "sips"]},
        },
        output_required=["input", "output", "mode", "requested", "actual", "backend"],
    ),
    "thumb": dict(
        description="Create a thumbnail sized by its longest edge, preserving aspect ratio.",
        role="execution",
        backends=["magick", "sips"],
        verify=["check"],
        output_schema={
            "input": {"type": "string"},
            "output": {"type": "string"},
            "long_edge": {"type": "integer"},
            "actual": _WH,
            "backend": {"type": "string", "enum": ["magick", "sips"]},
        },
        output_required=["input", "output", "long_edge", "actual", "backend"],
    ),
    "strip": dict(
        description="Remove GPS/EXIF metadata. Applies orientation before stripping. Requires ImageMagick.",
        role="execution",
        backends=["magick"],
        verify=["check", "probe"],
        output_schema={
            "input": {"type": "string"},
            "output": {"type": "string"},
            "has_gps": {"type": "boolean", "description": "always false: a result that still has GPS is a failure"},
            "backend": {"type": "string", "enum": ["magick"]},
        },
        output_required=["input", "output", "has_gps", "backend"],
    ),
    "trim": dict(
        description="Trim a solid-color border. Fails instead of over-trimming. Requires ImageMagick.",
        role="execution",
        backends=["magick"],
        verify=["check"],
        output_schema={
            "input": {"type": "string"},
            "output": {"type": "string"},
            "original": _WH,
            "trimmed": _WH,
            "removed_percent": {"type": "number"},
            "backend": {"type": "string", "enum": ["magick"]},
        },
        output_required=["input", "output", "original", "trimmed", "removed_percent", "backend"],
    ),
    "check": dict(
        description="Verify an output file opens, matches promised dimensions/format, and didn't overwrite the input.",
        role="verification",
        backends=["magick", "sips"],
        verify=[],
        output_schema={
            "output": {"type": "string"},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "format": {"type": ["string", "null"], "description": "read only when --expect-format is given"},
        },
        output_required=["output", "width", "height", "format"],
    ),
    "batch": dict(
        description="Run one of convert/resize/thumb/strip/trim over every image in a folder.",
        role="execution",
        backends=["magick", "sips"],
        verify=["check"],
        extra_properties={
            "tool_args": {
                "type": "array",
                "items": {"type": "string"},
                "cli": "after --",
                "description": "arguments forwarded to the per-file tool, e.g. [\"--width\", \"1200\", \"--height\", \"1200\"]",
            },
        },
        output_schema={
            "tool": {"type": "string"},
            "count": {"type": "integer"},
            "all_ok": {"type": "boolean"},
            "results": {"type": "array", "description": "one {file, output, ok, result|reason} per input file"},
        },
        output_required=["tool", "count", "all_ok", "results"],
    ),
}

RULES = [
    "Never overwrite the input: -o/--output is required and must differ from the input path.",
    "Every tool supports --json for machine-readable output; every tool that writes a file also supports --dry-run to preview the command without running it (check.py writes nothing, so it has no --dry-run).",
    "Failures - including a malformed invocation with missing or invalid flags - return ok:false with a human-readable 'reason'; a broken or empty output is never reported as success.",
    "Call probe.py before editing and check.py after, to confirm the result matches what was promised.",
    "Tools never invoke mogrify (which overwrites in place) and never build a magick command from caller-supplied strings.",
]

EXECUTION = {"shell": False, "network": False, "input_mutation": False, "arbitrary_executables": False}


def public_tools():
    """Tool names in contract order. Every public script (no leading underscore)
    must have a TOOL_META entry and vice versa - tests enforce both directions."""
    return list(TOOL_META)


def _load_tool_module(name):
    spec = importlib.util.spec_from_file_location(f"imagemagick_skill_tool_{name}", os.path.join(SCRIPTS_DIR, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_type(action):
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return {"type": "boolean"}
    if isinstance(action, argparse._AppendAction) or action.nargs in ("+", "*"):
        return {"type": "array", "items": {"type": "string"}}
    if action.type is int:
        return {"type": "integer"}
    if action.type is float:
        return {"type": "number"}
    return {"type": "string"}


def input_schema(parser):
    """JSON-schema-like description of a parser: one property per argparse dest."""
    props = {}
    required = []
    positional = []
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction):
            continue
        prop = _json_type(action)
        if action.help and action.help != argparse.SUPPRESS:
            prop["description"] = action.help
        if action.choices:
            prop["enum"] = list(action.choices)
        if action.default not in (None, False, argparse.SUPPRESS):
            prop["default"] = action.default
        if action.option_strings:
            prop["cli"] = list(action.option_strings)
            if action.required:
                required.append(action.dest)
        else:
            prop["cli"] = "positional"
            positional.append(action.dest)
            if action.nargs not in ("?", "*"):
                required.append(action.dest)
        props[action.dest] = prop
    schema = {
        "type": "object",
        "properties": props,
        "required": required,
        "positional": positional,
        "additionalProperties": False,
    }
    groups = [g for g in getattr(parser, "_mutually_exclusive_groups", []) if g._group_actions]
    if groups:
        schema["mutually_exclusive"] = [[a.dest for a in g._group_actions] for g in groups]
    return schema


def _flag_label(prop, dest):
    cli = prop["cli"]
    if cli == "positional":
        return dest
    return "/".join(cli)


def tool_spec(name):
    meta = TOOL_META[name]
    parser = _load_tool_module(name).build_parser()
    schema = input_schema(parser)
    for dest, prop in meta.get("extra_properties", {}).items():
        schema["properties"][dest] = dict(prop)
    props = schema["properties"]
    real = [d for d in props if props[d]["cli"] != "after --"]
    required_args = [_flag_label(props[d], d) for d in real if d in schema["required"]]
    optional_args = [_flag_label(props[d], d) for d in real if d not in schema["required"]]
    writes_output = "output" in props or "output_dir" in props
    if name == "check":
        writes_output = False  # its positional is named "output" but it only reads it
    return {
        "name": name,
        "script": f"{name}.py",
        "description": meta["description"],
        "writes_output": writes_output,
        "required_args": required_args,
        "optional_args": optional_args,
        "id": f"{SKILL_ID}/{name}",
        "executable": f"scripts/{name}.py",
        "role": meta["role"],
        "backends": list(meta["backends"]),
        "requires_magick": meta["backends"] == ["magick"],
        "supports_json": "json" in props,
        "supports_dry_run": "dry_run" in props,
        "mutates_input": False,
        "verify": list(meta["verify"]),
        "input_schema": schema,
        "output_schema": {
            "type": "object",
            "properties": dict(meta["output_schema"]),
            "required": ["ok"] + list(meta["output_required"]),
        },
    }


def build_contract_payload():
    tools = [tool_spec(name) for name in public_tools()]
    return {
        "ok": True,
        "name": SKILL_ID,
        "version": VERSION,
        "contract_version": CONTRACT_VERSION,
        "skill": {
            "id": SKILL_ID,
            "version": VERSION,
            "execution_mode": "local",
            "entrypoints": {
                "cli": "python3 scripts/<tool>.py",
                "contract": "python3 scripts/_contract.py contract --json",
                "doctor": "python3 scripts/_contract.py doctor --json",
            },
        },
        "requirements": {
            "python": ">=3.9 (standard library only)",
            "backends": "ImageMagick `magick` (every tool) or macOS `sips` (subset; see each tool's backends)",
        },
        "execution": dict(EXECUTION),
        "result_shapes": {"failure": FAILURE_SCHEMA, "dry_run": DRY_RUN_SCHEMA},
        "tools": tools,
        "rules": RULES,
    }


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
                    else "not detected as blocked here; PDF conversion is out of scope for this skill regardless"
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
        name: _tool_status(magick, sips, needs_magick_only=meta["backends"] == ["magick"])
        for name, meta in TOOL_META.items()
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
    parser = JSONArgumentParser(description=f"{SKILL_ID} contract/doctor")
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
