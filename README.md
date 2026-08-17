# Agent Relay

An Agent Skill that turns a git branch's changes into a five-section,
human-readable Markdown report. The report is shown in the conversation and
saved to `.agents/handoff/<branch>-vs-<base>.md` in the summarized project,
so other agents can find it.

## Report shape

一句话 → 规模 → 核心业务流程 → 主要新增模块（表格）→ 开发演进

例如：

> **一句话**：为离职流程新建了一个"离职报告智能体"——在员工离职人群聊中接入 AI Agent，自动生成风险研判报告。
>
> **规模**：96 个 commit，97 个文件，+41k/-9.4k 行（其中 kitex_gen 生成代码占大头）。

## How it works

The skill instructs an agent to collect facts with git (`log`, `diff --stat`,
merge-base against `master`/`main`), then render the five-section template
under writing constraints that keep the report factual and aggregate-based.
No scripts, no protocol — instructions only.

## Installation

Copy or link this repository into the skill directory of any Agent
Skills-compatible runtime. Requires git.

## License

[MIT](LICENSE) © 2026 tr1v3r
