import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import probe  # noqa: E402
import strip  # noqa: E402
from _common import which_magick  # noqa: E402
from fixtures import write_solid_png, write_jpeg_with_gps  # noqa: E402

MAGICK = which_magick()


@unittest.skipUnless(MAGICK, "GPS EXIF fixtures and strip.py require ImageMagick")
class TestStrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        base_png = os.path.join(self.tmp.name, "base.png")
        write_solid_png(base_png, 20, 20)

        self.gps_jpg = os.path.join(self.tmp.name, "with_gps.jpg")
        write_jpeg_with_gps(MAGICK, base_png, self.gps_jpg)

    def test_input_has_gps_before_strip(self):
        args = probe.build_parser().parse_args([self.gps_jpg, "--json"])
        payload = probe.run_probe(args)
        self.assertTrue(payload["has_gps"])

    def test_strip_removes_gps(self):
        dest = os.path.join(self.tmp.name, "clean.jpg")
        args = strip.build_parser().parse_args([self.gps_jpg, "-o", dest, "--json"])
        payload = strip.run_strip(args)
        self.assertFalse(payload["has_gps"])

        probed = probe.run_probe(probe.build_parser().parse_args([dest, "--json"]))
        self.assertFalse(probed["has_gps"])

    def test_strip_does_not_touch_input(self):
        dest = os.path.join(self.tmp.name, "clean2.jpg")
        strip.run_strip(strip.build_parser().parse_args([self.gps_jpg, "-o", dest, "--json"]))

        still_has_gps = probe.run_probe(probe.build_parser().parse_args([self.gps_jpg, "--json"]))
        self.assertTrue(still_has_gps["has_gps"])


if __name__ == "__main__":
    unittest.main()
