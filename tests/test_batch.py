import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import batch  # noqa: E402
from _common import ImageSkillError, which_magick, which_sips  # noqa: E402
from fixtures import write_solid_png  # noqa: E402

HAS_BACKEND = bool(which_magick() or which_sips())


class TestBatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.in_dir = os.path.join(self.tmp.name, "in")
        self.out_dir = os.path.join(self.tmp.name, "out")
        os.makedirs(self.in_dir)

    def test_rejects_same_input_and_output_dir(self):
        args = batch.parse_args(
            ["thumb", "-i", self.in_dir, "-o", self.in_dir, "--json", "--", "--long-edge", "10"]
        )
        with self.assertRaises(ImageSkillError):
            batch.run_batch(args)

    def test_convert_requires_ext(self):
        args = batch.parse_args(["convert", "-i", self.in_dir, "-o", self.out_dir, "--json"])
        with self.assertRaises(ImageSkillError) as ctx:
            batch.run_batch(args)
        self.assertIn("--ext", str(ctx.exception))

    def test_per_file_argparse_error_is_recorded_not_fatal(self):
        """A bad per-file invocation (e.g. forgetting `-- --width/--height`) must
        show up as one failed entry in `results`, not crash the whole batch -
        JSONArgumentParser.error() raises ImageSkillError instead of calling
        sys.exit(), so run_batch's existing per-file try/except catches it."""
        write_solid_png(os.path.join(self.in_dir, "a.png"), 10, 10)

        args = batch.parse_args(["resize", "-i", self.in_dir, "-o", self.out_dir, "--json"])
        payload = batch.run_batch(args)

        self.assertEqual(payload["count"], 1)
        self.assertFalse(payload["all_ok"])
        self.assertFalse(payload["results"][0]["ok"])
        self.assertIn("--width", payload["results"][0]["reason"])

    @unittest.skipUnless(HAS_BACKEND, "requires ImageMagick or sips")
    def test_processes_every_image_without_overwriting_inputs(self):
        write_solid_png(os.path.join(self.in_dir, "a.png"), 40, 40)
        write_solid_png(os.path.join(self.in_dir, "b.png"), 40, 40)

        args = batch.parse_args(
            ["thumb", "-i", self.in_dir, "-o", self.out_dir, "--json", "--", "--long-edge", "20"]
        )
        payload = batch.run_batch(args)

        self.assertEqual(payload["count"], 2)
        self.assertTrue(payload["all_ok"])
        for name in ("a.png", "b.png"):
            self.assertTrue(os.path.isfile(os.path.join(self.in_dir, name)))
            self.assertTrue(os.path.isfile(os.path.join(self.out_dir, name)))


if __name__ == "__main__":
    unittest.main()
