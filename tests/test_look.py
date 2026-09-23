import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import look  # noqa: E402
from _common import ImageSkillError, identify_dims, which_magick  # noqa: E402
from fixtures import write_solid_png  # noqa: E402


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class LookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.inputs = []
        for i, (w, h) in enumerate([(400, 200), (100, 300), (50, 50)]):
            path = os.path.join(self.tmp.name, f"in{i}.png")
            write_solid_png(path, w, h, (40 * i, 100, 200))
            self.inputs.append(path)

    def run_look(self, *extra):
        out = os.path.join(self.tmp.name, "sheet.png")
        args = look.build_parser().parse_args(self.inputs[: extra[0]] + ["-o", out] + list(extra[1:]))
        return look.run_look(args), out

    def test_grid_has_the_promised_size_and_leaves_inputs_alone(self):
        before = [os.path.getmtime(p) for p in self.inputs]
        payload, out = self.run_look(3, "--tile", "100", "--cols", "2")
        self.assertEqual((payload["cols"], payload["rows"]), (2, 2))
        label_h = look.LABEL_HEIGHT if payload["labels"] else 0
        self.assertEqual(identify_dims(out), (2 * 100 + 8, 2 * (100 + label_h) + 8))
        self.assertEqual([i["width"] for i in payload["inputs"]], [400, 100, 50])
        self.assertEqual(before, [os.path.getmtime(p) for p in self.inputs])

    def test_pair_needs_exactly_two(self):
        with self.assertRaises(ImageSkillError):
            self.run_look(3, "--pair")
        payload, _ = self.run_look(2, "--pair", "--tile", "64")
        self.assertEqual(payload["mode"], "pair")
        self.assertEqual(payload["cols"], 2)

    def test_refuses_to_write_over_an_input(self):
        args = look.build_parser().parse_args(self.inputs + ["-o", self.inputs[0], "--overwrite"])
        with self.assertRaises(ImageSkillError):
            look.run_look(args)


if __name__ == "__main__":
    unittest.main()
