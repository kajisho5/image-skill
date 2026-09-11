#!/usr/bin/env node
"use strict";

// Reads NEW_VERSION from the environment (set via `env:` in the workflow,
// never interpolated into a shell script with `${{ }}`) and writes it into
// package.json. Called only when release.yml has decided an auto-bump is
// safe (package.json's current version still matches the latest tag).

const fs = require("fs");
const path = require("path");

const newVersion = process.env.NEW_VERSION;
if (!newVersion) {
  console.error("NEW_VERSION is required");
  process.exit(1);
}

const pkgPath = path.join(__dirname, "..", "..", "package.json");
const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
pkg.version = newVersion;
fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + "\n");
console.log(`package.json version set to ${newVersion}`);
