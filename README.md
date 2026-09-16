# Agent Relay

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

## How it works

The skill instructs an agent to:

1. resolve the user-specified baseline or the repository's actual default branch;
2. resolve and consistently use immutable base, target, and merge-base commit
   identities;
3. collect commit, file, rename, binary, and line statistics from one consistent
   Git range;
4. inspect the patch and representative implementation, tests, and documentation;
5. separate committed changes from staged, unstaged, and untracked work without
   double-counting paths shared by multiple worktree states;
6. produce a factual five-part summary without review findings or invented phases.

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

## Installation

Copy or link this repository into the skill directory of any Agent
Skills-compatible runtime.

## License

[MIT](LICENSE) © 2026 tr1v3r
