import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from _common import identify_dims, which_magick  # noqa: E402
from fixtures import write_png  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "optimize.py")


def busy(x, y):
    # deterministic high-frequency content so quality really changes the size
    v = (x * 131 + y * 71 + (x * y) % 97) % 256
    return (v, (v * 3) % 256, (255 - v))


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class OptimizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "busy.png")
        write_png(self.src, 320, 240, busy)

    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT, self.src, *args, "--json"], capture_output=True, text=True)
        return proc.returncode, json.loads(proc.stdout)

    def test_fits_the_budget_and_keeps_dimensions(self):
        out = os.path.join(self.tmp.name, "o.jpg")
        code, payload = self.run_cli("-o", out, "--max-kb", "40")
        self.assertEqual(code, 0, payload)
        self.assertLessEqual(os.path.getsize(out), 40_000)
        self.assertEqual(payload["bytes"], os.path.getsize(out))
        self.assertEqual(identify_dims(out), (320, 240))
        self.assertIn(payload["method"], ("quality-search",))
        self.assertTrue(40 <= payload["quality"] <= 95)

    def test_webp_fits_by_quality_or_target_size(self):
        out = os.path.join(self.tmp.name, "o.webp")
        code, payload = self.run_cli("-o", out, "--max-kb", "30")
        self.assertEqual(code, 0, payload)
        self.assertLessEqual(os.path.getsize(out), 30_000)
        self.assertIn(payload["method"], ("quality-search", "webp:target-size"))

    def test_unreachable_budget_fails_with_smallest_size_and_writes_nothing(self):
        out = os.path.join(self.tmp.name, "tiny.jpg")
        code, payload = self.run_cli("-o", out, "--max-kb", "1")
        self.assertEqual(code, 1)
        self.assertGreater(payload["smallest_bytes"], 1000)
        self.assertFalse(os.path.exists(out))
        self.assertEqual([f for f in os.listdir(self.tmp.name) if "optimize" in f], [])

    def test_png_is_one_lossless_attempt(self):
        out = os.path.join(self.tmp.name, "o.png")
        code, payload = self.run_cli("-o", out, "--max-kb", "10000")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["method"], "lossless")
        self.assertIsNone(payload["quality"])

    def test_refuses_unsupported_formats_and_bad_bounds(self):
        code, payload = self.run_cli("-o", os.path.join(self.tmp.name, "o.gif"), "--max-kb", "10")
        self.assertEqual(code, 1)
        code, payload = self.run_cli("-o", os.path.join(self.tmp.name, "o.jpg"), "--max-kb", "10",
                                     "--min-quality", "90", "--max-quality", "50")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
