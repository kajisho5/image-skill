#!/usr/bin/env node
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const PKG_ROOT = path.join(__dirname, "..");
const SCRIPTS_SRC = path.join(PKG_ROOT, "scripts");
const SKILL_MD_SRC = path.join(PKG_ROOT, "SKILL.md");
const PACKAGE_JSON_SRC = path.join(PKG_ROOT, "package.json");
const SKILL_NAME = "image-skill";

const USAGE = `usage: npx image-skill [target] [--uninstall]
       npx image-skill doctor [--json]
       npx image-skill contract --json
       npx image-skill --help

Install targets (default: global Claude Code):
  (no flag)          ~/.claude/skills/image-skill
  --cursor           ~/.cursor/skills/image-skill
  --codex            ~/.codex/skills/image-skill
  --all              all of the above
  --dir <parent>     <parent>/image-skill
  --project          ./.claude/skills/image-skill (current project only)

  --uninstall        remove the installed target(s) instead of installing
`;

function targetDirs(flags, cwd) {
  const home = os.homedir();
  if (flags.dir) {
    return [path.join(flags.dir, SKILL_NAME)];
  }
  if (flags.project) {
    return [path.join(cwd, ".claude", "skills", SKILL_NAME)];
  }
  const globalTargets = {
    claude: path.join(home, ".claude", "skills", SKILL_NAME),
    cursor: path.join(home, ".cursor", "skills", SKILL_NAME),
    codex: path.join(home, ".codex", "skills", SKILL_NAME),
  };
  if (flags.all) {
    return [globalTargets.claude, globalTargets.cursor, globalTargets.codex];
  }
  if (flags.cursor) return [globalTargets.cursor];
  if (flags.codex) return [globalTargets.codex];
  return [globalTargets.claude];
}

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (entry.name === "__pycache__") continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function installTo(dir) {
  // Wipe first so a reinstall never leaves an older version's scripts behind.
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  fs.copyFileSync(SKILL_MD_SRC, path.join(dir, "SKILL.md"));
  fs.copyFileSync(PACKAGE_JSON_SRC, path.join(dir, "package.json"));
  copyDir(SCRIPTS_SRC, path.join(dir, "scripts"));
}

function uninstallFrom(dir) {
  const existed = fs.existsSync(dir);
  fs.rmSync(dir, { recursive: true, force: true });
  return existed;
}

function warnIfNoBackend() {
  const doctorScript = path.join(SCRIPTS_SRC, "_contract.py");
  const result = spawnSync("python3", [doctorScript, "doctor", "--json"], { encoding: "utf8" });
  if (result.error || result.status !== 0 || !result.stdout) {
    return; // python3 missing or doctor itself failed; `doctor` will surface the real error
  }
  let payload;
  try {
    payload = JSON.parse(result.stdout);
  } catch {
    return;
  }
  if (payload.ok) return;

  console.warn("");
  console.warn("warning: no usable image backend found (magick or sips).");
  console.warn("  macOS:          brew install imagemagick");
  console.warn("  Debian/Ubuntu:  sudo apt install imagemagick");
  console.warn("  Windows:        https://imagemagick.org/script/download.php#windows");
  console.warn("  Then check:     npx image-skill doctor");
  console.warn("");
}

function runContractOrDoctor(command, extraArgs) {
  const script = path.join(SCRIPTS_SRC, "_contract.py");
  const result = spawnSync("python3", [script, command, ...extraArgs], { stdio: "inherit" });
  process.exit(result.status === null ? 1 : result.status);
}

function parseFlags(argv) {
  const flags = {
    cursor: false,
    codex: false,
    all: false,
    project: false,
    uninstall: false,
    dir: null,
    help: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    switch (arg) {
      case "--cursor":
        flags.cursor = true;
        break;
      case "--codex":
        flags.codex = true;
        break;
      case "--all":
        flags.all = true;
        break;
      case "--project":
        flags.project = true;
        break;
      case "--uninstall":
        flags.uninstall = true;
        break;
      case "--help":
      case "-h":
        flags.help = true;
        break;
      case "--dir":
        flags.dir = argv[++i];
        if (!flags.dir) {
          console.error("--dir requires a path argument");
          process.exit(1);
        }
        break;
      default:
        console.error(`unknown flag: ${arg}`);
        console.error(USAGE);
        process.exit(1);
    }
  }
  return flags;
}

function main() {
  const argv = process.argv.slice(2);
  const command = argv[0];

  if (command === "doctor" || command === "contract") {
    runContractOrDoctor(command, argv.slice(1));
    return;
  }

  const flags = parseFlags(argv);
  if (flags.help) {
    console.log(USAGE);
    return;
  }

  const dirs = targetDirs(flags, process.cwd());

  if (flags.uninstall) {
    let removedAny = false;
    for (const dir of dirs) {
      if (uninstallFrom(dir)) {
        console.log(`removed: ${dir}`);
        removedAny = true;
      }
    }
    if (!removedAny) console.log("nothing to remove");
    return;
  }

  for (const dir of dirs) {
    installTo(dir);
    console.log(`installed: ${dir}`);
  }
  console.log("");
  console.log("Already installed? Re-running replaces the copy with whatever version you run.");
  console.log("Next: npx image-skill doctor");

  warnIfNoBackend();
}

main();
