import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import compare  # noqa: E402
from _common import ImageSkillError, which_magick  # noqa: E402
from fixtures import write_png  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "compare.py")


class SsimMathTests(unittest.TestCase):
    """The pure-Python SSIM on known inputs (cross-checked against scikit-image 0.26's
    structural_similarity(win_size=7, data_range=255) to 1e-12 while developing)."""

    def test_identical_is_one(self):
        x = [float((i * 37) % 256) for i in range(20 * 15)]
        self.assertAlmostEqual(compare.ssim(x, list(x), 20, 15), 1.0, places=12)

    def test_constant_offset_lowers_luminance_term_only_slightly(self):
        x = [float((i * 37) % 200) for i in range(20 * 15)]
        y = [v + 10 for v in x]
        self.assertTrue(0.9 < compare.ssim(x, y, 20, 15) < 1.0)

    def test_inverted_image_scores_low(self):
        x = [float((i * 37) % 256) for i in range(20 * 15)]
        y = [255 - v for v in x]
        self.assertLess(compare.ssim(x, y, 20, 15), 0.0)

    def test_too_small_is_an_error(self):
        with self.assertRaises(ImageSkillError):
            compare.ssim([0.0] * 36, [0.0] * 36, 6, 6)


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a = os.path.join(self.tmp.name, "a.png")
        self.b = os.path.join(self.tmp.name, "b.png")
        base = lambda x, y: ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256)  # noqa: E731
        write_png(self.a, 120, 90, base)
        # exactly 100 changed pixels: a 10x10 block
        write_png(self.b, 120, 90, lambda x, y: (255, 255, 255) if 20 <= x < 30 and 40 <= y < 50 else base(x, y))

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT, *args, "--json"], capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def test_identical_images(self):
        code, out = self.run_cli(self.a, self.a)
        self.assertEqual(code, 0)
        self.assertTrue(out["identical"])
        self.assertEqual((out["ssim"], out["psnr_db"], out["diff_pixels"]), (1.0, None, 0))

    def test_counts_changed_pixels_exactly(self):
        code, out = self.run_cli(self.a, self.b)
        self.assertEqual(code, 0)
        self.assertEqual(out["diff_pixels"], 100)
        self.assertAlmostEqual(out["diff_ratio"], 100 / (120 * 90), places=6)
        self.assertLess(out["ssim"], 1.0)
        self.assertGreater(out["psnr_db"], 10)

    def test_fail_below_reports_metrics_and_exit_1(self):
        code, out = self.run_cli(self.a, self.b, "--fail-below", "0.9999")
        self.assertEqual(code, 1)
        self.assertFalse(out["ok"])
        self.assertIn("ssim", out)
        self.assertFalse(out["passed"])

    def test_heatmap_is_written_with_the_same_size(self):
        heat = os.path.join(self.tmp.name, "heat.png")
        code, out = self.run_cli(self.a, self.b, "-o", heat)
        self.assertEqual(code, 0)
        self.assertEqual(out["output"], heat)
        from _common import identify_dims
        self.assertEqual(identify_dims(heat), (120, 90))

    def test_size_mismatch_is_refused(self):
        small = os.path.join(self.tmp.name, "small.png")
        write_png(small, 60, 45, lambda x, y: (0, 0, 0))
        code, out = self.run_cli(self.a, small)
        self.assertEqual(code, 1)
        self.assertIn("differ in size", out["reason"])


if __name__ == "__main__":
    unittest.main()
