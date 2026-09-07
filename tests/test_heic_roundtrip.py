import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import convert  # noqa: E402
import probe  # noqa: E402
import _contract  # noqa: E402
from fixtures import write_solid_png  # noqa: E402

# No HEIC binary is committed to this repo (licensing and repo-bloat concerns
# aside, a real backend's own encoder is the only reliable way to produce valid
# HEIC bytes anyway - see verify_output_format's whole reason for existing).
# Instead this generates a tiny one on the fly with whatever real backend on
# this machine can actually write HEIC, and skips everywhere else.
_HEIC_WRITE_CAPABLE = _contract.build_doctor_payload().get("heic", {}).get("write", False)


@unittest.skipUnless(_HEIC_WRITE_CAPABLE, "no backend on this machine can write HEIC (see doctor's heic.write)")
class TestHeicRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_write_then_read_back_real_heic(self):
        src = os.path.join(self.tmp.name, "src.png")
        write_solid_png(src, 32, 24)

        heic_path = os.path.join(self.tmp.name, "out.heic")
        convert.run_convert(convert.build_parser().parse_args([src, "-o", heic_path, "--json"]))

        with open(heic_path, "rb") as f:
            head = f.read(12)
        self.assertEqual(head[4:8], b"ftyp", "output should be a real ISOBMFF/HEIC container, not a mislabeled file")

        probed = probe.run_probe(probe.build_parser().parse_args([heic_path, "--json"]))
        self.assertEqual(probed["width"], 32)
        self.assertEqual(probed["height"], 24)
        # Case varies by backend - magick reports "HEIC", sips reports "heic" -
        # and the project's own convention (check.py's --expect-format) already
        # treats format names as case-insensitive, so this does too.
        self.assertEqual(probed["format"].upper(), "HEIC")


if __name__ == "__main__":
    unittest.main()
