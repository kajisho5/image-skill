import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import convert  # noqa: E402
import resize  # noqa: E402
from _common import ImageSkillError  # noqa: E402
from fixtures import write_solid_png  # noqa: E402


class TestOverwriteProtection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "in.png")
        write_solid_png(self.src, 20, 10)

    def test_convert_rejects_same_path(self):
        args = convert.build_parser().parse_args([self.src, "-o", self.src, "--json"])
        with self.assertRaises(ImageSkillError) as ctx:
            convert.run_convert(args)
        self.assertIn("output path must differ from input path", str(ctx.exception))

    def test_resize_rejects_same_path(self):
        args = resize.build_parser().parse_args(
            [self.src, "-o", self.src, "--width", "10", "--height", "5", "--json"]
        )
        with self.assertRaises(ImageSkillError) as ctx:
            resize.run_resize(args)
        self.assertIn("output path must differ from input path", str(ctx.exception))

    def test_convert_rejects_existing_output_without_overwrite_flag(self):
        dest = os.path.join(self.tmp.name, "out.png")
        write_solid_png(dest, 5, 5)
        args = convert.build_parser().parse_args([self.src, "-o", dest, "--json"])
        with self.assertRaises(ImageSkillError) as ctx:
            convert.run_convert(args)
        self.assertIn("refusing to overwrite", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
