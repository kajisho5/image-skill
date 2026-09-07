import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import _common  # noqa: E402
import _contract  # noqa: E402


class TestVerifyOutputFormat(unittest.TestCase):
    """magick can exit 0 while silently writing the *input* format under a
    requested output name when it has no encode delegate for the target
    format (observed for real: converting to .heic on a read-only HEIC build
    wrote plain PNG bytes named .heic, with only a stderr warning). This must
    surface as ok:false, not a mislabeled "successful" file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_flags_a_silently_wrong_format(self):
        output = os.path.join(self.tmp.name, "photo.heic")
        with open(output, "wb") as f:
            f.write(b"not actually heic")

        with mock.patch.object(_common, "which_magick", return_value="/usr/bin/magick"), mock.patch.object(
            _common, "run", return_value={"dry_run": False, "stdout": "PNG\n", "stderr": ""}
        ):
            with self.assertRaises(_common.ImageSkillError) as ctx:
                _common.verify_output_format(output, "magick")

        self.assertIn("HEIC", str(ctx.exception))
        self.assertIn("PNG", str(ctx.exception))
        self.assertFalse(os.path.exists(output), "the mislabeled file should be removed, not left behind")

    def test_passes_when_format_matches(self):
        output = os.path.join(self.tmp.name, "photo.jpg")
        with open(output, "wb") as f:
            f.write(b"pretend jpeg bytes")

        with mock.patch.object(_common, "which_magick", return_value="/usr/bin/magick"), mock.patch.object(
            _common, "run", return_value={"dry_run": False, "stdout": "JPEG\n", "stderr": ""}
        ):
            _common.verify_output_format(output, "magick")  # must not raise

        self.assertTrue(os.path.exists(output))

    def test_skipped_for_sips_backend(self):
        output = os.path.join(self.tmp.name, "photo.heic")
        with open(output, "wb") as f:
            f.write(b"whatever")

        with mock.patch.object(_common, "run") as run_mock:
            _common.verify_output_format(output, "sips")

        run_mock.assert_not_called()

    def test_skipped_for_unknown_extension(self):
        output = os.path.join(self.tmp.name, "photo.xyz")
        with open(output, "wb") as f:
            f.write(b"whatever")

        with mock.patch.object(_common, "run") as run_mock:
            _common.verify_output_format(output, "magick")

        run_mock.assert_not_called()


class TestDoctorFormatCapabilities(unittest.TestCase):
    """doctor must distinguish read from write per format instead of treating any
    mention of the format name in `magick -list format` as full support."""

    def test_parses_read_only_and_read_write_modes(self):
        sample = (
            "   Format  Module    Mode  Description\n"
            "-------------------------------------------------------------------------------\n"
            "     HEIC            r--   Apple High efficiency Image Format (1.17.6)\n"
            "     WEBP* WEBP      rw+   WebP Image Format (libwebp 1.3.2)\n"
        )
        caps = _contract._format_capabilities(sample)
        self.assertEqual(caps["HEIC"], (True, False))
        self.assertEqual(caps["WEBP"], (True, True))

    def test_doctor_reports_heic_write_false_when_read_only(self):
        formats_out = "     HEIC            r--   Apple High efficiency Image Format (1.17.6)\n"
        with mock.patch.object(_contract, "which_magick", return_value="/usr/bin/magick"), mock.patch.object(
            _contract, "which_sips", return_value=None
        ), mock.patch.object(
            _contract,
            "_magick_lists",
            return_value=(formats_out, "", "Version: ImageMagick 6.9\n"),
        ):
            payload = _contract.build_doctor_payload()

        self.assertTrue(payload["heic"]["usable"])
        self.assertTrue(payload["heic"]["read"])
        self.assertFalse(payload["heic"]["write"])
        self.assertIsNotNone(payload["heic"]["fix"])


if __name__ == "__main__":
    unittest.main()
