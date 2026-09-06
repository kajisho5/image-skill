"""Shared helpers for image-skill scripts.

Backend precedence: ImageMagick `magick` first, macOS `sips` as a partial
fallback. Standard library only - no third-party Python packages, no network
calls. Subprocess commands are always argv lists (never a shell string), so
no user-supplied path or filter string can be interpreted as shell syntax.
"""
import json
import os
import platform
import shutil
import subprocess
import sys


class ImageSkillError(Exception):
    """Raised for user-facing failures. The CLI layer turns this into ok:false."""


def emit(payload, as_json):
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if payload.get("ok"):
        for key, value in payload.items():
            if key != "ok":
                print(f"{key}: {value}")
    else:
        print(f"error: {payload.get('reason', 'unknown error')}", file=sys.stderr)


def fail(reason, as_json, **extra):
    payload = {"ok": False, "reason": reason}
    payload.update(extra)
    emit(payload, as_json)
    sys.exit(1)


def succeed(payload, as_json):
    payload = {"ok": True, **payload}
    emit(payload, as_json)
    return payload


def which_magick():
    return shutil.which("magick")


def which_sips():
    if platform.system() != "Darwin":
        return None
    return shutil.which("sips")


def check_output_not_input(input_path, output_path):
    if os.path.realpath(input_path) == os.path.realpath(output_path):
        raise ImageSkillError(
            "output path must differ from input path (refusing to overwrite the original)"
        )


def check_output_not_exists(output_path, allow_overwrite=False):
    if not allow_overwrite and os.path.exists(output_path):
        raise ImageSkillError(f"output already exists: {output_path} (refusing to overwrite)")


def run(cmd, dry_run=False, timeout=120):
    """Run a subprocess command given as an argv list. Never uses shell=True."""
    if dry_run:
        return {"dry_run": True, "command": cmd}
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise ImageSkillError(f"command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise ImageSkillError(f"command timed out: {' '.join(cmd)}")
    if result.returncode != 0:
        raise ImageSkillError(
            f"command failed ({cmd[0]}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return {"dry_run": False, "command": cmd, "stdout": result.stdout, "stderr": result.stderr}


def identify_dims(path):
    """Return (width, height) using whichever backend is available."""
    magick = which_magick()
    if magick:
        result = run([magick, "identify", "-format", "%w %h", path])
        width, height = result["stdout"].split()
        return int(width), int(height)

    sips = which_sips()
    if sips:
        result = run([sips, "-g", "pixelWidth", "-g", "pixelHeight", path])
        width = height = None
        for line in result["stdout"].splitlines():
            line = line.strip()
            if line.startswith("pixelWidth:"):
                width = int(line.split(":", 1)[1].strip())
            elif line.startswith("pixelHeight:"):
                height = int(line.split(":", 1)[1].strip())
        return width, height

    raise ImageSkillError("no usable backend: install ImageMagick (magick) or, on macOS, use sips")
