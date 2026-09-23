"""GPS detection reads the raw EXIF block itself. ImageMagick 6 attaches a HEIC file's
EXIF as a bare TIFF block and never parses it into exif:* properties, so the old
%[EXIF:GPSLatitude] check reported "no GPS" for an iPhone-style HEIC that had it."""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import probe  # noqa: E402
import strip  # noqa: E402
from _common import exif_blob_has_gps, image_has_gps, which_magick  # noqa: E402
from fixtures import build_exif_gps_app1, build_exif_orientation_app1, write_jpeg_with_gps, write_png  # noqa: E402

HEIF_ENC = shutil.which("heif-enc")


def app1_payload(app1):
    return app1[4:]  # drop the APP1 marker and length: "Exif\0\0" + TIFF


class ExifBlobTests(unittest.TestCase):
    def test_every_layout_imagemagick_emits(self):
        with_gps = app1_payload(build_exif_gps_app1())
        self.assertTrue(exif_blob_has_gps(with_gps))                          # JPEG / WebP: Exif\0\0 + TIFF
        self.assertTrue(exif_blob_has_gps(with_gps[6:]))                      # HEIC on IM6: bare TIFF
        self.assertTrue(exif_blob_has_gps(struct.pack(">I", 6) + with_gps))  # HEIF item: offset + Exif\0\0

    def test_exif_without_gps(self):
        self.assertFalse(exif_blob_has_gps(app1_payload(build_exif_orientation_app1(6))))
        self.assertFalse(exif_blob_has_gps(b""))

    def test_unparseable_is_unknown_not_false(self):
        self.assertIsNone(exif_blob_has_gps(b"garbage that is not exif"))
        self.assertIsNone(exif_blob_has_gps(b"Exif\x00\x00II*\x00\xff\xff\x00\x00"))


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class ImageGpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.png = os.path.join(self.tmp.name, "base.png")
        write_png(self.png, 64, 48, lambda x, y: (x * 3 % 256, y * 5 % 256, 90))
        self.jpg = os.path.join(self.tmp.name, "gps.jpg")
        write_jpeg_with_gps(which_magick(), self.png, self.jpg)

    def test_jpeg_and_png(self):
        self.assertTrue(image_has_gps(which_magick(), self.jpg))
        self.assertFalse(image_has_gps(which_magick(), self.png))

    @unittest.skipUnless(HEIF_ENC, "requires heif-enc (libheif-examples) to build a HEIC with EXIF")
    def test_heic_with_gps_is_detected_and_stripped(self):
        heic = os.path.join(self.tmp.name, "photo.heic")
        subprocess.run([HEIF_ENC, "-q", "50", self.jpg, "-o", heic], check=True, capture_output=True)
        payload = probe.run_probe(probe.build_parser().parse_args([heic, "--json"]))
        self.assertTrue(payload["has_gps"], payload)
        out = os.path.join(self.tmp.name, "clean.jpg")
        strip.run_strip(strip.build_parser().parse_args([heic, "-o", out]))
        self.assertFalse(image_has_gps(which_magick(), out))


if __name__ == "__main__":
    unittest.main()
