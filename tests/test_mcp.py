"""mcp/server.py over real stdio, in both protocol eras, and the three surfaces that
must agree: contract --json, docs/contract.md and the MCP tools/list."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVER = os.path.join(ROOT, "mcp", "server.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import _contract  # noqa: E402
from _common import which_magick  # noqa: E402
from fixtures import write_solid_png  # noqa: E402

MODERN = {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}


def session(*requests):
    """Send JSON-RPC lines to a fresh server; return responses keyed by id."""
    payload = "".join(json.dumps(r) + "\n" for r in requests)
    proc = subprocess.run([sys.executable, SERVER], input=payload, capture_output=True, text=True, timeout=300)
    responses = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    return {r["id"]: r for r in responses}, responses


def req(id_, method, params=None):
    r = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        r["params"] = params
    return r


class LegacyHandshakeTests(unittest.TestCase):
    def test_initialize_then_list(self):
        by_id, responses = session(
            req(1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "t", "version": "0"}}),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            req(2, "tools/list"),
        )
        self.assertEqual(len(responses), 2, "a notification must not get a response")
        init = by_id[1]["result"]
        self.assertEqual(init["protocolVersion"], "2025-06-18")
        self.assertEqual(init["serverInfo"]["name"], "imagemagick-skill")
        self.assertIn("tools", init["capabilities"])
        self.assertNotIn("resultType", by_id[2]["result"])

    def test_unknown_legacy_version_gets_the_newest_legacy_one(self):
        by_id, _ = session(req(1, "initialize", {"protocolVersion": "2099-01-01"}))
        self.assertEqual(by_id[1]["result"]["protocolVersion"], "2025-11-25")


class ModernEraTests(unittest.TestCase):
    def test_discover_and_per_request_version(self):
        by_id, _ = session(req(1, "server/discover", MODERN), req(2, "tools/list", MODERN))
        discover = by_id[1]["result"]
        self.assertIn("2026-07-28", discover["supportedVersions"])
        self.assertIn("2025-11-25", discover["supportedVersions"])
        self.assertEqual(discover["resultType"], "complete")
        self.assertEqual(discover["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], "imagemagick-skill")
        self.assertEqual(by_id[2]["result"]["resultType"], "complete")

    def test_unsupported_version_error(self):
        by_id, _ = session(req(1, "tools/list", {"_meta": {"io.modelcontextprotocol/protocolVersion": "1900-01-01"}}))
        error = by_id[1]["error"]
        self.assertEqual(error["code"], -32022)
        self.assertEqual(error["data"]["requested"], "1900-01-01")
        self.assertIn("2026-07-28", error["data"]["supported"])


class ProtocolErrorTests(unittest.TestCase):
    def test_unknown_method_tool_and_bad_json(self):
        payload = json.dumps(req(1, "bogus/method")) + "\n" + json.dumps(
            req(2, "tools/call", {"name": "nope", "arguments": {}})) + "\n{not json\n"
        proc = subprocess.run([sys.executable, SERVER], input=payload, capture_output=True, text=True, timeout=60)
        out = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(out[0]["error"]["code"], -32601)
        self.assertEqual(out[1]["error"]["code"], -32602)
        self.assertEqual(out[2]["error"]["code"], -32700)

    def test_unknown_argument_is_a_tool_error_the_model_can_fix(self):
        by_id, _ = session(req(1, "tools/call", {"name": "probe", "arguments": {"input": "/x.png", "bogus": 1}}))
        result = by_id[1]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("bogus", result["content"][0]["text"])


class SurfacesAgreeTests(unittest.TestCase):
    """Completion check: contract --json, docs/contract.md and MCP tools/list name the
    same tools in the same order, and MCP inputSchema is the contract's input_schema."""

    def test_contract_docs_and_mcp_agree(self):
        contract = _contract.build_contract_payload()
        names = [t["name"] for t in contract["tools"]]
        with open(os.path.join(ROOT, "docs", "contract.md"), encoding="utf-8") as f:
            doc_names = re.findall(r"^### `([a-z_]+)`$", f.read(), re.M)
        by_id, _ = session(req(1, "tools/list"))
        mcp = by_id[1]["result"]["tools"]
        self.assertEqual(names, doc_names)
        self.assertEqual(names, [t["name"] for t in mcp])
        for spec, tool in zip(contract["tools"], mcp):
            expected = [d for d in spec["input_schema"]["properties"] if d != "json"]
            self.assertEqual(list(tool["inputSchema"]["properties"]), expected, spec["name"])
            self.assertEqual(tool["inputSchema"].get("required", []),
                             [d for d in spec["input_schema"]["required"] if d != "json"], spec["name"])


@unittest.skipUnless(which_magick(), "requires ImageMagick")
class ToolCallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = os.path.join(self.tmp.name, "in.png")
        write_solid_png(self.src, 64, 48)

    def test_probe_and_convert_through_mcp(self):
        out = os.path.join(self.tmp.name, "out.jpg")
        by_id, _ = session(
            req(1, "tools/call", {"name": "probe", "arguments": {"input": self.src}}),
            req(2, "tools/call", {"name": "convert", "arguments": {"input": self.src, "output": out}}),
            req(3, "tools/call", {"name": "convert", "arguments": {"input": self.src, "output": out}}),
        )
        probe = by_id[1]["result"]
        self.assertFalse(probe["isError"])
        self.assertEqual((probe["structuredContent"]["width"], probe["structuredContent"]["height"]), (64, 48))
        self.assertEqual(json.loads(probe["content"][0]["text"]), probe["structuredContent"])
        self.assertFalse(by_id[2]["result"]["isError"])
        self.assertTrue(os.path.isfile(out))
        refused = by_id[3]["result"]  # output now exists and overwrite was not given
        self.assertTrue(refused["isError"])
        self.assertFalse(refused["structuredContent"]["ok"])

    def test_cli_helpers(self):
        listed = subprocess.run([sys.executable, SERVER, "--list"], capture_output=True, text=True, check=True).stdout
        self.assertEqual(len(listed.strip().splitlines()), len(_contract.TOOL_META))
        called = subprocess.run([sys.executable, SERVER, "--call", "probe", json.dumps({"input": self.src})],
                                capture_output=True, text=True)
        self.assertEqual(called.returncode, 0)
        self.assertTrue(json.loads(called.stdout)["structuredContent"]["ok"])


if __name__ == "__main__":
    unittest.main()
