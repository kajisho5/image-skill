# Agent evals

`agent_prompts.json` holds natural-language requests an agent with this skill installed
should handle, in the same format as ffmpeg-skill's evals:

| Key | Meaning |
| --- | --- |
| `id` | stable name |
| `prompt` | what the user says; `FIXTURES` and `OUTDIR` are placeholders for directories |
| `expect` | scripts the agent should run, in order; `a.py\|b.py` means either is right |
| `decline` | `true`: out of scope - the agent says so (video, GIF animation, AI editing, face recognition, RAW) and runs no raw `magick`/`ffmpeg` instead |
| `ask` | `true`: the request lacks something the skill never guesses (e.g. a size) - the agent asks |
| `note` | what a grader should look for beyond the script list |

Every run is also graded on the rules in SKILL.md: no raw `magick`/`convert`/`mogrify`/
`sips` command typed by the agent, no input file modified, `check.py` (or `probe.py`) on
every written output, and the report in the user's language.

## Running

```bash
python3 evals/write_fixtures.py /tmp/imsk-fixtures        # synthetic inputs, needs magick
python3 evals/run.py --list
python3 evals/run.py --show og-webp --fixtures /tmp/imsk-fixtures --out /tmp/imsk-out
```

Paste the printed prompt into a fresh agent session that has the skill installed
(`npx imagemagick-skill`), then compare the scripts it ran with `expect`. There is no
automated grader in this repository yet; results are not published until one exists.
`tests/test_evals.py` checks that the file itself stays valid (unique ids, only real
scripts in `expect`, placeholders only).
