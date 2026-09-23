import argparse
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import _common  # noqa: E402
from _common import which_magick  # noqa: E402


class ArgumentTypeTests(unittest.TestCase):
    def test_color_arg_accepts_names_hex_and_functions(self):
        for ok in ("white", "none", "gray50", "#fff", "#ffffff80", "rgb(1,2,3)", "rgba(1, 2, 3, 0.5)", "hsl(120,50%,50%)"):
            self.assertEqual(_common.color_arg(ok), ok)

    def test_color_arg_refuses_anything_else(self):
        for bad in ("red; rm -rf", "@file.txt", "#12", "rgb(1,2)", "url(x)", ""):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad):
                _common.color_arg(bad)

    def test_transparency_detection(self):
        self.assertTrue(_common.color_is_transparent("none"))
        self.assertTrue(_common.color_is_transparent("#ffffff80"))
        self.assertTrue(_common.color_is_transparent("rgba(0,0,0,0.2)"))
        self.assertFalse(_common.color_is_transparent("#ffffffff"))
        self.assertFalse(_common.color_is_transparent("white"))

    def test_ratio_arg(self):
        self.assertEqual(_common.ratio_arg("16:9"), (16.0, 9.0))
        self.assertEqual(_common.ratio_arg("1.91:1"), (1.91, 1.0))
        for bad in ("16x9", "0:1", "a:b"):
            with self.assertRaises(argparse.ArgumentTypeError):
                _common.ratio_arg(bad)

    def test_gravity_offset(self):
        self.assertEqual(_common.gravity_offset("northwest", 100, 50, 20, 10), (0, 0))
        self.assertEqual(_common.gravity_offset("center", 100, 50, 20, 10), (40, 20))
        self.assertEqual(_common.gravity_offset("southeast", 100, 50, 20, 10), (80, 40))
        self.assertEqual(_common.gravity_offset("north", 100, 50, 20, 10), (40, 0))

    def test_cjk_detection(self):
        self.assertTrue(_common.needs_cjk_font("ロゴ"))
        self.assertTrue(_common.needs_cjk_font("© 2026 梶山"))
        self.assertFalse(_common.needs_cjk_font("© 2026 kajisho5"))


@unittest.skipUnless(which_magick() and _common.find_fonts()["default"], "requires ImageMagick and a font")
class EscapedTextRendersLiterallyTests(unittest.TestCase):
    """ImageMagick expands %-escapes and backslashes in label: text, and reads a file when
    the text starts with '@'. Escaped text must render exactly its own characters; widths
    are compared against the same characters rendered where they are not special."""

    def width(self, text):
        font = _common.find_fonts()["default"]
        out = subprocess.run(
            [which_magick(), "-background", "white", "-fill", "black", "-font", font, "-pointsize", "40",
             f"label:{text}", "-format", "%w", "info:"],
            capture_output=True, text=True, check=True,
        ).stdout
        return int(out)

    def test_leading_at_is_text_not_a_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("THIS FILE MUST NOT BE RENDERED " * 20)
        self.addCleanup(os.remove, f.name)
        literal = self.width(_common.escape_magick_text("@" + f.name))
        reference = self.width("a@" + _common.escape_magick_text(f.name)) - self.width("a")
        self.assertLess(abs(literal - reference), 4)

    def test_percent_and_backslash_are_literal(self):
        self.assertLess(abs(self.width(_common.escape_magick_text("100%")) - (self.width("100%%"))), 2)
        with_escape = self.width(_common.escape_magick_text("%w"))
        self.assertGreater(with_escape, self.width("w"))  # "%w" stays two glyphs, not the image width
        self.assertEqual(self.width(_common.escape_magick_text("a\\b")), self.width("a\\\\b"))


if __name__ == "__main__":
    unittest.main()
