#!/usr/bin/env python3
"""List the agent eval prompts, or print one ready to paste into an agent session.

    python3 evals/run.py --list
    python3 evals/run.py --show og-webp --fixtures /tmp/fx --out /tmp/out

FIXTURES and OUTDIR in a prompt are replaced by the given directories (create the
fixtures with evals/write_fixtures.py). Grading is done by reading the agent's run
against the entry's `expect` - see evals/README.md.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    with open(os.path.join(HERE, "agent_prompts.json"), encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--show")
    parser.add_argument("--fixtures", default="FIXTURES")
    parser.add_argument("--out", default="OUTDIR")
    args = parser.parse_args(argv)
    prompts = load()
    if args.list or not args.show:
        for p in prompts:
            kind = "decline" if p.get("decline") else "ask" if p.get("ask") else " -> ".join(p["expect"])
            print(f"{p['id']:28} {kind}")
        return 0
    match = [p for p in prompts if p["id"] == args.show]
    if not match:
        print(f"unknown id: {args.show}", file=sys.stderr)
        return 1
    print(match[0]["prompt"].replace("FIXTURES", args.fixtures.rstrip("/")).replace("OUTDIR", args.out.rstrip("/")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
