import os
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
