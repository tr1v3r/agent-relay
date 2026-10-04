---
name: agent-relay
description: >-
  Summarize Git branch, ref, commit-range, or working-tree changes as a concise,
  evidence-backed five-part Markdown report covering the outcome, exact scale,
  main change flow, changed modules, and development phases. Use for requests
  such as “总结修改内容”, “总结分支”, “看看这个分支改了什么”, “总结一下改动”,
  “summarize changes”, “branch summary”, or a high-level digest of a Git diff.
  Do not use for a general product or repository overview, code review, release
  notes, or non-Git status summary unless the user specifically asks to frame it
  as a branch or diff summary.
---

# Branch Summary

Explain what a Git change set delivered without making the reader inspect the
diff. Build the report from repository evidence: refs define the comparison,
diffs establish what changed, implementation and tests explain behavior, and
commit history shows how the work evolved.

## 1. Resolve the comparison

Choose the comparison mode before interpreting changes. A tree delta and a
commit set answer different questions; name both rather than calling them one
range. Preserve explicit notation; ask when the requested meaning is ambiguous.

If clarification is required (invalid ref, ambiguous mode, missing merge parent,
or multiple merge bases), ask when interaction is available. In headless runs,
without an interaction tool, or when no answer is available, return the missing
decision and verified facts, then stop the blocked comparison. Do not guess,
invent scale, or wait/retry indefinitely. For combined requests, label the blocked
scope and report only independently resolved scopes; a blocker notice need not
fill the five-part report with placeholders.

| Request / mode | Tree delta (left → right) | History for count and phases |
| --- | --- | --- |
| What a branch introduced (default branch summary) | unique merge-base(base, target) → target | `base..target`, target-only reachable commits |
| Endpoint snapshot / explicit `A..B` diff | A → B | `A..B` only as labelled right-only supporting history, not the full explanation of the tree delta |
| Explicit `A...B` diff (`branch-introduced`) | unique merge-base(A, B) → B | `A..B`, labelled right-only history |
| Single commit C | sole parent → C; root uses empty tree | C only, exactly 1 commit |
| Merge commit C | selected parent → C | C only, exactly 1 commit; ask which parent if unspecified |
| Working tree / WIP | HEAD → index; index → worktree; tracked net HEAD → worktree | no commits; untracked files separate |

For `git diff`, `A..B` means the same endpoint comparison as `A B`, not a
merge-base comparison. For `git log`, `A...B` means the symmetric difference of
two histories, not the three-dot diff's target-only history. If the user asks for
that commit set, use `--left-right` and label both sides; do not turn it into a
single target-development timeline. Do not silently rewrite `..` to `...`.

### Target

Use the target explicitly named by the user. Otherwise use `HEAD`; name it with
the current branch, or `HEAD@<short-sha>` when detached. Verify named refs with:

```bash
git rev-parse --verify '<ref>^{commit}'
```

### Baseline

For branch summaries that need baseline discovery, use the first valid choice
in this order. Explicit endpoints and single-commit requests bypass discovery:

1. the baseline explicitly named by the user;
2. the remote default branch from `refs/remotes/origin/HEAD` (resolve with
   `git symbolic-ref --short refs/remotes/origin/HEAD`);
3. `origin/main`, `origin/master`, `main`, then `master`.

Do not silently replace an invalid user-supplied ref. Report it and ask for a
valid ref. Do not fetch unless the user requests fresh remote state; local
remote-tracking refs may be stale, so describe them as local Git state.

Resolve refs to full commit IDs with `git rev-parse --verify '<ref>^{commit}'`
and use those immutable IDs in subsequent `merge-base`, `rev-list`, `log`, and
`diff` commands. Short IDs are display labels only. This keeps the report
consistent even if a branch moves while facts are being collected.

For branch-introduced or three-dot comparisons, enumerate all merge bases:

```bash
git merge-base --all <base> <target>
```

Use the result only when exactly one merge base exists. With no common ancestor,
do not call a direct tree comparison work introduced by the target; offer an
explicitly requested snapshot instead. With multiple merge bases, do not pick
one arbitrarily: explain the ambiguity and ask for explicit comparison endpoints
or a snapshot. Shallow history or missing objects may prevent finding ancestry;
report that limitation rather than asserting the histories are unrelated.

For single commits, inspect parents with `git rev-list --parents -n 1 <commit>`.
Use the sole parent, or ask the user to select a merge parent. For a genuine root,
obtain the repository-format empty-tree ID with `git hash-object -t tree --stdin`
(empty input); use it as the left tree, not a commit/history baseline. A shallow
boundary is not proof of a root. Do not use a merge's default combined diff as a
substitute for a selected-parent comparison.

## 2. Collect facts

Record the mode (`branch-introduced`, `endpoint-snapshot`, `single-commit`, or
`working-tree`), resolved tree endpoints, and history selection. Use the chosen
`<left>` and `<right>` trees consistently for every file, line, module, and patch
query; do not mix endpoint and merge-base statistics.

```bash
git diff --name-status -z --find-renames <left> <right>
git diff --numstat -z --find-renames <left> <right>
```

For branch-introduced comparisons, collect the right-only history separately:

```bash
git rev-list --count <base>..<target>
git log --reverse --date=short --format='%ad%x09%h%x09%s' <base>..<target>
```

For endpoint snapshots, these history commands are optional supporting evidence;
label any count as right-only commits, not commits that uniquely produced the
snapshot delta. Baseline-side changes can contribute to that delta too. For a
single commit, count 1 and use `git log -1` on that commit, not an ancestor range.

Use `--name-status` for added, modified, deleted, and renamed files. Use
`--numstat` for additions and deletions; its `-` values identify binary files,
which do not contribute to line totals. Count files after rename detection, so a
rename is one changed path rather than an addition plus deletion. Parse `-z`
records (including rename source/destination fields), not whitespace or lines:
branch diffs can contain spaces, tabs, and newlines in filenames too.

Inspect the actual patch and representative implementation, tests, and docs:

```bash
git diff --find-renames <left> <right>
git --literal-pathspecs diff --numstat -z --find-renames <left> <right> -- '<path>'
```

For exact file queries, quote paths and use `--literal-pathspecs`: `--` ends
option/revision parsing but does not disable pathspec magic such as `:(glob)`.

Read progressively rather than dumping a large patch into context:

1. Inventory the whole comparison with path status and numstat; group paths into
   modules and distinguish handwritten changes from generated/bulk artifacts.
2. Read bounded patches for entry points, central changed behavior, and relevant
   tests/docs first; expand to related callers or contracts when a claim needs
   them. Read the selected commit's content, not an unrelated current checkout.
3. If output is truncated, continue the relevant file/hunk before citing it.
   Filename matches, commit subjects, and statistics alone are not behavior
   evidence. Narrow or omit claims whose implementation cannot be inspected.

Keep exact whole-comparison statistics separate from semantic reading coverage.
In the scale block, briefly name the inspected areas and anything only counted
or not inspected (for example generated output). Do not call representative
sampling a complete code review or claim all changed behavior was verified.
Reading a test establishes what it checks, not that it passed; report execution
results only when actually observed. Commit subjects explain chronology, not
proof of implementation.

Call out generated or bulk artifacts when they dominate the totals. Check
repository conventions and `.gitattributes` in addition to recognizable paths
such as generated clients, protobuf output, vendored code, and lock files.
When relevant generation inputs or configuration exist (for example schemas,
`buf.yaml`, or a Makefile), inspect them read-only in the selected version to
trace the output's origin. Do not run generators for a summary. If that origin
cannot be established, disclose the gap rather than infer it from filenames.

### Working-tree changes

Only include uncommitted changes when the user asks for the current worktree,
WIP, or uncommitted diff. Keep them separate from committed branch changes:

Freeze the current HEAD as `<head>`; WIP is relative to that checkout, not an
arbitrary target ref. If combining a different target with WIP, label the two
contexts explicitly. Collect the layers and tracked net independently:

```bash
git status --short
git diff --name-status -z --find-renames
git diff --numstat -z --find-renames
git diff --cached --name-status -z --find-renames <head>
git diff --cached --numstat -z --find-renames <head>
git diff --name-status -z --find-renames <head>
git diff --numstat -z --find-renames <head>
git ls-files -z --others --exclude-standard
```

Label staged (HEAD → index), unstaged (index → worktree), and untracked files
separately. The last diff pair measures tracked net HEAD → worktree: never add
staged and unstaged line totals, since their edits may overlap or cancel. A file
can appear in both layers yet have zero net changes. Report layer counts,
touched-path union, and tracked net file/line totals as distinct quantities.
For the union, deduplicate literal paths across layers and untracked entries;
include both names of a rename in that path set, and label it touched paths,
not rename-aware changed-file count. Net counts come from the net diff with
rename detection. Use NUL-delimited output (`-z`) if parsing unusual filenames.

Untracked files are absent from these diffs: count them separately, and exclude
their lines from tracked net totals. If inspected and counted, label their line
count separately. In an unborn repository, use `git diff --cached` without a
HEAD argument for staged additions, plus unstaged and untracked layers; report
no HEAD and no HEAD-relative net total. Unmerged index entries prevent a normal
net summary; disclose conflicts instead of presenting incomplete counts as a
clean snapshot. Index/worktree are mutable: recheck status after collection and
recollect or disclose any observed changes. Never imply WIP is committed delivery.

## 3. Write the report

Use the user's language and these five information blocks. Adapt the two section
headings to the nature of the change instead of inventing a feature narrative.

```markdown
# <target> vs <base> 总结

**一句话**：<交付结果和目的，一两句>

**比较范围**：<mode>；树 `<left>@<sha>` → `<right>@<sha>`；历史 <selection>（如适用，注明 base/target 与唯一 merge-base）

**规模**：<N> 个 commit，<M> 个文件，+<X>/-<Y> 行。<二进制、生成文件或未提交状态说明>
**阅读覆盖**：<已读实现/测试范围；仅统计或未检查部分>
**编号**：M=模块，E=证据；仅在本报告内有效，可追问“展开 M1 / E1”。

## <核心业务流程 | 核心变更链路>

<入口或变更起点>（M1 <模块名>，E1）→ <关键步骤>
  → <最终行为或影响>

## <主要新增模块 | 主要变更模块>

| 编号 / 模块 | 变更量 | 内容 / 证据 |
| --- | ---: | --- |
| M1 <目录/包名> | +<X>/-<Y> | <职责和实质变化>（E1） |

**证据**：
- E1：<范围与完整 SHA 或工作区状态>，<实际读取的路径、符号/行段或 diff hunk> → <支持的事实>

## 开发演进

1. <阶段名>（<日期或范围>）：<commit 主题和实际 diff 支持的归纳>
```

Keep comparison metadata within the scale block, not a sixth information block.
For endpoint snapshots, label counts `右侧独有 N 个 commit（辅助历史）`,
or state that no commit history was selected. For single
commits, identify the selected parent or root empty tree and report 1 commit.
For a working-tree-only report, name the branch and HEAD identity (or unborn),
write `0 个 commit`, and state the three layer counts and tracked net separately.
For combined branch-and-WIP requests, report committed and uncommitted scale
separately rather than adding unlike scopes together.

Choose `核心业务流程` only when the diff implements a recognizable runtime or
user workflow. Otherwise use `核心变更链路`. Choose `主要新增模块` only when
the change predominantly adds modules; otherwise use `主要变更模块`.

Group the timeline into 1–6 evidence-backed phases. A one-commit fix is one
phase. Empty history has no invented phase: state that the selected commit set
is empty. If history was not selected or is unavailable, say so rather than
claiming there are zero commits.

### Compact references and follow-up

Use `M1`, `M2`, ... for modules and `E1`, `E2`, ... for evidence, allocated in
first-appearance order. Keep readable names beside module IDs. Define each ID
once, reuse it consistently, and resolve every reference inside the report;
an ID is a local handle, not a permanent identity or an importance score.
A shared source can support several modules through the same E entry, but only
for facts that source actually establishes. Do not force separate evidence for
every sentence or invent modules merely to fill the template.

Keep evidence definitions inside the module block, not a sixth top-level
section. Each E entry identifies its supporting fact and a precise source:

- For committed content, bind the full commit SHA and repository-relative path
  plus the inspected symbol, line span, or diff hunk. Full SHA aliases may be
  defined once and reused; abbreviated display IDs alone are not the binding.
- For committed deletions, use the comparison's old-side SHA and old path; for
  committed renames, record old → new paths and which side was read. In a branch
  comparison the old tree is the merge-base, not necessarily the baseline tip.
- For a diff or Git-derived count, bind the exact frozen endpoints, comparison
  mode, and any path filter/calculation. Do not substitute a commit subject.
- For WIP, label staged, unstaged, or untracked, the observed HEAD (or unborn),
  and the inspected path/range. Bind the actual layer pair: staged is HEAD →
  index (empty tree → index when unborn); unstaged is index → worktree. WIP
  deletions and renames identify the old path in that old layer, plus the new
  path for a rename. An unstaged deletion's old content is in the index, not
  necessarily HEAD; never invent a commit SHA for the index or worktree. These
  are mutable observations; recheck before reuse and disclose changes.

Use links to inspected sources where the host can resolve them; do not invent
remote URLs or link a deleted path as though it exists in the target. Missing
objects or unavailable lines mean limited evidence, not a fabricated locator.
For a one-module fix, a single M/E pair and inline source suffice. With an empty
tree delta, omit M/E scaffolding and do not invent changed modules or a flow.
This does not imply empty history: preserve any nonzero selected commit count
and evidence-backed evolution (for example a change followed by its revert).

On “expand M2 / E3”, keep the original comparison mode, frozen endpoints, and
ID meanings, and read only the additional relevant evidence. Append new IDs
without reassigning old ones. Do not silently switch to current HEAD; if the
original report or binding is unavailable, ask for it. A changed worktree needs
an explicitly labelled fresh observation rather than confirmation of old WIP.
Return the requested detail; the initial response still contains all five blocks.
See [evidence examples](references/evidence.md) for compact layouts and edge cases.

## 4. Handle boundaries

- **No tree differences**: say the selected tree delta is empty; do not manufacture
  modules or flow. History can still be nonempty (for example a reverted change),
  and empty right-only history does not imply an empty endpoint delta. Describe
  evidenced history separately, without claiming a net delivery.
- **Initial repository with no commits**: summarize working-tree files only when
  requested; otherwise explain that no commit comparison is available.
- **Detached HEAD**: use `HEAD@<short-sha>` as the target label.
- **Binary files or submodules**: count changed paths, but do not invent line
  counts or internal behavior.
- **Shallow history or missing objects**: state the limitation and avoid claims
  that require unavailable history.
- **Review findings**: keep defects, recommendations, and approval judgments out
  of this report. This skill summarizes; it does not review.

Every number must come from Git output or an explicitly described calculation.
Prefer exact `+X/-Y` module totals over “about N lines.” Report facts only, and
distinguish observed implementation from inferred intent.

## 5. Deliver

Always show the complete report in the conversation. Persist it only when the
user asks to save, archive, hand off, or relay the result:

```text
.agents/handoff/<target>-vs-<base>.md
```

For a working-tree-only report, use `<target>-working-tree.md`. Sanitize each ref
component by replacing every character outside `[A-Za-z0-9._-]` with `-`.

Before writing, check whether `.agents/handoff/` is ignored. If it is not, warn
the user so the report is not committed accidentally. If the directory cannot
be written, still return the full report and mention that persistence failed;
file output must not block the summary.
