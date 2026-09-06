#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const PKG_ROOT = path.join(__dirname, "..");
const SCRIPTS_SRC = path.join(PKG_ROOT, "scripts");
const SKILL_MD_SRC = path.join(PKG_ROOT, "SKILL.md");

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function toPosix(relPath) {
  return relPath.split(path.sep).join("/");
}

function installClaudeCode(cwd) {
  const dest = path.join(cwd, ".claude", "skills", "image-skill");
  fs.mkdirSync(dest, { recursive: true });
  fs.copyFileSync(SKILL_MD_SRC, path.join(dest, "SKILL.md"));
  copyDir(SCRIPTS_SRC, path.join(dest, "scripts"));
  return dest;
}

function installCursor(cwd, skillDir) {
  const rel = toPosix(path.relative(cwd, skillDir));
  const dir = path.join(cwd, ".cursor", "rules");
  fs.mkdirSync(dir, { recursive: true });
  const dest = path.join(dir, "image-skill.mdc");
  const body = `---
description: Local image editing (probe/convert/resize/thumb/strip/trim/check) that never overwrites originals.
globs:
alwaysApply: false
---

Full instructions: ${rel}/SKILL.md
Scripts: ${rel}/scripts/ (Python 3.9+ stdlib, needs \`magick\` or macOS \`sips\` on PATH)

Run \`python3 ${rel}/scripts/_contract.py doctor --json\` before using any tool that needs a backend.
`;
  fs.writeFileSync(dest, body);
  return dest;
}

function installCodex(cwd, skillDir) {
  const rel = toPosix(path.relative(cwd, skillDir));
  const marker = "<!-- image-skill:start -->";
  const endMarker = "<!-- image-skill:end -->";
  const block = `${marker}
## image-skill

Local image editing (probe/convert/resize/thumb/strip/trim/check) that never
overwrites originals. Full instructions: ${rel}/SKILL.md
Run \`python3 ${rel}/scripts/_contract.py doctor --json\` first.
${endMarker}
`;
  const agentsPath = path.join(cwd, "AGENTS.md");
  let existing = "";
  if (fs.existsSync(agentsPath)) {
    existing = fs.readFileSync(agentsPath, "utf8");
    if (existing.includes(marker)) {
      const re = new RegExp(`${marker}[\\s\\S]*?${endMarker}\\n?`);
      existing = existing.replace(re, "");
    }
  }
  const next = existing.trimEnd() + (existing.trim() ? "\n\n" : "") + block;
  fs.writeFileSync(agentsPath, next);
  return agentsPath;
}

function runDoctor() {
  const doctorScript = path.join(SCRIPTS_SRC, "_contract.py");
  const result = spawnSync("python3", [doctorScript, "doctor", "--json"], {
    stdio: "inherit",
  });
  process.exit(result.status === null ? 1 : result.status);
}

function main() {
  const command = process.argv[2];
  const cwd = process.cwd();

  if (command === "doctor") {
    runDoctor();
    return;
  }

  if (command && command !== "install") {
    console.error(`unknown command: ${command}`);
    console.error("usage: npx image-skill [install|doctor]");
    process.exit(1);
  }

  const skillDir = installClaudeCode(cwd);
  const cursorFile = installCursor(cwd, skillDir);
  const agentsFile = installCodex(cwd, skillDir);

  console.log("image-skill installed:");
  console.log(`  Claude Code: ${toPosix(path.relative(cwd, skillDir))}/SKILL.md`);
  console.log(`  Cursor:      ${toPosix(path.relative(cwd, cursorFile))}`);
  console.log(`  Codex:       ${toPosix(path.relative(cwd, agentsFile))} (AGENTS.md block)`);
  console.log("");
  console.log("Next: npx image-skill doctor");
}

main();
