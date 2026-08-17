---
name: agent-relay
description: >-
  Summarize what a git branch changed versus its baseline as a concise
  five-section Markdown report: one-liner, scale, core flow, new modules,
  development phases. Use when the user asks to “总结修改内容”, “总结分支”,
  “看看这个分支改了什么”, “总结一下改动”, “summarize changes”, “branch
  summary”, or wants a high-level digest of a diff or commit range.
---

# Branch Summary

Summarize what a branch changed compared to a baseline. The report is for a
human who wants to understand the work without reading the diff: what was
delivered, how big it is, how it works, what was added, and how it evolved.

## 1. Collect facts

Establish the baseline first — default `master`, fall back to `main`, then to
whatever the user names — then gather numbers from git:

```bash
git merge-base <base> HEAD
git log --oneline --date=short --pretty=format:'%ad %s' <base>..HEAD
git diff --stat <base>...HEAD | tail -1
```

Drill into the biggest changed directories to name modules:

```bash
git diff --stat <base>...HEAD -- <dir>
```

Adapt the same commands to other inputs: two arbitrary refs, a commit range,
or uncommitted work via `git status` and `git diff`. Every number in the
report comes from command output — never estimate.

## 2. Report format

Render exactly these five sections, in the user's language:

```markdown
# <branch> vs <base> 总结

**一句话**：<分支交付了什么、为了解决什么问题，一两句说完>

**规模**：<N> 个 commit，<M> 个文件，+<X>/-<Y> 行<（生成代码/大块配套占大头时注明）>。

## 核心业务流程

<入口或起点> → <步骤>（<关键文件>）
  → <步骤> → <步骤>
  → <最终动作和下游影响>

## 主要新增模块

| 模块 | 内容 |
| --- | --- |
| <目录/包名（约 N 行）> | <职责一句话 + 关键能力> |

## 开发演进

1. <阶段名>（<日期或日期范围>）：<该阶段 commit 主题的归纳>
2. …
```

## 3. Deliver

Show the report in the conversation, then persist it in the summarized
project so other agents can find it:

```text
.agents/handoff/<branch>-vs-<base>.md
```

Sanitize `/` in ref names to `-`. If `.agents/handoff/` is not covered by the
project's `.gitignore`, say so — the file should not be committed accidentally.

## 4. Writing constraints

- **一句话** answers “这个分支交付了什么”, not “我做了哪些动作”.
- **规模** numbers must come from git output; note when generated code
  (kitex_gen, protobuf, vendored files, lock files) dominates the line count.
- **核心业务流程** is the single main chain: arrows between steps, key file
  in parentheses, indented continuation lines. Do not enumerate branches or
  edge cases.
- **主要新增模块** aggregates by directory or package with its rough size,
  not file by file; include modified-but-existing modules only when the change
  is substantial.
- **开发演进** groups the commit timeline into 3–6 named phases with dates,
  one line each summarizing what its commits did.
- Report facts only — no review, no advice, no process narrative.
