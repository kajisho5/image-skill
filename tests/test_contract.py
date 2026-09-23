"""The contract is derived from the scripts, and every surface that restates it
(docs/contract.md, package/plugin versions, each tool's real --json output) is checked
against it here, so drift fails CI instead of shipping."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, ".github", "scripts"))

import _contract  # noqa: E402
import contract_md  # noqa: E402
from _common import which_magick  # noqa: E402
from fixtures import write_bordered_png, write_solid_png  # noqa: E402


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class ContractShapeTests(unittest.TestCase):
    def setUp(self):
        self.payload = _contract.build_contract_payload()
        self.tools = {t["name"]: t for t in self.payload["tools"]}

    def test_every_public_script_has_a_contract_entry_and_vice_versa(self):
        public = sorted(f[:-3] for f in os.listdir(SCRIPTS) if f.endswith(".py") and not f.startswith("_"))
        self.assertEqual(public, sorted(self.tools))

    def test_input_schema_is_the_scripts_own_parser(self):
        for name, tool in self.tools.items():
            parser = _contract._load_tool_module(name).build_parser()
            dests = [a.dest for a in parser._actions if a.dest != "help"]
            extra = list(_contract.TOOL_META[name].get("extra_properties", {}))
            self.assertEqual(list(tool["input_schema"]["properties"]), dests + extra, name)

    def test_writing_tools_take_output_overwrite_and_dry_run(self):
        for name, tool in self.tools.items():
            props = tool["input_schema"]["properties"]
            self.assertTrue(tool["supports_json"], name)
            self.assertFalse(tool["mutates_input"], name)
            if tool["writes_output"] and name != "batch" and not tool["output_optional"]:
                self.assertTrue({"output", "output_dir"} & set(tool["input_schema"]["required"]), name)
                self.assertIn("overwrite", props, name)
            if tool["writes_output"]:
                self.assertTrue(tool["supports_dry_run"], name)

    def test_top_level_identity(self):
        with open(os.path.join(ROOT, "package.json")) as f:
            pkg = json.load(f)
        self.assertEqual(self.payload["name"], pkg["name"])
        self.assertEqual(self.payload["skill"]["id"], pkg["name"])
        self.assertEqual(self.payload["version"], pkg["version"])
        self.assertEqual(self.payload["skill"]["version"], pkg["version"])
        self.assertEqual(self.payload["execution"]["shell"], False)

    def test_contract_cli_prints_the_same_payload(self):
        out = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "_contract.py"), "contract", "--json"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(json.loads(out), json.loads(json.dumps(self.payload)))


class DocsAgreeWithContractTests(unittest.TestCase):
    def test_contract_md_tools_section_is_generated_from_the_contract(self):
        self.assertEqual(contract_md.current_block(_read("docs", "contract.md")), contract_md.expected_block())

    def test_versions_agree_everywhere(self):
        version = json.loads(_read("package.json"))["version"]
        self.assertEqual(json.loads(_read(".claude-plugin", "plugin.json"))["version"], version)
        contract = _read("docs", "contract.md")
        self.assertIn(f"the npm / package.json version (`{version}`)", contract)
        self.assertIn(f'"skill": {{"id": "imagemagick-skill", "version": "{version}"', contract)
        self.assertEqual(len(re.findall(r"The released version today is \*\*" + re.escape(version) + r"\*\*",
                                        _read("docs", "roadmap.md"))), 1)

    def test_plugin_and_marketplace_name_the_package(self):
        name = json.loads(_read("package.json"))["name"]
        self.assertEqual(json.loads(_read(".claude-plugin", "plugin.json"))["name"], name)
        market = json.loads(_read(".claude-plugin", "marketplace.json"))
        self.assertEqual([p["name"] for p in market["plugins"]], [name])
        self.assertEqual(market["plugins"][0]["source"], "./")

    def test_design_decisions_cite_tests_that_exist(self):
        names = set(re.findall(r"`(test_[a-z0-9_]+)`", _read("docs", "design-decisions.md")))
        self.assertTrue(names)
        tests_dir = os.path.join(ROOT, "tests")
        defined = set()
        for f in os.listdir(tests_dir):
            if f.endswith(".py"):
                defined.update(re.findall(r"def (test_[a-z0-9_]+)\(", _read("tests", f)))
        self.assertEqual(sorted(names - defined), [])

    def test_skill_md_stays_under_the_30kb_budget(self):
        # SKILL.md is loaded into every agent session (ffmpeg-skill keeps the same budget).
        self.assertLess(len(_read("SKILL.md").encode("utf-8")), 30_000)

    def test_skill_md_names_every_tool(self):
        skill = _read("SKILL.md")
        for name in _contract.TOOL_META:
            self.assertIn(f"`{name}.py`", skill)

    def test_skill_md_frontmatter_name_matches_package(self):
        name = json.loads(_read("package.json"))["name"]
        self.assertIn(f"\nname: {name}\n", _read("SKILL.md"))


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class OutputSchemaConformanceTests(unittest.TestCase):
    """Run every tool for real and hold its --json output to its declared output_schema."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "in.png")
        write_bordered_png(self.src, 60, 40, 5)
        self.dir_in = os.path.join(self.tmp.name, "folder")
        os.makedirs(self.dir_in)
        write_solid_png(os.path.join(self.dir_in, "a.png"), 30, 20)
        self.square = os.path.join(self.tmp.name, "square.png")
        write_solid_png(self.square, 600, 600)

    def invocations(self):
        o = lambda n: os.path.join(self.tmp.name, n)  # noqa: E731
        return {
            "probe": [self.src],
            "convert": [self.src, "-o", o("c.jpg")],
            "resize": [self.src, "-o", o("r.png"), "--width", "30", "--height", "30"],
            "thumb": [self.src, "-o", o("t.png"), "--long-edge", "20"],
            "strip": [self.src, "-o", o("s.png")],
            "trim": [self.src, "-o", o("tr.png")],
            "check": [self.src, "--expect-width", "60"],
            "look": [self.src, os.path.join(self.dir_in, "a.png"), "-o", o("look.png")],
            "compare": [self.src, self.src, "-o", o("heat.png")],
            "optimize": [self.src, "-o", o("opt.jpg"), "--max-kb", "50"],
            "crop": [self.src, "-o", o("crop.png"), "--aspect", "1:1"],
            "pad": [self.src, "-o", o("pad.png"), "--aspect", "1:1", "--color", "white"],
            "rotate": [self.src, "-o", o("rot.png"), "--degrees", "90"],
            "adjust": [self.src, "-o", o("adj.png"), "--contrast", "10"],
            "overlay": [self.src, "-o", o("ov.png"), "--image", os.path.join(self.dir_in, "a.png"), "--position", "center"],
            "montage": [self.src, os.path.join(self.dir_in, "a.png"), "-o", o("mont.png"), "--background", "white"],
            "icons": [self.square, "-o", o("icons")],
            "preset": [self.src, "-o", o("preset.png"), "--preset", "pwa-icon-192", "--mode", "fit"],
            "batch": ["thumb", "-i", self.dir_in, "-o", o("batch-out"), "--", "--long-edge", "10"],
        }

    def run_tool(self, name, args):
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, f"{name}.py"), *args, "--json"]
            if name != "batch" else
            [sys.executable, os.path.join(SCRIPTS, "batch.py"), *args[:5], "--json", *args[5:]],
            capture_output=True, text=True, timeout=120,
        )
        return proc, json.loads(proc.stdout)

    def test_success_output_matches_output_schema(self):
        invocations = self.invocations()
        self.assertEqual(sorted(invocations), sorted(_contract.TOOL_META))
        for tool in _contract.build_contract_payload()["tools"]:
            with self.subTest(tool=tool["name"]):
                proc, out = self.run_tool(tool["name"], invocations[tool["name"]])
                self.assertEqual(proc.returncode, 0, out)
                allowed = {"ok"} | set(tool["output_schema"]["properties"])
                self.assertLessEqual(set(out), allowed)
                self.assertLessEqual(set(tool["output_schema"]["required"]), set(out))

    def test_failure_and_dry_run_shapes(self):
        shapes = _contract.build_contract_payload()["result_shapes"]
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "resize.py"), "--json"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(set(json.loads(proc.stdout)), set(shapes["failure"]))
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "convert.py"), self.src, "-o",
             os.path.join(self.tmp.name, "dry.webp"), "--dry-run", "--json"],
            capture_output=True, text=True,
        )
        self.assertEqual(set(json.loads(proc.stdout)), set(shapes["dry_run"]))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "dry.webp")))


if __name__ == "__main__":
    unittest.main()
