import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import probe  # noqa: E402
from _common import ImageSkillError, which_magick, which_sips  # noqa: E402
from fixtures import write_solid_png  # noqa: E402

HAS_BACKEND = bool(which_magick() or which_sips())


class TestProbe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_missing_input_fails(self):
        args = probe.build_parser().parse_args([os.path.join(self.tmp.name, "nope.png"), "--json"])
        with self.assertRaises(ImageSkillError):
            probe.run_probe(args)

    @unittest.skipUnless(HAS_BACKEND, "requires ImageMagick or sips")
    def test_probe_reports_dimensions(self):
        path = os.path.join(self.tmp.name, "img.png")
        write_solid_png(path, 64, 32)
        args = probe.build_parser().parse_args([path, "--json"])
        payload = probe.run_probe(args)
        self.assertEqual(payload["width"], 64)
        self.assertEqual(payload["height"], 32)

    @unittest.skipUnless(HAS_BACKEND, "requires ImageMagick or sips")
    def test_dry_run_does_not_touch_filesystem(self):
        path = os.path.join(self.tmp.name, "img2.png")
        write_solid_png(path, 10, 10)
        args = probe.build_parser().parse_args([path, "--dry-run", "--json"])
        payload = probe.run_probe(args)
        self.assertTrue(payload["dry_run"])
        self.assertIn("would_run", payload)


if __name__ == "__main__":
    unittest.main()
