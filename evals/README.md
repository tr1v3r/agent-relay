# Evaluation datasets and deterministic Git regression

These are three separate layers, not interchangeable test results:

| Layer | Files | What is checked |
| --- | --- | --- |
| Deterministic Git regression | `../scripts/git_fixtures.py`, `../tests/test_git_contract.py` | Real temporary Git repositories verify comparison commands and known fixture facts. No model runs. |
| Trigger dataset | `trigger-evals.json` | `query` / `should_trigger` examples for a future skill-selection experiment. CI checks structure only. |
| Post-invocation behavior datasets | `evals.json`, supplementary `*.json` objects | Prompts and expectations for a future agent run. CI checks structure and fixture linkage, not whether an agent follows instructions. |

The Git tests are **development tooling**, not a runtime collector. Their explicit
command contracts are not extracted from or automatically equivalent to the skill
prompt. Passing CI does not establish model triggering accuracy, semantic
compliance, evidence quality, safe persistence, or a quality improvement over a
baseline. There are no model benchmark scores in this repository from these tests.
Behavior cases may describe desired edge-case contracts ahead of prompt changes;
their presence is not evidence that the current skill satisfies them.

## Run locally

Requires Python 3.11+ and Git with `git init --initial-branch` support (Git 2.28+).
No pip packages, credentials, API calls, or remote fetches are needed.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

CI runs this command on Ubuntu with Python 3.11 and 3.13, alongside the existing
skill-structure checks. Fixture repositories are created under Python temporary
directories and automatically cleaned up. Fixed identities/dates and isolated Git
configuration prevent user signing, hooks, global ignores, attributes, and inherited
`GIT_*` environment variables from changing the cases. Tests compare dynamically
resolved object IDs rather than assuming a particular hash algorithm or Git version.
The shallow-history test clones only a local fixture using a `file://` URL; it does
not contact a remote server.

## Materialize a repository for a real agent run

Run from the skill checkout and choose a **nonexistent** destination:

```sh
python3 scripts/git_fixtures.py divergent /tmp/agent-relay-divergent
python3 scripts/git_fixtures.py wip /tmp/agent-relay-wip
```

The CLI prints its absolute path and named commit IDs as JSON, and refuses to
reuse an existing destination. It does not modify the skill checkout or configure
an actual remote. `origin/main` and `origin/HEAD` are local fixture refs.
Use the matching case's `prompt` in that repository, with the intended skill version
available, and record the skill revision, model, prompt, transcript, final report,
and any output files. Materialize a fresh repository for each run/configuration
because a save scenario can change its worktree. The prompt's branch names are
labels, not evidence of implemented business behavior.

To evaluate skill quality, grade actual runs against their expectations and review
the evidence and report. To claim comparative improvement, run the same fixture and
prompt with a baseline skill and the candidate, retain per-run results, and account
for model variability. That experiment is **not** part of this deterministic CI.

## Fixture coverage

| ID | Known facts / purpose |
| --- | --- |
| `divergent` | Main has a unique file; feature has two commits adding two lines. Branch-introduced diff: 1 file, +2/-0. Endpoint diff: 2 files, +2/-1. Right-only history: 2; symmetric history: 3. |
| `deletion` | Remote default points to baseline; one commit deletes a one-line fallback file. |
| `wip` | Staged 2, unstaged 2, untracked 2; union 5 literal paths. `common.txt` cancels between layers. Tracked net: 2 files, +2/-0. Ignored file excluded. |
| `artifacts` | One pure rename, two binary files, generated file (+100) and lockfile (+50): 5 records, +150/-0 text lines. Generated attribute is explicit. |
| `empty` | HEAD and origin/main are identical; also provides an existing fallback ref when testing invalid explicit input. |
| `commits` | Root, ordinary commit and two-parent merge; parent 1 diff is side.txt, parent 2 diff is one.txt. A merge's single-commit history is one commit even when parent1..merge contains two. Parent choice requires user input. |
| `special-paths` | Six paths containing spaces, tab, newline, Unicode, leading dash and pathspec magic; NUL-safe records and literal selection. Tests additionally stage a special-name rename. |
| `unrelated` | Two independent roots: no branch attribution, but an explicitly requested endpoint comparison is possible. |
| `unborn` | No HEAD; one staged and one untracked file. Layer facts exist, HEAD net diff does not. |
| `criss-cross` | Two equally best merge bases; do not silently choose one for branch attribution. |
| `net-zero-history` | Two commits change and restore a file: nonempty history with an empty final tree diff. |

Tests additionally cover staged rename followed by unstaged deletion (both literal
paths touched, index-side evidence preserved, one net deleted file), immutable IDs
after a ref moves, and missing parents in a shallow local clone. The NUL parser in the tests handles numstat rename records;
it is deliberately not shipped as a production report generator. Rename-aware
change-record counts and a working-tree touched-path union are different metrics:
for a rename, the literal touched set includes both old and new names.

## Add datasets

`tests/test_datasets.py` automatically discovers every `evals/*.json` file.

- Trigger data is a nonempty list of objects with a nonempty `query` and a Boolean
  `should_trigger`; queries must be unique within the file.
- Behavior data is an object with `skill_name: "agent-relay"`, optional
  `dataset_type: "behavior"`, and nonempty `evals`.
- Each behavior case has a string/integer `id` unique **within its dataset**, a
  nonempty `prompt`, `expected_output`, `expectations` (list of nonempty strings),
  and `files` (list of existing repository-relative input file paths).
- `fixture` is optional or null for **guidance-only scenarios**. When present it
  must name a registered builder. A linked fixture supplies repeatable input but
  still does not execute the agent or validate its report.
- Supplementary evidence or handoff datasets may use guidance-only scenarios;
  their schema passing does not mean hostile filesystem cases or safe writes were
  executed. Add real execution coverage separately when appropriate.

Do not add generated model transcripts/results as input datasets in this folder;
keep experiment artifacts outside the skill checkout.
