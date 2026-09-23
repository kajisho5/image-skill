"""overlay.py, montage.py, adjust.py, icons.py and preset.py."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import adjust  # noqa: E402
import icons  # noqa: E402
import montage  # noqa: E402
import overlay  # noqa: E402
import preset  # noqa: E402
from _common import ImageSkillError, find_fonts, identify_dims, which_magick  # noqa: E402
from fixtures import write_png  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GRAY, RED, WHITE = (128, 128, 128), (255, 0, 0), (255, 255, 255)


def mean_rgb(path, x, y, w, h):
    # -colorspace sRGB first: ImageMagick 7 writes an all-grey result as a one-channel
    # greyscale PNG, and reading .g/.b of that image gives 0, not the grey value.
    fmt = ",".join(f"%[fx:int(255*mean.{c})]" for c in "rgb")
    out = subprocess.run([which_magick(), path, "-colorspace", "sRGB", "-crop", f"{w}x{h}+{x}+{y}", "+repage",
                          "-format", fmt, "info:"],
                         capture_output=True, text=True, check=True).stdout
    return tuple(int(v) for v in out.split(","))


class PresetDataTests(unittest.TestCase):
    def test_every_preset_cites_a_source(self):
        presets = preset.load_presets()
        self.assertIn("og", presets)
        for name, spec in presets.items():
            with self.subTest(preset=name):
                self.assertGreater(spec["width"], 0)
                self.assertGreater(spec["height"], 0)
                self.assertTrue(spec["source"].startswith("https://"))
                self.assertTrue(spec["quote"].strip())

    def test_no_preset_without_an_official_source(self):
        # X/Twitter's docs no longer state a card image size; see presets.json "_about".
        self.assertFalse([n for n in preset.load_presets() if n.startswith(("x-", "twitter"))])

    def test_list_needs_no_input(self):
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "preset.py"), "--list", "--json"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["presets"]["og"]["width"], 1200)


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = self.path("base.png")
        write_png(self.base, 400, 200, lambda x, y: GRAY)
        self.logo = self.path("logo.png")
        write_png(self.logo, 40, 20, lambda x, y: RED)

    def path(self, name):
        return os.path.join(self.tmp.name, name)

    def test_image_overlay_lands_in_the_corner_with_margin(self):
        payload = overlay.run_overlay(overlay.build_parser().parse_args(
            [self.base, "-o", self.path("o.png"), "--image", self.logo, "--position", "southeast", "--margin", "10"]))
        self.assertEqual(payload["overlay"], {"width": 40, "height": 20})
        self.assertEqual(identify_dims(self.path("o.png")), (400, 200))
        self.assertEqual(mean_rgb(self.path("o.png"), 350, 170, 40, 20), RED)
        self.assertEqual(mean_rgb(self.path("o.png"), 391, 191, 9, 9), GRAY)

    def test_opacity_blends(self):
        overlay.run_overlay(overlay.build_parser().parse_args(
            [self.base, "-o", self.path("o.png"), "--image", self.logo, "--position", "center", "--opacity", "0.5"]))
        r, g, b = mean_rgb(self.path("o.png"), 190, 95, 20, 10)
        self.assertTrue(180 <= r <= 200 and 55 <= g <= 75, (r, g, b))

    def test_overlay_larger_than_base_is_refused(self):
        with self.assertRaises(ImageSkillError):
            overlay.run_overlay(overlay.build_parser().parse_args(
                [self.logo, "-o", self.path("o.png"), "--image", self.base, "--position", "center"]))

    @unittest.skipUnless(find_fonts()["default"], "requires a font")
    def test_text_needs_size_and_color_and_is_drawn(self):
        with self.assertRaises(ImageSkillError):
            overlay.run_overlay(overlay.build_parser().parse_args(
                [self.base, "-o", self.path("t.png"), "--text", "hi", "--position", "center"]))
        payload = overlay.run_overlay(overlay.build_parser().parse_args(
            [self.base, "-o", self.path("t.png"), "--text", "@name 100%", "--font-size", "30", "--color", "white",
             "--position", "northwest", "--margin", "5"]))
        self.assertEqual(payload["kind"], "text")
        self.assertGreater(mean_rgb(self.path("t.png"), 5, 5, payload["overlay"]["width"], payload["overlay"]["height"])[0], 128)

    @unittest.skipUnless(find_fonts()["cjk"], "requires a CJK font")
    def test_japanese_text_picks_a_cjk_font(self):
        payload = overlay.run_overlay(overlay.build_parser().parse_args(
            [self.base, "-o", self.path("j.png"), "--text", "撮影 2026", "--font-size", "24", "--color", "white",
             "--position", "south"]))
        self.assertEqual(payload["font"], find_fonts()["cjk"])

    def test_adjust_changes_pixels_not_size(self):
        payload = adjust.run_adjust(adjust.build_parser().parse_args(
            [self.base, "-o", self.path("a.png"), "--brightness", "40"]))
        self.assertEqual(payload["actual"], {"width": 400, "height": 200})
        self.assertGreater(mean_rgb(self.path("a.png"), 0, 0, 400, 200)[0], GRAY[0] + 20)
        adjust.run_adjust(adjust.build_parser().parse_args([self.logo, "-o", self.path("s.png"), "--saturation", "0"]))
        r, g, b = mean_rgb(self.path("s.png"), 0, 0, 40, 20)
        self.assertTrue(abs(r - g) <= 2 and abs(g - b) <= 2, (r, g, b))

    def test_adjust_needs_an_operation_and_valid_ranges(self):
        with self.assertRaises(ImageSkillError):
            adjust.run_adjust(adjust.build_parser().parse_args([self.base, "-o", self.path("a.png")]))
        for bad in (["--contrast", "150"], ["--levels", "90,10"], ["--blur", "0"]):
            with self.assertRaises(ImageSkillError, msg=bad):
                adjust.run_adjust(adjust.build_parser().parse_args([self.base, "-o", self.path("a.png")] + bad))

    def test_montage_grid_size_and_background(self):
        payload = montage.run_montage(montage.build_parser().parse_args(
            [self.base, self.logo, self.logo, "--cols", "2", "--gap", "10", "--background", "white",
             "-o", self.path("m.png")]))
        self.assertEqual(payload["cell"], {"width": 400, "height": 200})
        self.assertEqual(identify_dims(self.path("m.png")), (810, 410))
        self.assertEqual(mean_rgb(self.path("m.png"), 400, 0, 10, 200), WHITE)  # the gap
        self.assertEqual(mean_rgb(self.path("m.png"), 590, 90, 20, 10), RED)  # logo centred in cell 2

    def test_montage_refuses_transparent_jpeg(self):
        with self.assertRaises(ImageSkillError):
            montage.run_montage(montage.build_parser().parse_args(
                [self.base, self.logo, "--background", "none", "-o", self.path("m.jpg")]))

    def test_icons_write_every_size(self):
        square = self.path("sq.png")
        write_png(square, 512, 512, lambda x, y: RED)
        out_dir = self.path("icons")
        payload = icons.run_icons(icons.build_parser().parse_args([square, "-o", out_dir]))
        names = sorted(os.path.basename(f["path"]) for f in payload["files"])
        self.assertEqual(names, ["apple-touch-icon.png", "favicon.ico", "icon-192x192.png", "icon-32x32.png",
                                 "icon-512x512.png"])
        frames = subprocess.run([which_magick(), "identify", "-format", "%w\n", os.path.join(out_dir, "favicon.ico")],
                                capture_output=True, text=True, check=True).stdout.split()
        self.assertEqual(sorted(int(f) for f in frames), [16, 32, 48])
        self.assertEqual(identify_dims(os.path.join(out_dir, "apple-touch-icon.png")), (180, 180))
        self.assertTrue(any("apple-touch-icon" in h for h in payload["html"]))
        self.assertEqual([m["sizes"] for m in payload["manifest_icons"]], ["192x192", "512x512"])

    def test_icons_refuse_non_square_and_upscaling(self):
        with self.assertRaises(ImageSkillError):
            icons.run_icons(icons.build_parser().parse_args([self.base, "-o", self.path("i1")]))
        small = self.path("small.png")
        write_png(small, 64, 64, lambda x, y: RED)
        with self.assertRaises(ImageSkillError):
            icons.run_icons(icons.build_parser().parse_args([small, "-o", self.path("i2")]))

    def test_preset_modes(self):
        payload = preset.run_preset(preset.build_parser().parse_args(
            [self.base, "-o", self.path("og.png"), "--preset", "og", "--mode", "fill"]))
        self.assertEqual(payload["actual"], {"width": 1200, "height": 630})
        self.assertEqual(payload["via"], ["resize"])
        payload = preset.run_preset(preset.build_parser().parse_args(
            [self.base, "-o", self.path("sq.png"), "--preset", "instagram-square", "--mode", "pad", "--color", "white"]))
        self.assertEqual(payload["actual"], {"width": 1080, "height": 1080})
        self.assertEqual(payload["via"], ["resize", "pad"])
        self.assertEqual([f for f in os.listdir(self.tmp.name) if "preset-fit" in f], [])
        with self.assertRaises(ImageSkillError):
            preset.run_preset(preset.build_parser().parse_args(
                [self.base, "-o", self.path("x.png"), "--preset", "og", "--mode", "pad"]))


if __name__ == "__main__":
    unittest.main()
