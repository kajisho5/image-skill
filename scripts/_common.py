"""Shared helpers for imagemagick-skill scripts.

Backend precedence: ImageMagick `magick` first, macOS `sips` as a partial
fallback. Standard library only - no third-party Python packages, no network
calls. Subprocess commands are always argv lists (never a shell string), so
no user-supplied path or filter string can be interpreted as shell syntax.
"""
import argparse
import json
import os
import platform
import re
import shutil
import struct
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


class JSONArgumentParser(argparse.ArgumentParser):
    """An ArgumentParser whose own usage errors (missing/invalid flags, unknown
    arguments) raise ImageSkillError instead of argparse's default
    usage-text-to-stderr plus exit(2). A script's own main() then reports it
    through the same ok:false/--json contract as every other failure - and,
    because it's a normal exception rather than a hard process exit,
    batch.py can catch a bad per-file argument the same way it catches any
    other per-file failure instead of the whole batch aborting."""

    def error(self, message):
        raise ImageSkillError(message)


def wants_json(argv):
    """Best-effort check for whether --json was requested, usable even when
    argparse hasn't (or couldn't) successfully parse argv yet - e.g. to decide
    how to report a parse error itself."""
    return "--json" in (sys.argv[1:] if argv is None else argv)


IM6_SUBCOMMANDS = ("identify", "compare", "montage", "composite", "convert")
_IM6_CONVERT_CHECKED = {}


def _im6_convert():
    """ImageMagick 6's `convert`, when there is no `magick` (Debian/Ubuntu's apt package).

    Only a `convert` whose -version says ImageMagick 6 counts, and never on Windows,
    where `convert.exe` is the system's disk-conversion tool."""
    if os.name == "nt":
        return None
    path = shutil.which("convert")
    if not path:
        return None
    if path not in _IM6_CONVERT_CHECKED:
        try:
            out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10).stdout
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        first = out.strip().splitlines()[0] if out.strip() else ""
        _IM6_CONVERT_CHECKED[path] = first.startswith("Version: ImageMagick 6.")
    return path if _IM6_CONVERT_CHECKED[path] else None


def which_magick():
    """The ImageMagick command every tool runs: `magick` (ImageMagick 7), else
    ImageMagick 6's `convert`. Pass commands through run() (or magick_argv) so an
    IM7-style `magick identify ...` reaches IM6's own `identify`."""
    return shutil.which("magick") or _im6_convert()


def magick_kind():
    """"magick", "imagemagick6" (convert/identify, no magick command) or None."""
    if shutil.which("magick"):
        return "magick"
    return "imagemagick6" if _im6_convert() else None


def magick_argv(cmd):
    """IM7-style argv -> the argv that runs on this machine. With `magick`, unchanged.
    With ImageMagick 6, `convert identify ...` becomes `identify ...` (likewise compare,
    montage, composite) and `convert convert ...` becomes `convert ...`; everything else
    is already convert's own syntax. A list of argvs is mapped item by item."""
    if not cmd:
        return cmd
    if isinstance(cmd[0], list):
        return [magick_argv(c) for c in cmd]
    if len(cmd) < 2 or cmd[1] not in IM6_SUBCOMMANDS or os.path.basename(cmd[0]) != "convert":
        return cmd
    if shutil.which("magick") or cmd[0] != _im6_convert():
        return cmd
    if cmd[1] == "convert":
        return [cmd[0]] + list(cmd[2:])
    return [shutil.which(cmd[1]) or cmd[1]] + list(cmd[2:])


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
    cmd = magick_argv(cmd)
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


EXT_TO_MAGICK_FORMAT = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "heic": "HEIC",
    "heif": "HEIC",
    "gif": "GIF",
    "bmp": "BMP",
    "tif": "TIFF",
    "tiff": "TIFF",
}


def verify_output_format(output_path, backend):
    """After a magick-backed write, confirm the output's actual format matches its
    extension.

    magick can "succeed" (exit 0, only a stderr warning) while writing the
    *input* format under the requested output name when it has no encode
    delegate for the target format - e.g. writing to .heic on a build whose
    HEIC support is read-only. Without this check that shows up as ok:true for
    a mislabeled file instead of the failure it actually is. sips is skipped:
    it's restricted to a small, known-writable set of formats already (see
    convert.py's SIPS_FORMATS), so this class of silent-fallback isn't a
    concern there.
    """
    if backend != "magick":
        return
    ext = os.path.splitext(output_path)[1].lstrip(".").lower()
    expected = EXT_TO_MAGICK_FORMAT.get(ext)
    if not expected:
        return
    magick = which_magick()
    result = run([magick, "identify", "-format", "%m", output_path])
    actual = result["stdout"].strip().upper()
    if actual != expected:
        os.remove(output_path)
        raise ImageSkillError(
            f"expected to write {expected} but got {actual or 'an unreadable file'} instead "
            f"(likely no {expected} encode delegate on this system - run doctor to check write support)"
        )


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


NO_BACKEND = "no usable backend: install ImageMagick (magick) or, on macOS, use sips"

GRAVITIES = ("northwest", "north", "northeast", "west", "center", "east", "southwest", "south", "southeast")

# Output formats that can carry an alpha channel; a transparent fill into anything
# else (JPEG, BMP) would silently turn black or white, so tools refuse it instead.
ALPHA_CAPABLE_EXTS = {"png", "webp", "gif", "tif", "tiff", "heic", "heif", "avif", "ico"}


def ext_of(path):
    return os.path.splitext(path)[1].lstrip(".").lower()


def require_input(path, label="input"):
    if not os.path.isfile(path):
        raise ImageSkillError(f"{label} not found: {path}")


def prepare_output(input_paths, output_path, overwrite):
    """The output rules every writing tool shares: never an input, never an existing
    file unless --overwrite, and its directory must already exist."""
    for path in input_paths:
        check_output_not_input(path, output_path)
    check_output_not_exists(output_path, allow_overwrite=overwrite)
    parent = os.path.dirname(os.path.abspath(output_path))
    if not os.path.isdir(parent):
        raise ImageSkillError(f"output directory does not exist: {parent}")


def add_output_args(parser, output_required=True, output_help=None):
    parser.add_argument(
        "-o",
        "--output",
        required=output_required,
        help=output_help or "file to write; must differ from the input, extension picks the format",
    )
    parser.add_argument("--overwrite", action="store_true", help="allow replacing an existing output file")
    parser.add_argument("--json", action="store_true", help="print one JSON object (ok:true/false) instead of text")
    parser.add_argument("--dry-run", action="store_true", help="print the backend command that would run, write nothing")


def select_backend(sips_ok):
    """Return ("magick", path) or, when magick is missing and sips can do this job,
    ("sips", path). sips_ok is True or a string explaining why sips cannot."""
    magick = which_magick()
    if magick:
        return "magick", magick
    sips = which_sips()
    if sips and sips_ok is True:
        return "sips", sips
    if sips:
        raise ImageSkillError(f"needs ImageMagick (magick): {sips_ok}")
    raise ImageSkillError(NO_BACKEND)


def finish_output(path, backend):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise ImageSkillError(f"backend reported success but {path} is missing or empty")
    verify_output_format(path, backend)


def magick_info(magick, path, fmt, auto_orient=True):
    """Read properties of the first frame, as displayed (EXIF orientation applied),
    through `magick in[0] -auto-orient -format FMT info:`."""
    cmd = [magick, f"{path}[0]"] + (["-auto-orient"] if auto_orient else []) + ["-format", fmt, "info:"]
    return run(cmd)["stdout"]


def oriented_dims(path):
    """(width, height) as displayed. Geometry a tool computes (crop boxes, canvases)
    must use these, since every magick write applies -auto-orient first."""
    magick = which_magick()
    if magick:
        w, h = magick_info(magick, path, "%w %h").split()
        return int(w), int(h)
    return identify_dims(path)


_COLOR_RE = re.compile(
    r"^(#[0-9a-fA-F]{3,4}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|[a-zA-Z]+[0-9]{0,2}"
    r"|(?:s?rgba?|hsla?)\(\s*[0-9.]+%?\s*(?:,\s*[0-9.]+%?\s*){2,3}\))$"
)


def color_arg(value):
    """argparse type for a fill colour: a name (white, none), #RGB/#RGBA/#RRGGBB/
    #RRGGBBAA, or rgb()/rgba()/hsl()/hsla(). Anything else is refused rather than
    handed to ImageMagick's option parser."""
    if not _COLOR_RE.match(value.strip()):
        raise argparse.ArgumentTypeError(
            f"invalid color {value!r}: use a name (white, none), #RRGGBB, #RRGGBBAA, or rgb(...)/rgba(...)"
        )
    return value.strip()


def color_is_transparent(color):
    c = color.lower().replace(" ", "")
    if c in ("none", "transparent"):
        return True
    if re.fullmatch(r"#[0-9a-f]{4}", c):
        return c[-1] != "f"
    if re.fullmatch(r"#[0-9a-f]{8}", c):
        return c[-2:] != "ff"
    m = re.fullmatch(r"(?:s?rgba|hsla)\(([^)]*)\)", c)
    if m:
        alpha = m.group(1).split(",")[-1]
        try:
            return (float(alpha[:-1]) / 100 if alpha.endswith("%") else float(alpha)) < 1
        except ValueError:
            return True
    return False


def ratio_arg(value):
    """argparse type for an aspect ratio "W:H" (e.g. 16:9, 1:1, 1.91:1)."""
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*:\s*([0-9]*\.?[0-9]+)\s*", value)
    if not m or float(m.group(1)) <= 0 or float(m.group(2)) <= 0:
        raise argparse.ArgumentTypeError(f"invalid aspect ratio {value!r}: use W:H, e.g. 16:9")
    return float(m.group(1)), float(m.group(2))


def positive_int(value):
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {value!r}")
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be greater than 0, got {n}")
    return n


def non_negative_int(value):
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a whole number, got {value!r}")
    if n < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more, got {n}")
    return n


def gravity_offset(gravity, outer_w, outer_h, inner_w, inner_h):
    """Top-left (x, y) of an inner box placed inside an outer one by gravity."""
    free_w, free_h = outer_w - inner_w, outer_h - inner_h
    x = 0 if gravity.endswith("west") else free_w if gravity.endswith("east") else free_w // 2
    y = 0 if gravity.startswith("north") else free_h if gravity.startswith("south") else free_h // 2
    return x, y


def escape_magick_text(text):
    """Make text render literally in label:/-annotate. ImageMagick expands %-escapes
    (%w, %[EXIF:...]), processes backslash escapes, and reads a *file* when the text
    starts with '@' - so user text is escaped rather than passed through."""
    escaped = text.replace("\\", "\\\\").replace("%", "%%")
    if escaped.startswith("@"):
        escaped = "\\" + escaped
    return escaped


# First existing file wins. "default" must cover Latin text; "cjk" must cover Japanese,
# Chinese and Korean, since a Latin-only font renders them as empty boxes.
FONT_CANDIDATES = {
    "default": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arial.ttf",
    ],
    "cjk": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "C:\\Windows\\Fonts\\YuGothM.ttc",
        "C:\\Windows\\Fonts\\msgothic.ttc",
    ],
}

_CJK_RE = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff66-\uff9f]")


def find_fonts():
    return {kind: next((p for p in paths if os.path.isfile(p)), None) for kind, paths in FONT_CANDIDATES.items()}


def needs_cjk_font(text):
    return bool(_CJK_RE.search(text))


def resolve_font(text, explicit=None):
    """Font file for rendering `text`: the caller's --font if given (must exist),
    else a CJK-capable font when the text needs one, else the default font."""
    if explicit:
        if not os.path.isfile(explicit):
            raise ImageSkillError(f"font file not found: {explicit}")
        return explicit
    fonts = find_fonts()
    if needs_cjk_font(text):
        if not fonts["cjk"]:
            raise ImageSkillError(
                "the text contains Japanese/Chinese/Korean characters but no CJK font was found; "
                "pass --font /path/to/font.ttc (doctor --json lists fonts)"
            )
        return fonts["cjk"]
    if not fonts["default"]:
        raise ImageSkillError("no usable font found; pass --font /path/to/font.ttf (doctor --json lists fonts)")
    return fonts["default"]


def exif_blob_has_gps(blob):
    """True/False for whether an EXIF block holds GPS coordinates, None if it can't be
    parsed. Accepts the block as ImageMagick emits it for any format: "Exif\0\0" + TIFF
    (JPEG, WebP), a bare TIFF (HEIC on ImageMagick 6), or HEIF's 4-byte offset prefix.
    Parsed here rather than trusting %[EXIF:GPSLatitude], which ImageMagick 6 leaves
    empty for HEIC even when the file carries GPS."""
    if not blob:
        return False
    starts = [i for i in (0, 4, 6, 10) if blob[i:i + 4] in (b"II*\x00", b"MM\x00*")]
    if not starts:
        return None
    tiff = blob[starts[0]:]
    try:
        endian = "<" if tiff[:2] == b"II" else ">"
        (ifd0,) = struct.unpack(endian + "I", tiff[4:8])
        (count,) = struct.unpack(endian + "H", tiff[ifd0:ifd0 + 2])
        gps_ifd = None
        for n in range(count):
            entry = tiff[ifd0 + 2 + 12 * n: ifd0 + 14 + 12 * n]
            tag, _type, _count, value = struct.unpack(endian + "HHII", entry)
            if tag == 0x8825:
                gps_ifd = value
                break
        if gps_ifd is None:
            return False
        (gps_count,) = struct.unpack(endian + "H", tiff[gps_ifd:gps_ifd + 2])
        tags = {struct.unpack(endian + "H", tiff[gps_ifd + 2 + 12 * n: gps_ifd + 4 + 12 * n])[0] for n in range(gps_count)}
    except struct.error:
        return None
    return bool(tags & {2, 4})  # GPSLatitude / GPSLongitude


def image_has_gps(magick, path):
    """True/False/None for GPS in an image's EXIF, via the raw profile (`exif:-`)."""
    proc = subprocess.run([magick, f"{path}[0]", "exif:-"], capture_output=True, timeout=120)
    if proc.returncode != 0 or not proc.stdout:
        # "no APP1 data is available": the image has no EXIF block at all
        return False
    return exif_blob_has_gps(proc.stdout)
