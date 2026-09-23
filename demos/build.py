#!/usr/bin/env python3
"""Rebuild every README demo from scratch: python3 demos/build.py

Development-only. It needs ImageMagick (`magick`, or IM6's `convert` behind a `magick`
shim) and, for the HEIC source, either a HEIC-writing ImageMagick or `heif-enc`
(libheif-examples). The skill itself never needs any of this.

Every input is drawn here by ImageMagick - a synthetic landscape and a synthetic logo -
so no photograph, person or third-party artwork is involved. Every "after" is the real
output of the skill's own scripts, and every number printed on a frame is read from that
script's --json result: nothing on a frame is typed in by hand.

Writes:
  docs/demos/*.gif     the four README demos
  docs/demos.md        the gallery: each GIF with the exact commands and their results
  assets/logo.png      the README banner (and demos/.work/logo-1024.png, the icon source)
Scratch files go to demos/.work/ (git-ignored).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from _common import escape_magick_text, find_fonts, which_magick  # noqa: E402
from fixtures import write_jpeg_with_gps  # noqa: E402

WORK = os.path.join(ROOT, "demos", ".work")
OUT = os.path.join(ROOT, "docs", "demos")
ASSETS = os.path.join(ROOT, "assets")

W, H = 960, 540                 # frame size
IMG_TOP, IMG_H = 60, 340        # picture area
BG, FG, DIM, ACCENT, BAD = "#0f172a", "#f8fafc", "#94a3b8", "#fbbf24", "#f87171"
DELAY = 220                     # 1/100 s per frame

MONO_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Menlo.ttc",
]
BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


class Demo:
    """Commands run and results kept for one demo, in the order they happened."""

    def __init__(self, key, title, gif, alt):
        self.key, self.title, self.gif, self.alt = key, title, gif, alt
        self.steps = []   # (display command, result dict)
        self.frames = []


def die(msg):
    sys.exit(f"demos/build.py: {msg}")


def first_font(candidates, fallback):
    return next((p for p in candidates if os.path.isfile(p)), fallback)


MAGICK = None
FONT = MONO = BOLD = None


def magick(*args):
    subprocess.run([MAGICK, *args], check=True, cwd=WORK)


def tool(demo, name, *args, expect_ok=True):
    """Run scripts/<name>.py inside WORK with --json and record it for docs/demos.md."""
    argv = [sys.executable, os.path.join(SCRIPTS, f"{name}.py"), *args, "--json"]
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=WORK)
    try:
        result = json.loads(proc.stdout)
    except ValueError:
        die(f"{name} printed no JSON (exit {proc.returncode}): {proc.stderr.strip()}")
    if bool(result.get("ok")) != expect_ok:
        die(f"{name} {' '.join(args)}: expected ok={expect_ok}, got {json.dumps(result)}")
    display = " ".join(["python3", f"scripts/{name}.py", *[_quote(a) for a in args]])
    demo.steps.append((display, result))
    return result, display


def _quote(arg):
    return f'"{arg}"' if (" " in arg or not arg) else arg


def text_args(font, size, color, gravity, x, y, text):
    return ["-font", font, "-pointsize", str(size), "-fill", color, "-gravity", gravity,
            "-annotate", f"+{x}+{y}", escape_magick_text(text)]


def frame(demo, step, picture_args, lines):
    """One GIF frame: title bar, a picture area built by `picture_args` (magick args that
    leave exactly one image of any size on the stack), and up to four caption lines as
    (text, colour) pairs."""
    n = len(demo.frames) + 1
    path = os.path.join(WORK, f"{demo.key}-{n:02d}.png")
    args = ["-size", f"{W}x{H}", f"xc:{BG}",
            "(", *picture_args, "-resize", f"{W - 40}x{IMG_H}>", ")",
            "-gravity", "north", "-geometry", f"+0+{IMG_TOP}", "-compose", "over", "-composite"]
    args += text_args(BOLD, 22, FG, "northwest", 20, 16, demo.title)
    args += text_args(MONO, 18, DIM, "northeast", 20, 18, step)
    y = IMG_TOP + IMG_H + 16
    for text, color in lines[:4]:
        args += text_args(MONO, 16, color, "northwest", 20, y, text)
        y += 27
    magick(*args, path)
    demo.frames.append(path)


def fit(path, w, h):
    return [f"{path}[0]", "-auto-orient", "-resize", f"{w}x{h}"]


def checker_under(path, w, h):
    """An image with transparency shown over a checkerboard the image's own size."""
    return [f"{path}[0]", "-resize", f"{w}x{h}", "(", "+clone", "-tile", "pattern:checkerboard",
            "-draw", "color 0,0 reset", ")", "+swap", "-compose", "over", "-composite"]


def row(items, gap=24, label_color=FG, bg=BG):
    """[(magick args producing one image, label)] side by side, each label underneath."""
    out = ["(", "-background", bg]
    for i, (picture, label) in enumerate(items):
        out += ["(", *picture, "-background", bg, "-fill", label_color, "-font", MONO,
                "-pointsize", "16", "-gravity", "center", "+size", f"label:{escape_magick_text(label)}", "-append"]
        if i:
            out += ["-gravity", "west", "-splice", f"{gap}x0"]
        out += [")"]
    out += ["-gravity", "center", "+append", ")"]
    return out


def kb(n):
    return f"{n / 1000:.1f} KB" if n < 1_000_000 else f"{n / 1_000_000:.2f} MB"


# ---------------------------------------------------------------- sources


def make_sources():
    """Synthetic landscape (with GPS EXIF) as JPEG and HEIC, and a synthetic logo."""
    magick("-size", "2400x1800", "gradient:#1d3b6e-#f39c5a",
           "-fill", "#ffd27a", "-draw", "circle 1650,980 1650,1130",
           "-fill", "#5b4a7a", "-draw", "polygon 0,1150 400,760 800,1050 1200,700 1700,1100 2100,850 2400,1050 2400,1800 0,1800",
           "-fill", "#2e2a4f", "-draw", "polygon 0,1420 500,1180 1000,1380 1500,1220 2000,1440 2400,1320 2400,1800 0,1800",
           "-fill", "#34507f", "-draw", "rectangle 0,1560 2400,1800",
           "-seed", "7", "-attenuate", "0.25", "+noise", "Gaussian", "landscape.png")
    # GPS block from the test fixtures (a made-up coordinate, not a real photo location)
    write_jpeg_with_gps(MAGICK, os.path.join(WORK, "landscape.png"), os.path.join(WORK, "photo.jpg"), 35.0, 135.0)
    heic = os.path.join(WORK, "photo.heic")
    heif_enc = shutil.which("heif-enc")
    if heif_enc:  # keeps the EXIF block, as an iPhone HEIC has
        subprocess.run([heif_enc, "-q", "60", "photo.jpg", "-o", "photo.heic"], check=True,
                       cwd=WORK, capture_output=True)
    else:
        magick("photo.jpg", "-quality", "60", heic)

    size = 1024
    magick("-size", f"{size}x{size}", "gradient:#7c3aed-#f97316",
           "(", "-size", f"{size}x{size}", "xc:black", "-fill", "white",
           "-draw", "roundrectangle 48,48 975,975 190,190", ")",
           "-alpha", "off", "-compose", "CopyOpacity", "-composite", "-compose", "over",
           "-fill", "white", "-draw", "circle 650,370 650,480",
           "-draw", "polygon 190,800 430,470 560,640 670,520 840,800",
           "-fill", "#ffffff99", "-draw", "rectangle 190,812 840,850",
           "logo-1024.png")


# ---------------------------------------------------------------- demos


def demo_heic_og():
    d = Demo("heic_og", "HEIC photo -> 1200x630 OG WebP, GPS removed", "heic_og.gif",
             "an iPhone-style HEIC turned into an Open Graph WebP with the GPS removed")
    src, _ = tool(d, "probe", "photo.heic")
    if not src["has_gps"]:
        die("the synthetic HEIC lost its EXIF GPS; install heif-enc (libheif-examples)")
    frame(d, "1/4", fit("photo.heic", W - 40, IMG_H), [
        ("$ python3 scripts/probe.py photo.heic --json", DIM),
        (f"-> {src['width']}x{src['height']} {src['format']}", FG),
        (f"   has_gps: {str(src['has_gps']).lower()}   (location is in the file)", BAD),
    ])
    og, cmd = tool(d, "preset", "photo.heic", "-o", "og.webp", "--preset", "og", "--mode", "fill")
    mid, _ = tool(d, "probe", "og.webp")
    frame(d, "2/4", fit("og.webp", W - 40, IMG_H), [
        ("$ " + cmd + " --json", DIM),
        (f"-> {og['actual']['width']}x{og['actual']['height']} {mid['format']}  ({og['description']})", FG),
        (f"   has_gps: {str(mid['has_gps']).lower()}   (resizing alone keeps EXIF)", BAD if mid["has_gps"] else FG),
    ])
    clean, cmd = tool(d, "strip", "og.webp", "-o", "og-clean.webp")
    frame(d, "3/4", fit("og-clean.webp", W - 40, IMG_H), [
        ("$ " + cmd + " --json", DIM),
        ("-> og-clean.webp written, og.webp and photo.heic untouched", FG),
        (f"   has_gps: {str(clean['has_gps']).lower()}", ACCENT),
    ])
    chk, cmd = tool(d, "check", "og-clean.webp", "--input", "photo.heic",
                    "--expect-width", "1200", "--expect-height", "630", "--expect-format", "webp")
    frame(d, "4/4", row([(fit("photo.heic", 420, 300), "photo.heic (kept)"),
                         (fit("og-clean.webp", 420, 300), "og-clean.webp")]), [
        ("$ python3 scripts/check.py og-clean.webp --input photo.heic \\", DIM),
        ("    --expect-width 1200 --expect-height 630 --expect-format webp --json", DIM),
        (f"-> ok: {str(chk['ok']).lower()}   {chk['width']}x{chk['height']} {chk['format']}", ACCENT),
    ])
    return d


def demo_optimize():
    d = Demo("optimize", "optimize --max-kb: same pixels size, smaller file", "optimize.gif",
             "a photo re-encoded to 800, 400 and 200 KB budgets, and an honest failure at 100 KB")
    src, _ = tool(d, "probe", "photo.jpg")
    original = os.path.getsize(os.path.join(WORK, "photo.jpg"))
    zoom = ["-gravity", "northwest", "-crop", "300x300+1500+830", "+repage", "-scale", "100%"]

    def panel(path, label):
        return row([(fit(path, 440, 310), f"{src['width']}x{src['height']}"),
                    ([f"{path}[0]", *zoom], "detail at 100%")], label_color=DIM)

    frame(d, "1/5", panel("photo.jpg", "original"), [
        ("photo.jpg: the original", FG),
        (f"-> {kb(original)}   {src['width']}x{src['height']} {src['format']}", FG),
    ])
    smallest = None
    for i, budget in enumerate(("400", "200", "100"), start=2):
        res, cmd = tool(d, "optimize", "photo.jpg", "-o", f"photo-{budget}kb.jpg", "--max-kb", budget)
        smallest = min([a["bytes"] for a in res["attempts"]] + ([smallest] if smallest else []))
        frame(d, f"{i}/5", panel(f"photo-{budget}kb.jpg", budget), [
            ("$ " + cmd + " --json", DIM),
            (f"-> {kb(res['bytes'])} (budget {budget} KB)   quality {res['quality']}   "
             f"{res['actual']['width']}x{res['actual']['height']} unchanged", ACCENT),
            (f"   {len(res['attempts'])} encodes searched; {kb(original)} original kept", FG),
        ])
    # a budget below the smallest encode the search can make (quality 40) on this build
    too_small = str(max(1, int(smallest / 1000 * 0.7)))
    res, cmd = tool(d, "optimize", "photo.jpg", "-o", f"photo-{too_small}kb.jpg", "--max-kb", too_small,
                    expect_ok=False)
    reason = res["reason"]
    frame(d, "5/5", panel("photo-100kb.jpg", "last good"), [
        ("$ " + cmd + " --json", DIM),
        (f"-> ok: false, nothing written", BAD),
        ("   " + reason.split(" - ")[0], BAD),
        ("   " + (reason.split(" - ")[1] if " - " in reason else ""), FG),
    ])
    return d


def demo_compare():
    d = Demo("compare", "compare: SSIM, changed pixels and a heatmap", "compare.gif",
             "two versions of an image and the heatmap compare.py wrote for them")
    tool(d, "resize", "photo.jpg", "-o", "before.png", "--width", "1200", "--height", "900")
    tool(d, "overlay", "before.png", "-o", "after.png", "--text", "DRAFT v2", "--position", "southeast",
         "--margin", "40", "--font-size", "64", "--color", "white", "--opacity", "0.8")
    res, cmd = tool(d, "compare", "before.png", "after.png", "-o", "heatmap.png")
    facts = (f"-> ssim {res['ssim']:.4f}   psnr {res['psnr_db']:.1f} dB   "
             f"changed {res['diff_ratio'] * 100:.2f}% ({res['diff_pixels']} px)")
    frame(d, "1/3", fit("before.png", W - 40, IMG_H), [("before.png", FG)])
    frame(d, "2/3", fit("after.png", W - 40, IMG_H), [
        ("after.png - spot the difference?", FG),
    ])
    frame(d, "3/3", fit("heatmap.png", W - 40, IMG_H), [
        ("$ " + cmd + " --json", DIM),
        (facts, ACCENT),
        ("   heatmap: dimmed before.png, changes from blue (small) to yellow (large)", FG),
    ])
    return d


def demo_icons():
    d = Demo("icons", "icons: favicon.ico, PWA and apple-touch icons", "icons.gif",
             "one square logo turned into favicon.ico, PNG icons and apple-touch-icon.png")
    res, cmd = tool(d, "icons", "logo-1024.png", "-o", "icons")
    frame(d, "1/3", checker_under("logo-1024.png", 320, 320), [
        ("logo-1024.png: one square source, transparent corners", FG),
        ("$ " + cmd + " --json", DIM),
    ])
    ico = next(f for f in res["files"] if f["purpose"] == "favicon")
    sizes = sorted(ico["sizes"])
    items = []
    for s in sizes:
        idx = ico["sizes"].index(s)
        items.append(([f"icons/favicon.ico[{idx}]", "-scale", "400%", "(", "+clone", "-tile",
                       "pattern:checkerboard", "-draw", "color 0,0 reset", ")", "+swap",
                       "-compose", "over", "-composite"], f"{s}x{s} (x4)"))
    frame(d, "2/3", row(items, gap=40), [
        (f"favicon.ico: {len(sizes)} sizes in one file ({', '.join(map(str, sizes))}), shown 4x", FG),
        (res["html"][0], DIM),
    ])
    pngs = [f for f in res["files"] if f["format"] == "PNG"]
    pngs.sort(key=lambda f: f["sizes"][0])
    items = []
    for f in pngs:
        s = f["sizes"][0]
        rel = os.path.relpath(f["path"], WORK)
        shown = min(s, 256)
        label = f"{s}" if shown == s else f"{s} (shown {round(shown * 100 / s)}%)"
        items.append((checker_under(rel, shown, shown), label))
    frame(d, "3/3", row(items, gap=28), [
        (f"{len(res['files'])} files in icons/:", FG),
        ("  " + ", ".join(os.path.basename(f["path"]) for f in res["files"][:3]) + ",", FG),
        ("  " + ", ".join(os.path.basename(f["path"]) for f in res["files"][3:]), FG),
        ("+ <link> tags and manifest \"icons\" entries in the JSON result", DIM),
    ])
    return d


# ---------------------------------------------------------------- outputs


def write_gif(demo):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, demo.gif)
    magick("-delay", str(DELAY), "-loop", "0", *demo.frames[:-1],
           "-delay", str(DELAY * 2), demo.frames[-1],
           "-dither", "None", "-colors", "160", "-layers", "Optimize", path)
    return path


def write_logo():
    os.makedirs(ASSETS, exist_ok=True)
    path = os.path.join(ASSETS, "logo.png")
    magick("-size", "1280x320", "xc:none",
           "(", "logo-1024.png", "-resize", "240x240", ")", "-gravity", "west", "-geometry", "+40+0",
           "-compose", "over", "-composite",
           *text_args(BOLD, 76, "#7c3aed", "west", 320, -40, "imagemagick-skill"),
           *text_args(FONT, 30, "#64748b", "west", 324, 50, "local image editing for coding agents"),
           path)
    return path


def write_gallery(demos, im_version):
    lines = [
        "# Demos",
        "",
        "Every GIF here is rebuilt by `python3 demos/build.py` (development only: ImageMagick, and",
        "`heif-enc` or a HEIC-writing ImageMagick for the HEIC source). The inputs are drawn by",
        "ImageMagick in that script - a synthetic landscape and a synthetic logo, no photographs, no",
        "people, no third-party artwork - and every number on a frame is read from the `--json`",
        "result of the command shown under it. The results below are from the run that built the",
        f"committed GIFs ({im_version}); another ImageMagick build can land on slightly different",
        "byte counts and qualities.",
        "",
        "Shell examples run in the folder that holds the inputs; `scripts/` is the installed skill's",
        "`scripts/` folder (`~/.claude/skills/imagemagick-skill/scripts` after `npx imagemagick-skill`).",
        "",
    ]
    for d in demos:
        lines += [f"## {d.title}", "", f"![{d.alt}](demos/{d.gif})", "", "```bash"]
        lines += [cmd + " --json" for cmd, _ in d.steps]
        lines += ["```", "", "<details><summary>JSON results</summary>", "", "```json"]
        for cmd, result in d.steps:
            shown = dict(result)
            for key in ("output_dir",):
                if key in shown:
                    shown[key] = os.path.relpath(shown[key], WORK)
            if "files" in shown:
                shown["files"] = [dict(f, path=os.path.relpath(f["path"], WORK)) for f in shown["files"]]
            lines.append(json.dumps(shown, ensure_ascii=False))
        lines += ["```", "", "</details>", ""]
    with open(os.path.join(ROOT, "docs", "demos.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main(argv=None):
    global MAGICK, FONT, MONO, BOLD
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--keep-work", action="store_true", help="keep demos/.work afterwards")
    args = parser.parse_args(argv)
    MAGICK = which_magick()
    if not MAGICK:
        die("ImageMagick (magick) is required to build the demos")
    FONT = find_fonts()["default"]
    if not FONT:
        die("no default font found (see doctor's fonts field)")
    MONO = first_font(MONO_CANDIDATES, FONT)
    BOLD = first_font(BOLD_CANDIDATES, FONT)
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    version = subprocess.run([MAGICK, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    im_version = " ".join(version.split()[1:4])

    make_sources()
    demos = [demo_heic_og(), demo_optimize(), demo_compare(), demo_icons()]
    for d in demos:
        path = write_gif(d)
        print(f"{os.path.relpath(path, ROOT)}  {kb(os.path.getsize(path))}  {len(d.frames)} frames")
    print(os.path.relpath(write_logo(), ROOT))
    write_gallery(demos, im_version)
    print("docs/demos.md")
    if not args.keep_work:
        shutil.rmtree(WORK, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
