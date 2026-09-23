"""Behaviours that look like bugs but are decisions (docs/design-decisions.md). Each
test here is the pin that entry names."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import _contract  # noqa: E402
import convert  # noqa: E402
import thumb  # noqa: E402
from _common import identify_dims, which_magick  # noqa: E402
from fixtures import write_jpeg_with_orientation, write_solid_png  # noqa: E402


class ContractDecisionTests(unittest.TestCase):
    def test_check_has_no_dry_run_because_it_writes_nothing(self):
        tools = {t["name"]: t for t in _contract.build_contract_payload()["tools"]}
        self.assertFalse(tools["check"]["writes_output"])
        self.assertFalse(tools["check"]["supports_dry_run"])

    def test_sizes_are_never_defaulted(self):
        tools = {t["name"]: t for t in _contract.build_contract_payload()["tools"]}
        for name, dests in (("resize", ("width", "height")), ("thumb", ("long_edge",))):
            schema = tools[name]["input_schema"]
            for dest in dests:
                self.assertIn(dest, schema["required"], f"{name} {dest}")
                self.assertNotIn("default", schema["properties"][dest], f"{name} {dest}")


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class MagickDecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_thumb_never_upscales(self):
        src = os.path.join(self.tmp.name, "small.png")
        write_solid_png(src, 50, 30)
        out = os.path.join(self.tmp.name, "thumb.png")
        payload = thumb.run_thumb(thumb.build_parser().parse_args([src, "-o", out, "--long-edge", "200"]))
        self.assertEqual(payload["actual"], {"width": 50, "height": 30})

    def test_exif_orientation_is_baked_into_the_pixels(self):
        png = os.path.join(self.tmp.name, "wide.png")
        write_solid_png(png, 60, 30)
        tagged = os.path.join(self.tmp.name, "tagged.jpg")
        write_jpeg_with_orientation(which_magick(), png, tagged, 6)  # 6 = rotate 90 CW to display
        out = os.path.join(self.tmp.name, "upright.png")
        convert.run_convert(convert.build_parser().parse_args([tagged, "-o", out]))
        self.assertEqual(identify_dims(out), (30, 60))


if __name__ == "__main__":
    unittest.main()
