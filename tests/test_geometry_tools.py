"""crop.py, pad.py and rotate.py, checked by pixel colour, not only by size."""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import crop  # noqa: E402
import pad  # noqa: E402
import rotate  # noqa: E402
from _common import ImageSkillError, identify_dims, which_magick, which_sips  # noqa: E402
from fixtures import write_png  # noqa: E402

RED, BLUE, BLACK, WHITE = (255, 0, 0), (0, 0, 255), (0, 0, 0), (255, 255, 255)


def pixel(path, x, y):
    out = subprocess.run(
        [which_magick(), path, "-colorspace", "sRGB", "-format",
         f"%[fx:int(255*p{{{x},{y}}}.r)],%[fx:int(255*p{{{x},{y}}}.g)],"
         f"%[fx:int(255*p{{{x},{y}}}.b)],%[fx:p{{{x},{y}}}.a]", "info:"],
        capture_output=True, text=True, check=True,
    ).stdout.split(",")
    return tuple(int(v) for v in out[:3]) + (float(out[3]),)


class PureGeometryTests(unittest.TestCase):
    def test_aspect_box(self):
        self.assertEqual(crop.aspect_box(300, 200, 1, 1, "center"), (50, 0, 200, 200))
        self.assertEqual(crop.aspect_box(300, 200, 1, 1, "west"), (0, 0, 200, 200))
        self.assertEqual(crop.aspect_box(200, 300, 16, 9, "north"), (0, 0, 200, 112))

    def test_aspect_canvas(self):
        self.assertEqual(pad.aspect_canvas(100, 50, 1, 1), (100, 100))
        self.assertEqual(pad.aspect_canvas(100, 100, 16, 9), (178, 100))
        self.assertEqual(pad.aspect_canvas(160, 90, 16, 9), (160, 90))


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # 300x200 white with a 30x20 black block in the top-left corner
        self.src = os.path.join(self.tmp.name, "tl.png")
        write_png(self.src, 300, 200, lambda x, y: BLACK if x < 30 and y < 20 else WHITE)
        self.red = os.path.join(self.tmp.name, "red.png")
        write_png(self.red, 100, 50, lambda x, y: RED)

    def out(self, name):
        return os.path.join(self.tmp.name, name)

    def test_crop_rect_cuts_exact_pixels(self):
        payload = crop.run_crop(crop.build_parser().parse_args(
            [self.src, "-o", self.out("c.png"), "--x", "10", "--y", "5", "--width", "40", "--height", "30"]))
        self.assertEqual(payload["actual"], {"width": 40, "height": 30})
        self.assertEqual(pixel(self.out("c.png"), 19, 14)[:3], BLACK)
        self.assertEqual(pixel(self.out("c.png"), 20, 15)[:3], WHITE)

    def test_crop_never_clips(self):
        with self.assertRaises(ImageSkillError):
            crop.run_crop(crop.build_parser().parse_args(
                [self.src, "-o", self.out("c.png"), "--x", "290", "--y", "0", "--width", "20", "--height", "10"]))

    def test_crop_needs_one_mode(self):
        for argv in (["--aspect", "1:1", "--x", "0"], ["--x", "0", "--y", "0"]):
            with self.assertRaises(ImageSkillError):
                crop.run_crop(crop.build_parser().parse_args([self.src, "-o", self.out("c.png")] + argv))

    def test_pad_places_the_image_where_it_says(self):
        payload = pad.run_pad(pad.build_parser().parse_args(
            [self.red, "-o", self.out("p.png"), "--width", "200", "--height", "100", "--color", "blue",
             "--gravity", "southeast"]))
        self.assertEqual(payload["offset"], {"x": 100, "y": 50})
        self.assertEqual(pixel(self.out("p.png"), 100, 50)[:3], RED)
        self.assertEqual(pixel(self.out("p.png"), 99, 49)[:3], BLUE)

    def test_pad_transparent_stays_transparent_and_is_refused_for_jpeg(self):
        pad.run_pad(pad.build_parser().parse_args(
            [self.red, "-o", self.out("p.png"), "--aspect", "1:1", "--color", "none"]))
        self.assertEqual(identify_dims(self.out("p.png")), (100, 100))
        self.assertEqual(pixel(self.out("p.png"), 50, 5)[3], 0.0)
        self.assertEqual(pixel(self.out("p.png"), 50, 50)[:3], RED)
        with self.assertRaises(ImageSkillError):
            pad.run_pad(pad.build_parser().parse_args(
                [self.red, "-o", self.out("p.jpg"), "--aspect", "1:1", "--color", "none"]))

    def test_pad_never_shrinks_and_needs_a_color(self):
        with self.assertRaises(ImageSkillError):
            pad.run_pad(pad.build_parser().parse_args(
                [self.red, "-o", self.out("p.png"), "--width", "50", "--height", "50", "--color", "white"]))
        with self.assertRaises(ImageSkillError):
            pad.build_parser().parse_args([self.red, "-o", self.out("p.png"), "--aspect", "1:1"])

    def test_rotate_90_moves_the_corner(self):
        payload = rotate.run_rotate(rotate.build_parser().parse_args(
            [self.src, "-o", self.out("r.png"), "--degrees", "90"]))
        self.assertEqual(payload["actual"], {"width": 200, "height": 300})
        self.assertEqual(pixel(self.out("r.png"), 195, 5)[:3], BLACK)
        self.assertEqual(pixel(self.out("r.png"), 5, 5)[:3], WHITE)

    def test_flips(self):
        rotate.run_rotate(rotate.build_parser().parse_args([self.src, "-o", self.out("h.png"), "--flip-horizontal"]))
        self.assertEqual(pixel(self.out("h.png"), 295, 5)[:3], BLACK)
        rotate.run_rotate(rotate.build_parser().parse_args([self.src, "-o", self.out("v.png"), "--flip-vertical"]))
        self.assertEqual(pixel(self.out("v.png"), 5, 195)[:3], BLACK)

    def test_free_angle_needs_background(self):
        with self.assertRaises(ImageSkillError):
            rotate.run_rotate(rotate.build_parser().parse_args([self.src, "-o", self.out("r.png"), "--degrees", "15"]))
        payload = rotate.run_rotate(rotate.build_parser().parse_args(
            [self.src, "-o", self.out("r.png"), "--degrees", "15", "--background", "white"]))
        self.assertGreater(payload["actual"]["width"], 300)


@unittest.skipUnless(which_sips(), "requires macOS sips")
class SipsGeometryTests(unittest.TestCase):
    """The sips paths for the operations sips can do, forced even when magick exists."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "wide.png")
        write_png(self.src, 300, 200, lambda x, y: RED)

    def test_center_crop_pad_and_rotate(self):
        with mock.patch.object(crop, "select_backend", return_value=("sips", which_sips())), \
             mock.patch.object(crop, "oriented_dims", return_value=(300, 200)):
            payload = crop.run_crop(crop.build_parser().parse_args(
                [self.src, "-o", os.path.join(self.tmp.name, "c.png"), "--aspect", "1:1"]))
        self.assertEqual(payload["actual"], {"width": 200, "height": 200})

        with mock.patch.object(pad, "select_backend", return_value=("sips", which_sips())), \
             mock.patch.object(pad, "oriented_dims", return_value=(300, 200)):
            payload = pad.run_pad(pad.build_parser().parse_args(
                [self.src, "-o", os.path.join(self.tmp.name, "p.png"), "--aspect", "1:1", "--color", "#FFFFFF"]))
        self.assertEqual(payload["actual"], {"width": 300, "height": 300})

        with mock.patch.object(rotate, "select_backend", return_value=("sips", which_sips())), \
             mock.patch.object(rotate, "oriented_dims", return_value=(300, 200)):
            payload = rotate.run_rotate(rotate.build_parser().parse_args(
                [self.src, "-o", os.path.join(self.tmp.name, "r.png"), "--degrees", "90"]))
        self.assertEqual(payload["actual"], {"width": 200, "height": 300})


if __name__ == "__main__":
    unittest.main()
