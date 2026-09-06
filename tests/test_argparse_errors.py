import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import resize  # noqa: E402
import _contract  # noqa: E402


class TestArgparseErrorsFollowJSONContract(unittest.TestCase):
    """A malformed invocation (missing/invalid flags) must fail the same way
    every other error does: ok:false with a human-readable reason when --json
    is requested, plain text otherwise - never argparse's raw usage dump."""

    def test_missing_required_flags_with_json_emits_ok_false_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                resize.main(["in.png", "-o", "out.png", "--json"])
        self.assertEqual(ctx.exception.code, 1)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["ok"])
        self.assertIn("--width", payload["reason"])
        self.assertIn("--height", payload["reason"])

    def test_missing_required_flags_without_json_emits_plain_text_to_stderr(self):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            with self.assertRaises(SystemExit):
                resize.main(["in.png", "-o", "out.png"])
        self.assertEqual(out.getvalue(), "")
        self.assertIn("--width", err.getvalue())

    def test_contract_cli_invalid_subcommand_emits_ok_false_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                _contract.main(["bogus", "--json"])
        self.assertEqual(ctx.exception.code, 1)
        payload = json.loads(out.getvalue())
        self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
