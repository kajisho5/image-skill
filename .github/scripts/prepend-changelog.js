#!/usr/bin/env node
"use strict";

// Reads RELEASE_VERSION / RELEASE_BODY from the environment and prepends a
// new CHANGELOG.md section under the existing "# Changelog" heading.
//
// RELEASE_BODY is release-drafter's generated body, which is built from
// contributor-supplied PR titles - untrusted text. It reaches this script
// only via process.env (set through the workflow's `env:` block), never via
// GitHub Actions `${{ }}` template substitution into a run: block. That
// substitution happens before the shell/script even starts, so attacker
// content there (e.g. a PR titled with backticks or `$()`) could otherwise
// execute as part of the workflow. Reading it as plain env data here is safe
// regardless of what characters it contains.

const fs = require("fs");
const path = require("path");

const version = process.env.RELEASE_VERSION;
const body = process.env.RELEASE_BODY || "";

if (!version) {
  console.error("RELEASE_VERSION is required");
  process.exit(1);
}

const changelogPath = path.join(__dirname, "..", "..", "CHANGELOG.md");
const heading = "# Changelog";
const existing = fs.existsSync(changelogPath) ? fs.readFileSync(changelogPath, "utf8") : `${heading}\n`;

const date = new Date().toISOString().slice(0, 10);
const newSection = `## v${version} (${date})\n\n${body.trim()}\n`;

let updated;
if (existing.startsWith(heading)) {
  const rest = existing.slice(heading.length).replace(/^\n+/, "");
  updated = `${heading}\n\n${newSection}\n${rest}`;
} else {
  updated = `${heading}\n\n${newSection}\n${existing}`;
}

fs.writeFileSync(changelogPath, updated);
console.log(`CHANGELOG.md updated for v${version}`);
