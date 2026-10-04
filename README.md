# Agent Relay

[![CI](https://github.com/tr1v3r/agent-relay/actions/workflows/ci.yml/badge.svg)](https://github.com/tr1v3r/agent-relay/actions/workflows/ci.yml)

An Agent Skill that turns a Git branch, ref range, or working tree into a
concise, evidence-backed Markdown report. It is designed for someone who wants
to understand what changed without reading the full diff.

## Report shape

The report keeps five recognizable information blocks:

> **一句话** → **比较范围与规模** → **核心流程/变更链路** →
> **主要变更模块** → **开发演进**

Headings adapt to the change. A feature can use “核心业务流程” and “主要新增模块”;
a bug fix, refactor, deletion, configuration update, or documentation change uses
the more neutral “核心变更链路” and “主要变更模块.”

## Compact references

Reports use `M1`, `M2`, … for named modules and `E1`, `E2`, … for evidence.
A single legend explains them, and every reference resolves within that report
to inspected source, a frozen Git identity, or an explicitly labelled worktree
observation. Ask “expand M2 / E1” to see more detail without changing the original
comparison. IDs are local to one report, not permanent repository identifiers.

Large diffs are read progressively: inventory the full change set, then inspect
central implementation and related tests/contracts. The report distinguishes
exact overall statistics from sampled reading coverage; reading tests does not
imply they passed. Small fixes need only one M/E pair. An empty tree delta gets
no artificial references, but any nonzero selected history is still reported.

This is an original lightweight adaptation inspired by AOCI's compact semantic
representation, not an AOCI protocol implementation. See the
[evidence guide](references/evidence.md) for examples and pinned upstream sources.

## How it works

The skill instructs an agent to:

1. select branch-introduced, endpoint-snapshot, single-commit, or working-tree
   mode; preserve explicit `A..B` versus `A...B` diff semantics;
2. resolve immutable identities and require a unique merge base only for
   branch-introduced comparisons; ask for a parent when summarizing a merge commit;
3. collect tree-delta statistics consistently, keeping the selected commit history
   distinct from the trees being compared;
4. inspect the patch and representative implementation, tests, and documentation;
5. separate committed changes, staged/unstaged/untracked layers, touched paths,
   and tracked net WIP changes—layer line totals can cancel and are not additive;
6. produce a factual five-part summary without review findings or invented phases.

A branch summary compares its unique merge base to the target. An endpoint
snapshot (including explicit `A..B` diffs) compares the two trees directly, even
when their histories diverge. `A...B` diffs use the merge base, whereas `git log
A...B` selects both sides' unique commits. Single root commits compare against
an empty tree; single merge commits require an explicitly selected parent.
Missing or multiple merge bases are disclosed, never silently replaced with a
snapshot or an arbitrary ancestor. If a required clarification cannot be answered
in a headless/non-interactive run, the agent returns the missing decision and
verified facts, then stops that comparison without guessing numbers or waiting
indefinitely. Independently resolved scopes of a combined request can still be
reported.

No scripts or runtime protocol are required. Git is the only dependency.

## Persistence

The complete report is always returned in the conversation. When the user asks
to save, archive, hand off, or relay it, the report is also written to:

```text
.agents/handoff/<target>-vs-<base>.md
```

The repository should ignore `.agents/handoff/` so generated reports are not
committed accidentally. A write failure does not prevent the conversational
summary.

## Evaluation coverage

The bundled eval set covers multi-module feature branches, one-commit bug fixes,
dirty worktrees, generated-code-heavy changes, empty comparisons, and near-miss
requests that should not trigger this skill.

The [eight evidence cases](evals/evidence.json) additionally specify M/E mapping,
committed deletion, WIP layers, generated-output provenance and rename coverage,
scope-preserving follow-up, empty comparisons, zero-net-change history, and a
staged rename followed by an unstaged deletion. Fixture associations make the
Git inputs reproducible; dataset validation and Git-fact tests do not establish
that a model has passed these behavioral expectations.

## Installation

Copy or link this repository into the skill directory of any Agent
Skills-compatible runtime.

## License

[MIT](LICENSE) © 2026 tr1v3r
