# Deliberate behaviours (read before filing a bug)

This file lists behaviours that look like defects on a first read but are decisions,
with the reason and the test that pins each one. If one of them is wrong for your case,
say which sentence here no longer holds.

## Outputs and files

- **`-o/--output` is required and must differ from the input.** No tool has an
  "in place" mode, and `mogrify` (ImageMagick's in-place editor) is never called. An
  agent that overwrote a user's only copy of a photo cannot undo it.
  Code: `_common.check_output_not_input()`. Tests: `test_convert_rejects_same_path`,
  `test_resize_rejects_same_path`.

- **An existing output is refused unless `--overwrite` is passed.** Silently replacing a
  file from an earlier run hides mistakes; the refusal happens before anything runs.
  Code: `_common.check_output_not_exists()`. Test:
  `test_convert_rejects_existing_output_without_overwrite_flag`.

- **A written file whose real format differs from its extension is deleted and reported
  as `ok: false`.** ImageMagick exits 0 and only warns on stderr when it has no encoder
  for the requested format (e.g. HEIC read-only builds), writing the *input's* format
  under the new name. Keeping that file would report success for a mislabeled image.
  Code: `_common.verify_output_format()`. Test: `test_flags_a_silently_wrong_format`.

- **`trim` deletes its result and fails when more than `--max-trim-percent` (90%) of the
  area would go.** A uniform or near-uniform image trims to a sliver; that means the
  input was not "an image with a border", and `--fuzz` is the knob to adjust.
  Code: `trim.run_trim()`. Test: `test_refuses_over_trim_on_solid_image`.

## Pixels

- **Every writing tool bakes EXIF orientation into the pixels (`-auto-orient`).** A
  phone photo stored sideways with an Orientation tag would otherwise come out sideways
  as soon as the tag is lost - `strip` removes it, and many web/OG consumers ignore it.
  Test: `test_exif_orientation_is_baked_into_the_pixels`.

- **`thumb` never upscales.** A thumbnail larger than its source is not a thumbnail;
  `--long-edge` is a ceiling (`-resize NxN>`). Test: `test_thumb_never_upscales`.

- **The skill never picks a size.** `resize --width/--height` and `thumb --long-edge` are
  required with no default: dimensions come from the user or the task, never from the
  skill's taste (SKILL.md rule 4). Test: `test_sizes_are_never_defaulted`.

## Arguments and results

- **A malformed invocation still answers with `ok: false` JSON under `--json`**, exit 1,
  instead of argparse's usage text and exit 2. Agents parse one shape for every failure.
  Code: `_common.JSONArgumentParser.error()`. Tests:
  `test_missing_required_flags_with_json_emits_ok_false_json`,
  `test_contract_cli_invalid_subcommand_emits_ok_false_json`.

- **`check` has no `--dry-run`.** It only reads; there is nothing to preview.
  Test: `test_check_has_no_dry_run_because_it_writes_nothing`.

- **`batch` keeps going after a file fails** and reports `all_ok: false` with a per-file
  `reason`, including a bad per-file argument. One corrupt photo should not cost the rest
  of the folder. Test: `test_per_file_argparse_error_is_recorded_not_fatal`.

## Backends

- **`strip` and `trim` have no `sips` path.** `sips` has no reliable blanket
  metadata-strip flag and no border detection; a partial strip that leaves GPS behind is
  worse than a clear "needs ImageMagick". Test:
  `test_doctor_sips_only_marks_strip_and_trim_unusable`.

- **`doctor` calls read-only HEIC "usable" but reports `write: false` with a fix.** The
  documented workflow reads HEIC (iPhone photos in) and writes something else; creating
  HEIC is reported separately so nobody assumes it. Test:
  `test_doctor_reports_heic_write_false_when_read_only`.

## Installing

- **`--codex` installs to `~/.agents/skills`, not `~/.codex/skills`.** That is where
  Codex reads user skills. Test: `test_codex_installs_where_codex_reads_user_skills`.

- **An old `image-skill` directory is removed only when it is provably this project's.**
  The npm name `image-skill` belongs to another author; a directory with that name may be
  theirs. Anything not matching the exact layout and markers is left with a warning.
  Tests: `test_own_legacy_install_is_removed`,
  `test_foreign_image_skill_is_left_alone_with_a_warning`,
  `test_own_layout_with_extra_user_file_is_left_alone`.

## Releasing

- **No release is ever cut for a major version automatically.** `major`/`breaking` labels
  make version resolution fail, and the bump step refuses to cross a major boundary. A
  major release is a hand-made `package.json` bump in a PR. Tests:
  `test_major_is_refused`, `test_major_crossing_is_refused_and_writes_nothing`.

- **A merge of only chore/ci/docs/test/refactor/dependency PRs releases nothing.**
  A version number should mean the shipped package changed. Test:
  `test_nothing_releasable`.
