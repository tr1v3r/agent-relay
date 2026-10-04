# Compact evidence references

Read this when a report has shared evidence, old-side sources, or an expansion
request. These examples are schematic: replace placeholders only with observed
Git identities and inspected sources, never treat them as evidence themselves.

## One legend, short references

Keep the five report blocks. Put coverage and the legend beside scale; put
source definitions within the module block. A two-module layout can be:

```text
编号：M=模块，E=证据；仅本报告有效。

核心链路：M1 请求入口（E1）→ M2 重试策略（E2）→ 有界重试

模块               变更量       内容 / 证据
M1 请求入口         +12/-4       将临时失败交给策略（E1）
M2 重试策略         +31/-2       限制重试次数（E2）

证据绑定：target=<full SHA>; old=<full comparison-old-side SHA>
E1：target:<entry path>，<read symbol/line span>；old→target 对应 hunk
    → 入口新增策略调用。
E2：target:<policy path>，<read symbol/line span>；<test path/read span>
    → 尝试次数有上限；测试包含该断言（未运行）。
```

The actual report links paths when possible. Full SHA aliases are defined once
in the report, not kept only in the agent's memory. A source can be reused by
multiple M entries if it supports each claim. IDs never replace readable names
or precise source coordinates. Module totals still come from Git, not the
number of lines quoted in evidence.

## Old-side and mutable sources

- **Committed deletion:** E1 points to `old:<deleted path>` and the deletion hunk. For a
  merge-base branch comparison, `old` is the merge-base; for an explicit tree
  comparison, it is that comparison's left endpoint. Reading only the target
  cannot establish what the removed implementation used to do.
- **Committed rename:** retain `old/path → new/path`; bind old content to the
  old SHA and new content to target. Do not infer behavior from a filename alone.
- **WIP:** identify `staged`, `unstaged`, or `untracked` with observed HEAD (or
  unborn) and the inspected range. Staged compares HEAD → index (empty tree →
  index when unborn); unstaged compares index → worktree. Label old/new paths
  against those layers. A HEAD permalink does not contain WIP bytes, and neither
  index nor worktree has a commit SHA. For example, a staged `a → b` rename
  followed by an unstaged deletion of `b` has two distinct sources: HEAD:`a` →
  index:`b`, then index:`b` → worktree:(absent). Cite the actual index content
  for the deletion, not HEAD:`b`, which may never have existed. If an expansion
  observes different bytes, separate that new observation from the old one.
- **Incomplete read:** if a tool truncates a hunk, finish that relevant read or
  narrow the claim. Do not cite unread line numbers or label a sampled module
  as fully inspected. Missing objects remain explicit limitations.

An empty tree delta needs no M/E legend, modules, or flow, but it can coexist
with nonzero selected history. For a change followed by its revert, report the
real commit count and evidence-backed evolution despite zero net changed files.
Do not turn the lack of module references into a claim of zero commits.

## Progressive reading, complete summary

Start with the complete status/numstat inventory, then inspect central changed
implementation, tests, and relevant contracts in bounded slices. Generated
output may only be counted, but the report says so. All five summary blocks
remain visible initially; extra source detail is expanded on request. This is
not a promise that every source line has been read or tests passed.

For “expand M2”, reuse the original endpoints and ID definitions even if a
branch has since moved. Read the originally bound source first, append E IDs
when needed, and do not renumber the report. If the report's identity is no
longer available, request it rather than guessing what M2 meant.

## Inspiration, not compatibility

AOCI's [FRAS specification](https://github.com/aoci-spec/aoci-code/blob/fdb4cb9bf54d14bbe87002b58c6d72aefb706617/spec/public/aoci-object-fras-v2.txt)
uses compact, dictionary-defined semantic tags and canonical object references.
Its [Overview delivery contract](https://github.com/aoci-spec/aoci-code/blob/fdb4cb9bf54d14bbe87002b58c6d72aefb706617/docs/overview-delivery.md)
requires complete Whole-Index delivery; chunking is transport, not permission to
claim complete understanding from a sample.

Agent Relay borrows the idea of concise labels backed by explicit meaning and
traceable sources. `M`/`E` IDs are an original report-local convention, not AOCI
tags, object identities, or protocol compatibility. There is no FRAS dictionary,
importance rating, persistent index, MCP server, or AOCI runtime dependency.
