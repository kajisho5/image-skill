import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import _contract  # noqa: E402


class TestDoctorNoBackend(unittest.TestCase):
    def test_doctor_reports_not_ok_when_no_backend_found(self):
        with mock.patch.object(_contract, "which_magick", return_value=None), mock.patch.object(
            _contract, "which_sips", return_value=None
        ):
            payload = _contract.build_doctor_payload()

        self.assertFalse(payload["ok"])
        self.assertIn("reason", payload)
        for tool in ("probe", "convert", "resize", "thumb", "strip", "trim", "check", "batch"):
            self.assertFalse(payload["tools"][tool]["usable"], f"{tool} should be unusable with no backend")
        self.assertFalse(payload["heic"]["usable"])
        self.assertFalse(payload["webp"]["usable"])

    def test_doctor_sips_only_marks_strip_and_trim_unusable(self):
        with mock.patch.object(_contract, "which_magick", return_value=None), mock.patch.object(
            _contract, "which_sips", return_value="/usr/bin/sips"
        ), mock.patch.object(_contract.sys, "platform", "darwin"):
            payload = _contract.build_doctor_payload()

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["tools"]["convert"]["usable"])
        self.assertEqual(payload["tools"]["convert"]["backend"], "sips")
        self.assertFalse(payload["tools"]["strip"]["usable"])
        self.assertFalse(payload["tools"]["trim"]["usable"])
        self.assertFalse(payload["webp"]["usable"])


class TestContract(unittest.TestCase):
    def test_contract_lists_all_eight_tools(self):
        payload = _contract.build_contract_payload()
        names = {t["name"] for t in payload["tools"]}
        self.assertEqual(
            names,
            {"probe", "convert", "resize", "thumb", "strip", "trim", "check", "batch"},
        )
        self.assertTrue(payload["ok"])
        self.assertIn("rules", payload)


if __name__ == "__main__":
    unittest.main()
