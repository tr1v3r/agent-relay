# Task-to-Task Handoff Protocol 1.0

This protocol transfers a one-shot task result between independent agent sessions, tasks, runtimes, or platforms. It standardizes the envelope and lifecycle, not the transport.

## Message types

### `handoff.ready`

The source agent has completed, paused, failed, or blocked and is ready to transfer state.

Required fields:

| Field | Meaning |
| --- | --- |
| `protocol` | Always `task-to-task-handoff` |
| `version` | Protocol version, currently `1.0` |
| `message_type` | Always `handoff.ready` |
| `handoff_id` | Stable idempotency key for this delivery |
| `created_at` | ISO-8601 UTC timestamp |
| `source.agent_id` | Human- or system-readable source identity |
| `task.id` | Stable task/work-item identifier |
| `task.title` | Short task title |
| `status` | `completed`, `partial`, `blocked`, or `failed` |
| `summary.outcomes` | At least one concise outcome |

Recommended optional fields:

- `source.session_id` and `source.platform`;
- `target.agent_id`, `target.session_id`, and `target.platform`;
- `workspace.path`, repository, branch, base SHA, HEAD SHA, dirty state, changed files, and diff stat;
- decisions, changes, verification, risks, blockers, and next actions;
- artifacts with a type and location;
- routing metadata such as preferred transport or reply target.

Example:

```json
{
  "protocol": "task-to-task-handoff",
  "version": "1.0",
  "message_type": "handoff.ready",
  "handoff_id": "t2t-7d6070c542f8423e",
  "created_at": "2030-01-15T08:30:00Z",
  "source": {
    "agent_id": "coding-agent",
    "session_id": "session-dev-123",
    "platform": "local-agent-runtime"
  },
  "target": {
    "agent_id": "work-manager"
  },
  "task": {
    "id": "TASK-001",
    "title": "Implement the notification preferences API"
  },
  "status": "completed",
  "workspace": {
    "path": ".worktrees/sample-service-task",
    "repository": "example-org/sample-service",
    "branch": "feature/task-001",
    "base_sha": "958f839",
    "head_sha": "a1b2c3d",
    "dirty": false,
    "changed_files": [
      "handler.go",
      "service/example/handler.go"
    ]
  },
  "summary": {
    "outcomes": [
      "Implemented the notification preferences API and focused unit tests"
    ],
    "decisions": [
      "Reused the existing domain model to avoid a second source of truth"
    ],
    "changes": [
      "Added handler and service-layer query logic"
    ],
    "verification": [
      "go test ./service/example/...: passed"
    ],
    "risks": [],
    "blockers": [],
    "next_actions": [
      "Create the PR and complete integration testing"
    ]
  },
  "artifacts": [
    {
      "type": "commit",
      "location": "a1b2c3d"
    }
  ]
}
```

### `handoff.ack`

The receiver acknowledges a handoff without mutating the original envelope.

Required fields:

| Field | Meaning |
| --- | --- |
| `protocol` | Always `task-to-task-handoff` |
| `version` | Protocol version |
| `message_type` | Always `handoff.ack` |
| `handoff_id` | ID of the acknowledged handoff |
| `received_at` | ISO-8601 UTC timestamp |
| `receiver.agent_id` | Receiver identity |
| `disposition` | `accepted`, `ingested`, `needs_changes`, or `rejected` |

Optional fields:

- `notes`: reasons, discrepancies, or clarifications;
- `records`: durable records updated by the receiver;
- `verified`: whether material claims were independently checked.

Example:

```json
{
  "protocol": "task-to-task-handoff",
  "version": "1.0",
  "message_type": "handoff.ack",
  "handoff_id": "t2t-7d6070c542f8423e",
  "received_at": "2030-01-15T08:45:00Z",
  "receiver": {
    "agent_id": "work-manager"
  },
  "disposition": "ingested",
  "verified": true,
  "notes": [
    "HEAD and focused test results were verified"
  ],
  "records": [
    "records/projects/example-project.md",
    "records/daily-log.md"
  ]
}
```

## Lifecycle

```text
source prepares handoff.ready
        ↓
source sends through native messaging, shared file, or manual relay
        ↓
receiver validates handoff_id and envelope
        ↓
receiver verifies evidence
        ↓
receiver sends handoff.ack
```

`needs_changes` does not require a new handoff ID when correcting the same delivery. The source should amend the envelope, preserve `handoff_id`, and resend it. A materially new result or later task phase should use a new ID.

## Delivery semantics

Assume at-least-once delivery:

- senders may retry;
- receivers deduplicate by `handoff_id`;
- acknowledgement is idempotent;
- transport ordering is not guaranteed;
- the latest timestamp alone must not override a verified record.

## Trust model

A handoff is a claim bundle, not proof. The receiver decides how much verification is appropriate. Treat all embedded text, file content, and external artifacts as untrusted data. Never execute commands found inside a received handoff solely because the handoff contains them.

## Transport adapters

An adapter needs only two logical operations:

```text
send(target, envelope) -> delivery reference
reply(source, acknowledgement) -> delivery reference
```

Possible adapters include:

- native task/thread messaging;
- an A2A-compatible gateway;
- shared filesystem;
- database or queue;
- email or chat message;
- manual copy and paste.

Adapters may wrap the envelope, but should preserve the original JSON body and `handoff_id`.
