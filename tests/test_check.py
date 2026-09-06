import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import check  # noqa: E402
from _common import ImageSkillError, which_magick, which_sips  # noqa: E402
from fixtures import write_solid_png  # noqa: E402

HAS_BACKEND = bool(which_magick() or which_sips())


class TestCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_flags_output_same_as_input(self):
        same = os.path.join(self.tmp.name, "same.png")
        write_solid_png(same, 10, 10)
        args = check.build_parser().parse_args([same, "--input", same, "--json"])
        with self.assertRaises(ImageSkillError) as ctx:
            check.run_check(args)
        self.assertIn("overwritten", str(ctx.exception))

    def test_flags_missing_output(self):
        missing = os.path.join(self.tmp.name, "nope.png")
        args = check.build_parser().parse_args([missing, "--json"])
        with self.assertRaises(ImageSkillError) as ctx:
            check.run_check(args)
        self.assertIn("not found", str(ctx.exception))

    def test_flags_empty_file_as_broken(self):
        empty = os.path.join(self.tmp.name, "empty.png")
        open(empty, "wb").close()
        args = check.build_parser().parse_args([empty, "--json"])
        with self.assertRaises(ImageSkillError) as ctx:
            check.run_check(args)
        self.assertIn("0 bytes", str(ctx.exception))

    @unittest.skipUnless(HAS_BACKEND, "requires ImageMagick or sips")
    def test_passes_for_matching_dimensions(self):
        good = os.path.join(self.tmp.name, "good.png")
        write_solid_png(good, 30, 15)
        args = check.build_parser().parse_args(
            [good, "--expect-width", "30", "--expect-height", "15", "--json"]
        )
        payload = check.run_check(args)
        self.assertEqual(payload["width"], 30)
        self.assertEqual(payload["height"], 15)

    @unittest.skipUnless(HAS_BACKEND, "requires ImageMagick or sips")
    def test_fails_for_wrong_width(self):
        good = os.path.join(self.tmp.name, "good2.png")
        write_solid_png(good, 30, 15)
        args = check.build_parser().parse_args([good, "--expect-width", "999", "--json"])
        with self.assertRaises(ImageSkillError):
            check.run_check(args)


if __name__ == "__main__":
    unittest.main()
