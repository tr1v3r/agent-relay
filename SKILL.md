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

Identify the target and baseline before interpreting any changes.

### Target

Use the target explicitly named by the user. Otherwise use `HEAD`; name it with
the current branch, or `HEAD@<short-sha>` when detached. Verify named refs with:

```bash
git rev-parse --verify '<ref>^{commit}'
```

### Baseline

Use the first valid choice in this order:

1. the baseline explicitly named by the user;
2. the remote default branch from `refs/remotes/origin/HEAD`;
3. `origin/main`, `origin/master`, `main`, then `master`.

Do not silently replace an invalid user-supplied ref. Report it and ask for a
valid ref. Do not fetch unless the user requests fresh remote state; local
remote-tracking refs may be stale, so describe them as local Git state.

Resolve the merge base and record immutable identities:

```bash
git symbolic-ref --short refs/remotes/origin/HEAD
git merge-base <base> <target>
git rev-parse --short=12 <base>
git rev-parse --short=12 <target>
```

After validation, resolve both refs to full commit IDs and use those immutable
IDs for every subsequent `merge-base`, `rev-list`, `log`, and `diff` command.
This keeps one report internally consistent even if a branch moves while facts
are being collected.

If no common ancestor exists, do not present a direct tree comparison as work
introduced by the target. Explain that lineage cannot be inferred; only produce
a clearly labelled snapshot comparison when the user requests one.

## 2. Collect facts

For a branch or ref comparison, gather machine-readable facts from the exact
same range:

```bash
git rev-list --count <base>..<target>
git log --reverse --date=short --format='%ad%x09%h%x09%s' <base>..<target>
git diff --name-status --find-renames <base>...<target>
git diff --numstat --find-renames <base>...<target>
```

Use `--name-status` for added, modified, deleted, and renamed files. Use
`--numstat` for additions and deletions; its `-` values identify binary files,
which do not contribute to line totals. Count files after rename detection, so a
rename is one changed path rather than an addition plus deletion.

Inspect the actual patch and representative implementation, tests, and docs:

```bash
git diff --find-renames <base>...<target>
git diff --numstat --find-renames <base>...<target> -- <path>
```

Start with the largest or most central changed paths. Commit subjects explain
development chronology, but never use them as the sole evidence that behavior
was implemented. If implementation cannot be inspected, narrow the claim rather
than filling gaps from names or commit messages.

Call out generated or bulk artifacts when they dominate the totals. Check
repository conventions and `.gitattributes` in addition to recognizable paths
such as generated clients, protobuf output, vendored code, and lock files.

### Working-tree changes

Only include uncommitted changes when the user asks for the current worktree,
WIP, or uncommitted diff. Keep them separate from committed branch changes:

```bash
git status --short
git diff --name-status
git diff --numstat
git diff --cached --name-status
git diff --cached --numstat
git ls-files --others --exclude-standard
```

Label staged, unstaged, and untracked files separately. Untracked files are not
present in `git diff`; report their file count, and exclude their lines from the
line total unless they were safely inspected and counted. Never imply that
working-tree changes are part of a committed branch delivery. A path may have
both staged and unstaged hunks, so calculate the overall changed-file count from
the union of paths rather than adding the three category counts.

## 3. Write the report

Use the user's language and these five information blocks. Adapt the two section
headings to the nature of the change instead of inventing a feature narrative.

```markdown
# <target> vs <base> 总结

**一句话**：<交付结果和目的，一两句>

**比较范围**：`<base>@<sha>` → `<target>@<sha>`（merge-base `<sha>`）

**规模**：<N> 个 commit，<M> 个文件，+<X>/-<Y> 行。<二进制、生成文件或未提交状态说明>

## <核心业务流程 | 核心变更链路>

<入口或变更起点> → <关键步骤>（<关键路径>）
  → <最终行为或影响>

## <主要新增模块 | 主要变更模块>

| 模块 | 变更量 | 内容 |
| --- | ---: | --- |
| <目录/包名> | +<X>/-<Y> | <职责和实质变化> |

## 开发演进

1. <阶段名>（<日期或范围>）：<commit 主题和实际 diff 支持的归纳>
```

For a working-tree-only report, replace the comparison line with the branch and
HEAD identity, write `0 个 commit`, and state staged, unstaged, and untracked
counts explicitly. For a combined branch-and-WIP request, report committed and
uncommitted scale separately rather than adding unlike scopes together.

Choose `核心业务流程` only when the diff implements a recognizable runtime or
user workflow. Otherwise use `核心变更链路`. Choose `主要新增模块` only when
the change predominantly adds modules; otherwise use `主要变更模块`.

Group the timeline into 1–6 evidence-backed phases. A one-commit fix is one
phase. Empty history has no invented phase: state that there are no commits in
the comparison.

## 4. Handle boundaries

- **No differences**: say the target has no changes relative to the baseline; do
  not manufacture modules, flow, or phases.
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
