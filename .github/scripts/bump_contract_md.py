#!/usr/bin/env python3
"""Move docs/contract.md's current-version mentions from one release to the next.

Only the two places that state the version being released move - never a blind
replace of the old version string, which would also rewrite historical mentions:

  - the `skill.version` row: "the npm / package.json version (`X`)"
  - the `contract --json` example: `"skill": {"id": "imagemagick-skill", "version": "X"`

Each must be found exactly once; anything else is an error rather than a silent
partial bump.
"""
import sys

ANCHORS = (
    "the npm / package.json version (`{v}`)",
    '"skill": {{"id": "imagemagick-skill", "version": "{v}"',
)


def bump_contract_md(text, old, new):
    for anchor in ANCHORS:
        before, after = anchor.format(v=old), anchor.format(v=new)
        n = text.count(before)
        if n != 1:
            raise ValueError(f"docs/contract.md: expected exactly one {before!r}, found {n}")
        text = text.replace(before, after)
    return text


def main(argv):
    if len(argv) != 4:
        print("usage: bump_contract_md.py PATH OLD NEW", file=sys.stderr)
        return 2
    path, old, new = argv[1:]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        text = bump_contract_md(text, old, new)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
