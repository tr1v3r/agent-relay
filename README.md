# Agent Relay

Agent Relay is a platform-neutral Agent Skill for one-shot handoffs between independent agent tasks or sessions.

It transfers the minimum sufficient state needed to understand, verify, record, or continue a task without copying the full conversation. Native task messaging, shared files, queues, A2A gateways, and manual copy/paste can all carry the same protocol envelope.

## What it provides

- A sender and receiver workflow in [`SKILL.md`](SKILL.md)
- Task-to-Task Handoff Protocol 1.0 in [`references/protocol.md`](references/protocol.md)
- A JSON Schema for `handoff.ready` and `handoff.ack`
- A Python standard-library CLI to create, validate, render, acknowledge, and optionally verify Git state
- Evaluation prompts covering native messaging, shared-file fallback, verification, and deduplication

## Flow

```text
worker agent/session
    ↓ handoff.ready
native message | shared file | queue | manual relay
    ↓
coordinator/receiving agent
    ↓ validate and verify
durable project or knowledge record
    ↓ handoff.ack
worker agent/session
```

## Quick start

Create a handoff and capture Git state from a worktree:

```bash
python scripts/handoff.py create \
  --task-id TASK-001 \
  --title "Implement the notification preferences API" \
  --status completed \
  --source-agent coding-agent \
  --target-agent work-manager \
  --workspace /path/to/worktree \
  --summary "Implemented the API and focused unit tests" \
  --decision "Reused the existing domain model" \
  --verification "go test ./service/example/...: passed" \
  --next-action "Create the PR and complete integration testing" \
  --output .agents/handoff/HANDOFF.json
```

Validate and compare the recorded Git state with a local worktree:

```bash
python scripts/handoff.py validate .agents/handoff/HANDOFF.json \
  --check-git /path/to/worktree
```

Render a human-readable copy:

```bash
python scripts/handoff.py render .agents/handoff/HANDOFF.json \
  --output .agents/handoff/HANDOFF.md
```

Acknowledge successful ingestion:

```bash
python scripts/handoff.py ack .agents/handoff/HANDOFF.json \
  --receiver-agent work-manager \
  --disposition ingested \
  --verified \
  --record records/projects/example-project.md \
  --output .agents/handoff/ACK.json
```

## Installation

Copy or link this repository into the skill directory used by an Agent Skills-compatible runtime. The skill itself is described entirely by `SKILL.md`; Python and Git are optional and only required for the helper CLI and Git verification.

The protocol does not depend on Codex, Claude, a specific model, or a specific message API. A platform adapter only needs to deliver the JSON envelope without changing its `handoff_id` or meaning.

## Design boundary

Agent Relay is intentionally not a workflow engine or a live shared-memory system. It handles task-boundary handoff:

- the source prepares a concise result and evidence bundle;
- the receiver verifies material claims and records durable information;
- retries preserve the same `handoff_id`;
- the receiver acknowledges `accepted`, `ingested`, `needs_changes`, or `rejected`.

## License

[MIT](LICENSE) © 2026 tr1v3r
