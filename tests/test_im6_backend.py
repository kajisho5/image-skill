"""ImageMagick 6 without a `magick` command (Debian/Ubuntu's apt package) is used through
its own convert/identify. The mapping is pure argv; the detection is mocked here and
exercised for real by CI's ubuntu-with-imagemagick job, which has no `magick` shim."""
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import _common  # noqa: E402

CONVERT = "/usr/bin/convert"
IDENTIFY = "/usr/bin/identify"


def fake_which(table):
    return lambda name: table.get(name)


def version_out(first_line):
    return mock.Mock(stdout=first_line + "\nCopyright: ...\n")


class DetectionTests(unittest.TestCase):
    def setUp(self):
        _common._IM6_CONVERT_CHECKED.clear()
        self.addCleanup(_common._IM6_CONVERT_CHECKED.clear)

    def detect(self, which, version_line, os_name="posix"):
        with mock.patch.object(_common.shutil, "which", side_effect=fake_which(which)), \
                mock.patch.object(_common.subprocess, "run", return_value=version_out(version_line)) as run, \
                mock.patch.object(_common.os, "name", os_name):
            return _common.which_magick(), _common.magick_kind(), run

    def test_magick_wins_and_convert_is_not_even_asked(self):
        found, kind, run = self.detect({"magick": "/usr/local/bin/magick", "convert": CONVERT},
                                       "Version: ImageMagick 6.9.12-98 Q16")
        self.assertEqual((found, kind), ("/usr/local/bin/magick", "magick"))
        run.assert_not_called()

    def test_imagemagick6_convert_is_used_when_there_is_no_magick(self):
        found, kind, _ = self.detect({"convert": CONVERT}, "Version: ImageMagick 6.9.12-98 Q16 x86_64")
        self.assertEqual((found, kind), (CONVERT, "imagemagick6"))

    def test_a_convert_that_is_not_imagemagick6_is_ignored(self):
        found, kind, _ = self.detect({"convert": CONVERT}, "convert: some other program 1.0")
        self.assertEqual((found, kind), (None, None))

    def test_windows_convert_exe_is_never_used(self):
        found, kind, run = self.detect({"convert": r"C:\Windows\System32\convert.exe"},
                                       "Version: ImageMagick 6.9.12-98 Q16", os_name="nt")
        self.assertEqual((found, kind), (None, None))
        run.assert_not_called()


class ArgvMappingTests(unittest.TestCase):
    def mapped(self, cmd):
        table = {"convert": CONVERT, "identify": IDENTIFY, "compare": "/usr/bin/compare"}
        with mock.patch.object(_common.shutil, "which", side_effect=fake_which(table)), \
                mock.patch.object(_common, "_im6_convert", return_value=CONVERT):
            return _common.magick_argv(cmd)

    def test_subcommands_go_to_imagemagick6s_own_tools(self):
        self.assertEqual(self.mapped([CONVERT, "identify", "-format", "%w", "a.png"]),
                         [IDENTIFY, "-format", "%w", "a.png"])
        self.assertEqual(self.mapped([CONVERT, "compare", "a.png", "b.png", "d.png"]),
                         ["/usr/bin/compare", "a.png", "b.png", "d.png"])
        self.assertEqual(self.mapped([CONVERT, "convert", "a.png", "b.jpg"]), [CONVERT, "a.png", "b.jpg"])

    def test_convert_syntax_and_other_backends_are_unchanged(self):
        self.assertEqual(self.mapped([CONVERT, "a.png[0]", "-resize", "10x10", "b.png"]),
                         [CONVERT, "a.png[0]", "-resize", "10x10", "b.png"])
        self.assertEqual(self.mapped(["/usr/bin/sips", "-s", "format", "jpeg"]), ["/usr/bin/sips", "-s", "format", "jpeg"])
        self.assertEqual(self.mapped([]), [])

    def test_a_list_of_commands_is_mapped_item_by_item_and_mapping_is_idempotent(self):
        once = self.mapped([[CONVERT, "identify", "x.png"], [CONVERT, "x.png", "y.png"]])
        self.assertEqual(once, [[IDENTIFY, "x.png"], [CONVERT, "x.png", "y.png"]])
        self.assertEqual(self.mapped(once), once)

    def test_with_a_real_magick_nothing_changes(self):
        with mock.patch.object(_common.shutil, "which", side_effect=fake_which({"magick": "/opt/magick", "convert": CONVERT})):
            self.assertEqual(_common.magick_argv([CONVERT, "identify", "a.png"]), [CONVERT, "identify", "a.png"])
            self.assertEqual(_common.magick_argv(["/opt/magick", "identify", "a.png"]), ["/opt/magick", "identify", "a.png"])


@unittest.skipUnless(_common.magick_kind() == "imagemagick6", "needs ImageMagick 6 with no magick command")
class RealImageMagick6Tests(unittest.TestCase):
    def test_run_reaches_identify_and_doctor_names_the_kind(self):
        import tempfile

        from fixtures import write_solid_png
        with tempfile.TemporaryDirectory() as tmp:
            png = os.path.join(tmp, "a.png")
            write_solid_png(png, 7, 5)
            self.assertEqual(_common.identify_dims(png), (7, 5))
        out = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "..", "scripts", "_contract.py"),
                              "doctor", "--json"], capture_output=True, text=True)
        import json
        self.assertEqual(json.loads(out.stdout)["backends"]["magick"]["kind"], "imagemagick6")


if __name__ == "__main__":
    unittest.main()
