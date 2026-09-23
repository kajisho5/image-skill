#!/usr/bin/env python3
"""Create the synthetic input files the agent eval prompts refer to (FIXTURES/...).

    python3 evals/write_fixtures.py DIR

Everything is generated here - gradients, shapes and a hand-built EXIF/GPS block - so no
photo of a real person or place is involved. Needs ImageMagick (`magick`) for the JPEGs.
"""
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from fixtures import write_bordered_png, write_jpeg_with_gps, write_png  # noqa: E402


def gradient(w, h, a, b):
    def pixel(x, y):
        t = (x / max(1, w - 1) + y / max(1, h - 1)) / 2
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return pixel


def main(argv):
    if len(argv) != 1:
        print("usage: write_fixtures.py DIR", file=sys.stderr)
        return 2
    magick = shutil.which("magick")
    if not magick:
        print("write_fixtures.py needs ImageMagick (magick) on PATH", file=sys.stderr)
        return 1
    out = os.path.abspath(argv[0])
    os.makedirs(os.path.join(out, "photos"), exist_ok=True)

    base = os.path.join(out, "_hero.png")
    write_png(base, 1600, 1200, gradient(1600, 1200, (250, 160, 60), (40, 60, 160)))
    write_jpeg_with_gps(magick, base, os.path.join(out, "hero.jpg"), lat_deg=35.0, lon_deg=139.0)
    os.remove(base)
    os.remove(os.path.join(out, "hero.jpg.plain.jpg"))

    write_bordered_png(os.path.join(out, "screenshot.png"), 900, 700, 60)

    def logo(x, y):
        return (220, 40, 90) if (x - 256) ** 2 + (y - 150) ** 2 < 120 ** 2 else (255, 255, 255)
    write_png(os.path.join(out, "logo.png"), 512, 300, logo)

    for i, (a, b) in enumerate([((20, 120, 80), (230, 230, 120)), ((90, 20, 140), (240, 150, 200)), ((10, 10, 10), (200, 200, 200))]):
        tmp = os.path.join(out, f"_p{i}.png")
        write_png(tmp, 640, 480, gradient(640, 480, a, b))
        write_jpeg_with_gps(magick, tmp, os.path.join(out, "photos", f"photo{i + 1}.jpg"))
        os.remove(tmp)
        os.remove(os.path.join(out, "photos", f"photo{i + 1}.jpg.plain.jpg"))
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
