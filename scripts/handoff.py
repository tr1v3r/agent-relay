#!/usr/bin/env python3
"""Create, validate, render, and acknowledge Task-to-Task handoffs.

Uses only the Python standard library. Git integration is optional.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Iterable


PROTOCOL = "task-to-task-handoff"
VERSION = "1.0"
READY_STATUSES = {"completed", "partial", "blocked", "failed"}
ACK_DISPOSITIONS = {"accepted", "ingested", "needs_changes", "rejected"}
MAX_GIT_LINES = 200


class HandoffError(ValueError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def nonempty(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")


def string_list(value: Any, path: str, errors: list[str], required: bool = False) -> None:
    if value is None and not required:
        return
    if not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return
    if required and not value:
        errors.append(f"{path} must contain at least one item")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{path}[{index}] must be a non-empty string")


def identity_errors(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return
    nonempty(value.get("agent_id"), f"{path}.agent_id", errors)


def validate_envelope(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be an object"]

    if data.get("protocol") != PROTOCOL:
        errors.append(f"protocol must equal {PROTOCOL!r}")
    if data.get("version") != VERSION:
        errors.append(f"version must equal {VERSION!r}")
    nonempty(data.get("handoff_id"), "handoff_id", errors)

    message_type = data.get("message_type")
    if message_type == "handoff.ready":
        nonempty(data.get("created_at"), "created_at", errors)
        identity_errors(data.get("source"), "source", errors)
        if "target" in data:
            identity_errors(data.get("target"), "target", errors)

        task = data.get("task")
        if not isinstance(task, dict):
            errors.append("task must be an object")
        else:
            nonempty(task.get("id"), "task.id", errors)
            nonempty(task.get("title"), "task.title", errors)

        if data.get("status") not in READY_STATUSES:
            errors.append(
                "status must be one of " + ", ".join(sorted(READY_STATUSES))
            )

        summary = data.get("summary")
        if not isinstance(summary, dict):
            errors.append("summary must be an object")
        else:
            string_list(summary.get("outcomes"), "summary.outcomes", errors, True)
            for key in (
                "decisions",
                "changes",
                "verification",
                "risks",
                "blockers",
                "next_actions",
            ):
                string_list(summary.get(key), f"summary.{key}", errors)

        artifacts = data.get("artifacts", [])
        if not isinstance(artifacts, list):
            errors.append("artifacts must be an array")
        else:
            for index, artifact in enumerate(artifacts):
                if not isinstance(artifact, dict):
                    errors.append(f"artifacts[{index}] must be an object")
                    continue
                nonempty(artifact.get("type"), f"artifacts[{index}].type", errors)
                nonempty(
                    artifact.get("location"),
                    f"artifacts[{index}].location",
                    errors,
                )

    elif message_type == "handoff.ack":
        nonempty(data.get("received_at"), "received_at", errors)
        identity_errors(data.get("receiver"), "receiver", errors)
        if data.get("disposition") not in ACK_DISPOSITIONS:
            errors.append(
                "disposition must be one of "
                + ", ".join(sorted(ACK_DISPOSITIONS))
            )
        string_list(data.get("notes"), "notes", errors)
        string_list(data.get("records"), "records", errors)
    else:
        errors.append("message_type must be 'handoff.ready' or 'handoff.ack'")

    return errors


def git_output(workspace: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(workspace), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def limited_lines(text: str | None) -> tuple[list[str], bool]:
    if not text:
        return [], False
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[:MAX_GIT_LINES], len(lines) > MAX_GIT_LINES


def git_snapshot(workspace_arg: str, base_sha: str | None) -> dict[str, Any] | None:
    workspace = Path(workspace_arg).expanduser()
    if git_output(workspace, "rev-parse", "--is-inside-work-tree") != "true":
        return None

    head = git_output(workspace, "rev-parse", "HEAD")
    branch = git_output(workspace, "branch", "--show-current") or "(detached)"
    status_lines, status_truncated = limited_lines(
        git_output(workspace, "status", "--porcelain")
    )
    changed_files, files_truncated = limited_lines(
        git_output(
            workspace,
            "diff",
            "--name-only",
            base_sha if base_sha else "HEAD",
        )
    )
    untracked = [line[3:] for line in status_lines if line.startswith("?? ")]
    for item in untracked:
        if item not in changed_files:
            changed_files.append(item)

    diff_stat, stat_truncated = limited_lines(
        git_output(
            workspace,
            "diff",
            "--stat",
            base_sha if base_sha else "HEAD",
        )
    )

    snapshot: dict[str, Any] = {
        "path": workspace_arg,
        "branch": branch,
        "head_sha": head or "",
        "dirty": bool(status_lines),
        "changed_files": changed_files[:MAX_GIT_LINES],
        "diff_stat": diff_stat,
    }
    if base_sha:
        snapshot["base_sha"] = base_sha
    if status_truncated or files_truncated or stat_truncated:
        snapshot["truncated"] = True
    return snapshot


def atomic_json_write(path_arg: str, data: dict[str, Any]) -> None:
    if path_arg == "-":
        json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    path = Path(path_arg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary:
        json.dump(data, temporary, indent=2, ensure_ascii=False)
        temporary.write("\n")
        temp_name = temporary.name
    os.replace(temp_name, path)


def load_json(path_arg: str) -> dict[str, Any]:
    try:
        if path_arg == "-":
            data = json.load(sys.stdin)
        else:
            with open(path_arg, encoding="utf-8") as handle:
                data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise HandoffError(str(error)) from error
    if not isinstance(data, dict):
        raise HandoffError("root must be a JSON object")
    return data


def parse_artifacts(items: Iterable[str]) -> list[dict[str, str]]:
    artifacts = []
    for item in items:
        if "=" not in item:
            raise HandoffError(
                f"artifact {item!r} must use TYPE=LOCATION syntax"
            )
        artifact_type, location = item.split("=", 1)
        if not artifact_type.strip() or not location.strip():
            raise HandoffError(
                f"artifact {item!r} must use non-empty TYPE=LOCATION values"
            )
        artifacts.append(
            {"type": artifact_type.strip(), "location": location.strip()}
        )
    return artifacts


def deterministic_id(data: dict[str, Any]) -> str:
    workspace = data.get("workspace", {})
    identity = {
        "task_id": data["task"]["id"],
        "source": data["source"]["agent_id"],
        "target": data.get("target", {}).get("agent_id", ""),
        "branch": workspace.get("branch", ""),
        "head_sha": workspace.get("head_sha", ""),
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return "t2t-" + hashlib.sha256(encoded).hexdigest()[:16]


def identity(agent: str, session: str | None, platform: str | None) -> dict[str, str]:
    result = {"agent_id": agent}
    if session:
        result["session_id"] = session
    if platform:
        result["platform"] = platform
    return result


def command_create(args: argparse.Namespace) -> int:
    source_agent = args.source_agent or os.environ.get("T2T_AGENT_ID") or "unknown"
    envelope: dict[str, Any] = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "message_type": "handoff.ready",
        "handoff_id": args.handoff_id or "pending",
        "created_at": utc_now(),
        "source": identity(source_agent, args.source_session, args.source_platform),
        "task": {"id": args.task_id, "title": args.title},
        "status": args.status,
        "summary": {
            "outcomes": args.summary,
            "decisions": args.decision,
            "changes": args.change,
            "verification": args.verification,
            "risks": args.risk,
            "blockers": args.blocker,
            "next_actions": args.next_action,
        },
        "artifacts": parse_artifacts(args.artifact),
    }
    if args.target_agent:
        envelope["target"] = identity(
            args.target_agent, args.target_session, args.target_platform
        )

    snapshot = git_snapshot(args.workspace, args.base_sha) if args.workspace else None
    if snapshot:
        if args.repository:
            snapshot["repository"] = args.repository
        envelope["workspace"] = snapshot
    elif args.workspace or args.repository or args.base_sha:
        envelope["workspace"] = {
            key: value
            for key, value in {
                "path": args.workspace,
                "repository": args.repository,
                "base_sha": args.base_sha,
            }.items()
            if value
        }

    if args.preferred_transport or args.reply_to:
        envelope["routing"] = {
            key: value
            for key, value in {
                "preferred_transport": args.preferred_transport,
                "reply_to": args.reply_to,
            }.items()
            if value
        }

    if not args.handoff_id:
        envelope["handoff_id"] = deterministic_id(envelope)

    errors = validate_envelope(envelope)
    if errors:
        raise HandoffError("; ".join(errors))
    atomic_json_write(args.output, envelope)
    return 0


def compare_git(data: dict[str, Any], workspace_arg: str) -> list[str]:
    if data.get("message_type") != "handoff.ready":
        return ["Git verification applies only to handoff.ready messages"]
    recorded = data.get("workspace")
    if not isinstance(recorded, dict):
        return ["handoff has no workspace snapshot"]
    actual = git_snapshot(workspace_arg, recorded.get("base_sha"))
    if actual is None:
        return [f"{workspace_arg!r} is not an accessible Git worktree"]

    errors = []
    for key in ("head_sha", "branch"):
        expected = recorded.get(key)
        if expected and actual.get(key) != expected:
            errors.append(
                f"workspace {key} mismatch: recorded={expected!r}, actual={actual.get(key)!r}"
            )
    if recorded.get("dirty") is False and actual.get("dirty") is True:
        errors.append("workspace is dirty but handoff recorded dirty=false")
    return errors


def command_validate(args: argparse.Namespace) -> int:
    data = load_json(args.input)
    errors = validate_envelope(data)
    if args.check_git:
        errors.extend(compare_git(data, args.check_git))
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"valid {data['message_type']} {data['handoff_id']} (protocol {VERSION})"
    )
    return 0


def markdown_list(items: Iterable[str]) -> list[str]:
    values = [item for item in items if item]
    return [f"- {item}" for item in values] if values else ["- None"]


def render_ready(data: dict[str, Any]) -> str:
    summary = data.get("summary", {})
    workspace = data.get("workspace", {})
    lines = [
        f"# Handoff: {data.get('task', {}).get('title', '')}",
        "",
        f"- Handoff ID: `{data.get('handoff_id', '')}`",
        f"- Task: `{data.get('task', {}).get('id', '')}`",
        f"- Status: `{data.get('status', '')}`",
        f"- Source: `{data.get('source', {}).get('agent_id', '')}`",
    ]
    target = data.get("target", {}).get("agent_id")
    if target:
        lines.append(f"- Target: `{target}`")
    if workspace:
        lines.extend(
            [
                f"- Worktree: `{workspace.get('path', '')}`",
                f"- Branch: `{workspace.get('branch', '')}`",
                f"- HEAD: `{workspace.get('head_sha', '')}`",
                f"- Dirty: `{workspace.get('dirty', '')}`",
            ]
        )

    sections = [
        ("Outcomes", "outcomes"),
        ("Decisions", "decisions"),
        ("Changes", "changes"),
        ("Verification", "verification"),
        ("Risks", "risks"),
        ("Blockers", "blockers"),
        ("Next actions", "next_actions"),
    ]
    for title, key in sections:
        lines.extend(["", f"## {title}", "", *markdown_list(summary.get(key, []))])
    return "\n".join(lines) + "\n"


def render_ack(data: dict[str, Any]) -> str:
    lines = [
        f"# Handoff acknowledgement: {data.get('handoff_id', '')}",
        "",
        f"- Receiver: `{data.get('receiver', {}).get('agent_id', '')}`",
        f"- Disposition: `{data.get('disposition', '')}`",
        f"- Verified: `{data.get('verified', False)}`",
        "",
        "## Notes",
        "",
        *markdown_list(data.get("notes", [])),
        "",
        "## Records",
        "",
        *markdown_list(data.get("records", [])),
    ]
    return "\n".join(lines) + "\n"


def command_render(args: argparse.Namespace) -> int:
    data = load_json(args.input)
    errors = validate_envelope(data)
    if errors:
        raise HandoffError("; ".join(errors))
    output = render_ready(data) if data["message_type"] == "handoff.ready" else render_ack(data)
    if args.output == "-":
        sys.stdout.write(output)
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary.write(output)
            temp_name = temporary.name
        os.replace(temp_name, path)
    return 0


def command_ack(args: argparse.Namespace) -> int:
    handoff = load_json(args.input)
    errors = validate_envelope(handoff)
    if errors:
        raise HandoffError("cannot acknowledge invalid handoff: " + "; ".join(errors))
    if handoff.get("message_type") != "handoff.ready":
        raise HandoffError("input must be a handoff.ready message")
    acknowledgement = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "message_type": "handoff.ack",
        "handoff_id": handoff["handoff_id"],
        "received_at": utc_now(),
        "receiver": identity(
            args.receiver_agent, args.receiver_session, args.receiver_platform
        ),
        "disposition": args.disposition,
        "verified": args.verified,
        "notes": args.note,
        "records": args.record,
    }
    ack_errors = validate_envelope(acknowledgement)
    if ack_errors:
        raise HandoffError("; ".join(ack_errors))
    atomic_json_write(args.output, acknowledgement)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create a handoff.ready message")
    create.add_argument("--task-id", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--status", required=True, choices=sorted(READY_STATUSES))
    create.add_argument("--summary", action="append", required=True)
    create.add_argument("--decision", action="append", default=[])
    create.add_argument("--change", action="append", default=[])
    create.add_argument("--verification", action="append", default=[])
    create.add_argument("--risk", action="append", default=[])
    create.add_argument("--blocker", action="append", default=[])
    create.add_argument("--next-action", action="append", default=[])
    create.add_argument("--source-agent")
    create.add_argument("--source-session")
    create.add_argument("--source-platform")
    create.add_argument("--target-agent")
    create.add_argument("--target-session")
    create.add_argument("--target-platform")
    create.add_argument("--workspace")
    create.add_argument("--repository")
    create.add_argument("--base-sha")
    create.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="TYPE=LOCATION",
    )
    create.add_argument("--preferred-transport")
    create.add_argument("--reply-to")
    create.add_argument("--handoff-id")
    create.add_argument("--output", default="-")
    create.set_defaults(function=command_create)

    validate = subparsers.add_parser("validate", help="validate a handoff or ack")
    validate.add_argument("input")
    validate.add_argument(
        "--check-git",
        metavar="WORKTREE",
        help="compare recorded branch and HEAD with a local worktree",
    )
    validate.set_defaults(function=command_validate)

    render = subparsers.add_parser("render", help="render JSON as Markdown")
    render.add_argument("input")
    render.add_argument("--output", default="-")
    render.set_defaults(function=command_render)

    ack = subparsers.add_parser("ack", help="acknowledge a handoff.ready message")
    ack.add_argument("input")
    ack.add_argument("--receiver-agent", required=True)
    ack.add_argument("--receiver-session")
    ack.add_argument("--receiver-platform")
    ack.add_argument("--disposition", required=True, choices=sorted(ACK_DISPOSITIONS))
    ack.add_argument("--verified", action="store_true")
    ack.add_argument("--note", action="append", default=[])
    ack.add_argument("--record", action="append", default=[])
    ack.add_argument("--output", default="-")
    ack.set_defaults(function=command_ack)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.function(args)
    except HandoffError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

