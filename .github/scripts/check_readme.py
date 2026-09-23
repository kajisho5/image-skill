#!/usr/bin/env python3
"""Run every shell command in README.md, in order, in a throwaway HOME.

    python3 .github/scripts/check_readme.py

- `npm pack` builds the package from this checkout, and each `npx imagemagick-skill`
  runs that tarball (`npx --yes --package <tgz> imagemagick-skill ...`), so the install,
  doctor, contract and --uninstall examples exercise exactly what npm would ship.
- HOME is a new temporary folder: ~/.claude, ~/.cursor, ~/.agents and ~/.claude.json
  (`claude mcp add`, `claude plugin ...`) are all created inside it.
- Blocks that build or test the repository (unittest, demos/build.py, bin/install.js)
  run in a copy of this checkout; the others run in a folder holding photo.heic,
  made by demos/build.py's source generator.
- Absolute system paths the README writes to (/usr/local/bin/magick, /tmp/skills) are
  redirected into the sandbox, and `sudo` is dropped; everything else runs as written.
- Each ```bash block runs as one `bash -e` script; ```json blocks must parse.
- A block that calls `claude` is skipped (and reported) when the claude CLI is absent.

Exit status 0 only when every block ran (or was reported skipped) and the install
checks at the end hold. Development-only: needs node/npm, python3 and ImageMagick.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_MARKERS = ("unittest discover", "demos/build.py", "bin/install.js", "contract_md.py", "evals/run.py")


def blocks(markdown):
    for m in re.finditer(r"^```(\w+)\n(.*?)^```", markdown, re.S | re.M):
        yield m.group(1), m.group(2)


def prepare_inputs(folder):
    sys.path.insert(0, os.path.join(ROOT, "demos"))
    import build  # noqa: E402 - demos/build.py

    build.WORK = folder
    build.MAGICK = build.which_magick()
    if not build.MAGICK:
        sys.exit("check_readme: ImageMagick (magick) is required")
    build.make_sources()


def main():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    sandbox = tempfile.mkdtemp(prefix="readme-check-")
    home = os.path.join(sandbox, "home")
    work = os.path.join(sandbox, "work")
    repo = os.path.join(sandbox, "repo")
    for d in (home, work, os.path.join(home, "bin")):
        os.makedirs(d)
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".work"))

    packed = subprocess.run(["npm", "pack", "--silent", "--pack-destination", sandbox],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    tgz = os.path.join(sandbox, packed.stdout.strip().splitlines()[-1])
    prepare_inputs(work)

    env = dict(os.environ, HOME=home, npm_config_cache=os.path.join(sandbox, "npm-cache"),
               npm_config_update_notifier="false",
               PATH=os.path.join(home, "bin") + os.pathsep + os.environ["PATH"])
    have_claude = shutil.which("claude") is not None
    results = []
    for n, (lang, body) in enumerate(blocks(readme), start=1):
        first = body.strip().splitlines()[0] if body.strip() else ""
        if lang == "json":
            json.loads(body)
            results.append((n, "ok", "json parses: " + first[:60]))
            continue
        if lang != "bash":
            continue
        script = body
        script = script.replace("npx imagemagick-skill", f"npx --yes --package {tgz} imagemagick-skill")
        script = script.replace("/usr/local/bin/magick", os.path.join(home, "bin", "magick-shim"))
        script = script.replace("/tmp/skills", os.path.join(sandbox, "tmp-skills"))
        script = re.sub(r"(^|\|\s*)sudo ", r"\1", script, flags=re.M)
        if "claude " in script and not have_claude:
            results.append((n, "SKIPPED", "claude CLI not installed: " + first[:60]))
            continue
        cwd = repo if any(m in script for m in REPO_MARKERS) else work
        proc = subprocess.run(["bash", "-e", "-c", script], cwd=cwd, env=env,
                              capture_output=True, text=True, timeout=1800)
        status = "ok" if proc.returncode == 0 else f"FAILED (exit {proc.returncode})"
        results.append((n, status, first[:70]))
        if proc.returncode != 0:
            print(f"--- block {n} failed ---\n{body}\n--- stdout ---\n{proc.stdout[-3000:]}\n"
                  f"--- stderr ---\n{proc.stderr[-3000:]}", file=sys.stderr)

    # The README's own install/uninstall sequence, checked from the outside.
    skill = os.path.join(home, ".claude", "skills", "imagemagick-skill")
    checks = []
    if os.path.isdir(skill):
        checks.append(("~/.claude/skills/imagemagick-skill still present after the Install block's --uninstall", False))
    else:
        checks.append(("--uninstall removed ~/.claude/skills/imagemagick-skill", True))
    for target in (".cursor/skills/imagemagick-skill", ".agents/skills/imagemagick-skill"):
        checks.append((f"--all installed ~/{target}", os.path.isfile(os.path.join(home, target, "SKILL.md"))))
    shim = os.path.join(home, "bin", "magick-shim")
    if os.path.isfile(shim):
        ran = subprocess.run([shim, "-version"], capture_output=True, text=True)
        checks.append(("the README's magick shim runs ImageMagick", "ImageMagick" in ran.stdout))
    subprocess.run(["npx", "--yes", "--package", tgz, "imagemagick-skill"], cwd=work, env=env,
                   check=True, capture_output=True)
    doctor = subprocess.run(["npx", "--yes", "--package", tgz, "imagemagick-skill", "doctor", "--json"],
                            cwd=work, env=env, capture_output=True, text=True)
    checks.append(("install -> doctor --json parses", bool(json.loads(doctor.stdout).get("platform"))))
    subprocess.run(["npx", "--yes", "--package", tgz, "imagemagick-skill", "--uninstall"], cwd=work,
                   env=env, check=True, capture_output=True)
    checks.append(("install -> --uninstall leaves nothing", not os.path.exists(skill)))

    for n, status, first in results:
        print(f"block {n:2d}  {status:8}  {first}")
    for label, ok in checks:
        print(f"check     {'ok' if ok else 'FAILED':8}  {label}")
    print(f"tarball: {os.path.basename(tgz)}   sandbox: {sandbox}")
    failed = [r for r in results if r[1].startswith("FAILED")] + [c for c in checks if not c[1]]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
