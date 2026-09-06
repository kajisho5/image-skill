import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import trim  # noqa: E402
from _common import ImageSkillError, which_magick  # noqa: E402
from fixtures import write_bordered_png, write_solid_png  # noqa: E402


@unittest.skipUnless(which_magick(), "trim requires ImageMagick")
class TestTrim(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_trims_solid_border(self):
        src = os.path.join(self.tmp.name, "bordered.png")
        write_bordered_png(src, 100, 100, border=20)
        dest = os.path.join(self.tmp.name, "trimmed.png")

        args = trim.build_parser().parse_args([src, "-o", dest, "--json"])
        payload = trim.run_trim(args)

        self.assertLess(payload["trimmed"]["width"], payload["original"]["width"])
        self.assertLess(payload["trimmed"]["height"], payload["original"]["height"])
        self.assertAlmostEqual(payload["trimmed"]["width"], 60, delta=2)
        self.assertAlmostEqual(payload["trimmed"]["height"], 60, delta=2)

    def test_refuses_over_trim_on_solid_image(self):
        src = os.path.join(self.tmp.name, "solid.png")
        write_solid_png(src, 50, 50)
        dest = os.path.join(self.tmp.name, "trimmed2.png")

        args = trim.build_parser().parse_args(
            [src, "-o", dest, "--max-trim-percent", "90", "--json"]
        )
        with self.assertRaises(ImageSkillError) as ctx:
            trim.run_trim(args)
        self.assertIn("removed", str(ctx.exception))
        self.assertFalse(os.path.exists(dest))


if __name__ == "__main__":
    unittest.main()
