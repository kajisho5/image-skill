import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import resize  # noqa: E402
from _common import which_magick, which_sips  # noqa: E402
from fixtures import write_solid_png  # noqa: E402

HAS_BACKEND = bool(which_magick() or which_sips())


@unittest.skipUnless(HAS_BACKEND, "requires ImageMagick or sips")
class TestResizeFit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "wide.png")
        write_solid_png(self.src, 400, 100)  # 4:1 aspect ratio

    def test_fit_does_not_distort(self):
        dest = os.path.join(self.tmp.name, "out.png")
        args = resize.build_parser().parse_args(
            [self.src, "-o", dest, "--width", "100", "--height", "100", "--mode", "fit", "--json"]
        )
        payload = resize.run_resize(args)

        actual = payload["actual"]
        self.assertLessEqual(actual["width"], 100)
        self.assertLessEqual(actual["height"], 100)

        original_ratio = 400 / 100
        result_ratio = actual["width"] / actual["height"]
        self.assertAlmostEqual(original_ratio, result_ratio, places=1)

    @unittest.skipUnless(which_magick(), "fill mode requires ImageMagick")
    def test_fill_produces_exact_box(self):
        dest = os.path.join(self.tmp.name, "out-fill.png")
        args = resize.build_parser().parse_args(
            [self.src, "-o", dest, "--width", "50", "--height", "50", "--mode", "fill", "--json"]
        )
        payload = resize.run_resize(args)
        self.assertEqual(payload["actual"], {"width": 50, "height": 50})


class TestSipsFitDims(unittest.TestCase):
    """Pure arithmetic checks for the sips fit box calculation - no sips binary
    needed, so these run on every platform including Linux CI."""

    def test_tall_image_into_wide_box_stays_within_both_dimensions(self):
        w, h = resize._sips_fit_dims(100, 800, 800, 200)
        self.assertLessEqual(w, 800)
        self.assertLessEqual(h, 200)

    def test_wide_image_into_wide_box_stays_within_both_dimensions(self):
        w, h = resize._sips_fit_dims(800, 100, 800, 200)
        self.assertLessEqual(w, 800)
        self.assertLessEqual(h, 200)

    def test_preserves_aspect_ratio(self):
        w, h = resize._sips_fit_dims(300, 900, 800, 200)  # 1:3 portrait
        self.assertAlmostEqual(w / h, 300 / 900, places=2)


@unittest.skipUnless(which_sips(), "requires macOS sips")
class TestSipsFitIntegration(unittest.TestCase):
    """Forces the sips code path (even on a Mac that also has magick) to prove
    resize.py's fit mode keeps both dimensions within the box for both a wide and
    a tall source image, matching magick's fit guarantee."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_fit_800x200_respects_box_for_wide_and_tall_sources(self):
        with mock.patch.object(resize, "which_magick", return_value=None):
            for name, (src_w, src_h) in (("wide", (1600, 200)), ("tall", (200, 1600))):
                src = os.path.join(self.tmp.name, f"{name}.png")
                write_solid_png(src, src_w, src_h)
                dest = os.path.join(self.tmp.name, f"{name}-out.png")

                args = resize.build_parser().parse_args(
                    [src, "-o", dest, "--width", "800", "--height", "200", "--mode", "fit", "--json"]
                )
                payload = resize.run_resize(args)

                self.assertEqual(payload["backend"], "sips")
                self.assertLessEqual(payload["actual"]["width"], 800)
                self.assertLessEqual(payload["actual"]["height"], 200)


if __name__ == "__main__":
    unittest.main()
