import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class AgentPromptsTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "evals", "agent_prompts.json"), encoding="utf-8") as f:
            self.prompts = json.load(f)

    def test_at_least_twenty_unique_prompts(self):
        ids = [p["id"] for p in self.prompts]
        self.assertGreaterEqual(len(ids), 20)
        self.assertEqual(len(ids), len(set(ids)))

    def test_expected_scripts_exist(self):
        scripts = set(os.listdir(os.path.join(ROOT, "scripts")))
        for p in self.prompts:
            for step in p["expect"]:
                for alt in step.split("|"):
                    self.assertIn(alt, scripts, f"{p['id']}: {alt}")

    def test_declines_and_questions_expect_no_tool_run(self):
        for p in self.prompts:
            if p.get("decline") or p.get("ask"):
                self.assertEqual(p["expect"], [], p["id"])
            else:
                self.assertTrue(p["expect"], p["id"])

    def test_paths_are_placeholders_only(self):
        for p in self.prompts:
            self.assertNotRegex(p["prompt"], r"(^|\s)/(home|tmp|Users)/", p["id"])
            for path in re.findall(r"\b[A-Z]+/", p["prompt"]):
                self.assertIn(path, ("FIXTURES/", "OUTDIR/"), p["id"])


@unittest.skipUnless(shutil.which("magick"), "requires ImageMagick")
class WriteFixturesTests(unittest.TestCase):
    def test_every_fixture_a_prompt_names_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, os.path.join(ROOT, "evals", "write_fixtures.py"), tmp],
                           check=True, capture_output=True)
            with open(os.path.join(ROOT, "evals", "agent_prompts.json"), encoding="utf-8") as f:
                prompts = json.load(f)
            for p in prompts:
                if p.get("decline"):
                    continue
                for rel in re.findall(r"FIXTURES/([\w./-]+?)(?=[\s,.]*(?:\s|$|を|の|に))", p["prompt"]):
                    self.assertTrue(os.path.exists(os.path.join(tmp, rel)), f"{p['id']}: {rel}")


if __name__ == "__main__":
    unittest.main()
