#!/usr/bin/env python3
"""Render the per-tool section of docs/contract.md from `_contract.py contract --json`.

    python3 .github/scripts/contract_md.py --write   # regenerate the block in place
    python3 .github/scripts/contract_md.py --check   # exit 1 if the block is stale

Only the text between the BEGIN/END markers is generated; the rest of the page is
written by hand. tests/test_contract_docs.py runs the same comparison, so a flag added
to a script's parser without regenerating the doc fails CI instead of drifting.
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

BEGIN = "<!-- BEGIN GENERATED: tools (python3 .github/scripts/contract_md.py --write) -->"
END = "<!-- END GENERATED: tools -->"
DOC = os.path.join(ROOT, "docs", "contract.md")


def _cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _type(prop):
    t = prop.get("type", "string")
    if isinstance(t, list):
        t = " or ".join(t)
    if t == "array" and prop.get("items", {}).get("type"):
        t = f"array of {prop['items']['type']}"
    if prop.get("enum"):
        t += ": " + " | ".join(f"`{e}`" for e in prop["enum"])
    return t


def _argument(dest, prop):
    cli = prop.get("cli")
    if cli == "positional":
        return f"`{dest}` (positional)"
    if cli == "after --":
        return f"`{dest}` (after `--`)"
    return ", ".join(f"`{c}`" for c in cli)


def render_tool(tool):
    schema = tool["input_schema"]
    yes_no = lambda b: "yes" if b else "no"  # noqa: E731
    lines = [
        f"### `{tool['name']}`",
        "",
        tool["description"],
        "",
        f"- Script: `{tool['executable']}` · role: {tool['role']} · backends: {', '.join(tool['backends'])}",
        f"- Writes a file: {yes_no(tool['writes_output'])} · `--dry-run`: {yes_no(tool['supports_dry_run'])}"
        f" · `--json`: {yes_no(tool['supports_json'])} · verify with: "
        + (", ".join(f"`{v}`" for v in tool["verify"]) or "-"),
        "",
        "| Argument | Type | Required | Default | Description |",
        "| --- | --- | --- | --- | --- |",
    ]
    for dest, prop in schema["properties"].items():
        default = prop.get("default")
        lines.append(
            f"| {_argument(dest, prop)} | {_cell(_type(prop))} | {yes_no(dest in schema['required'])} | "
            f"{'' if default is None else '`' + _cell(json.dumps(default)) + '`'} | {_cell(prop.get('description', ''))} |"
        )
    out = tool["output_schema"]
    lines += [
        "",
        "Output of `--json` on success (`ok: true`):",
        "",
        "| Key | Type | Always present | Description |",
        "| --- | --- | --- | --- |",
        "| `ok` | boolean | yes | `true` |",
    ]
    for key, prop in out["properties"].items():
        lines.append(
            f"| `{key}` | {_cell(_type(prop))} | {yes_no(key in out['required'])} | {_cell(prop.get('description', ''))} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_tools_markdown(payload):
    parts = [BEGIN, ""]
    for tool in payload["tools"]:
        parts.append(render_tool(tool))
    parts.append(END)
    return "\n".join(parts)


def current_block(text):
    start = text.index(BEGIN)
    end = text.index(END) + len(END)
    return text[start:end]


def expected_block():
    import _contract

    return render_tools_markdown(_contract.build_contract_payload())


def main(argv):
    with open(DOC, encoding="utf-8") as f:
        text = f.read()
    expected = expected_block()
    if "--write" in argv:
        with open(DOC, "w", encoding="utf-8", newline="") as f:
            f.write(text.replace(current_block(text), expected))
        return 0
    if current_block(text) != expected:
        print("docs/contract.md is stale: run python3 .github/scripts/contract_md.py --write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
