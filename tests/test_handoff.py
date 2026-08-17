from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "handoff.py"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-B", str(CLI), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {result.stderr or result.stdout}"
        )
    return result


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


class AgentRelayCliTest(unittest.TestCase):
    def make_repo(self, directory: Path) -> tuple[Path, str]:
        repo = directory / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.name", "Agent Relay Test")
        git(repo, "config", "user.email", "agent-relay@example.invalid")
        (repo / "example.txt").write_text("one\n", encoding="utf-8")
        git(repo, "add", "example.txt")
        git(repo, "commit", "-qm", "initial")
        base = git(repo, "rev-parse", "HEAD")
        (repo / "example.txt").write_text("one\ntwo\n", encoding="utf-8")
        git(repo, "commit", "-qam", "change")
        return repo, base

    def create_handoff(self, directory: Path, repo: Path, base: str) -> Path:
        handoff = directory / "HANDOFF.json"
        run(
            "create",
            "--task-id",
            "TEST-001",
            "--title",
            "Test relay",
            "--status",
            "completed",
            "--source-agent",
            "worker",
            "--target-agent",
            "manager",
            "--workspace",
            str(repo),
            "--base-sha",
            base,
            "--summary",
            "Implemented the requested change",
            "--verification",
            "unit tests: passed",
            "--output",
            str(handoff),
        )
        return handoff

    def test_create_validate_render_and_ack(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            repo, base = self.make_repo(directory)
            handoff = self.create_handoff(directory, repo, base)

            ready = json.loads(handoff.read_text(encoding="utf-8"))
            self.assertEqual(ready["protocol"], "task-to-task-handoff")
            self.assertEqual(ready["message_type"], "handoff.ready")
            self.assertEqual(ready["workspace"]["head_sha"], git(repo, "rev-parse", "HEAD"))
            self.assertIn("example.txt", ready["workspace"]["changed_files"])

            valid = run("validate", str(handoff), "--check-git", str(repo))
            self.assertIn("valid handoff.ready", valid.stdout)

            rendered = run("render", str(handoff))
            self.assertIn("## Verification", rendered.stdout)
            self.assertIn("unit tests: passed", rendered.stdout)

            acknowledgement = directory / "ACK.json"
            run(
                "ack",
                str(handoff),
                "--receiver-agent",
                "manager",
                "--disposition",
                "ingested",
                "--verified",
                "--record",
                "project.md",
                "--output",
                str(acknowledgement),
            )
            ack = json.loads(acknowledgement.read_text(encoding="utf-8"))
            self.assertEqual(ack["handoff_id"], ready["handoff_id"])
            self.assertEqual(ack["disposition"], "ingested")

    def test_deterministic_id_is_stable_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            repo, base = self.make_repo(directory)
            first = self.create_handoff(directory, repo, base)
            first_id = json.loads(first.read_text(encoding="utf-8"))["handoff_id"]

            second = directory / "HANDOFF-RETRY.json"
            run(
                "create",
                "--task-id",
                "TEST-001",
                "--title",
                "Test relay",
                "--status",
                "completed",
                "--source-agent",
                "worker",
                "--target-agent",
                "manager",
                "--workspace",
                str(repo),
                "--base-sha",
                base,
                "--summary",
                "Retry of the same completed result",
                "--output",
                str(second),
            )
            second_id = json.loads(second.read_text(encoding="utf-8"))["handoff_id"]
            self.assertEqual(first_id, second_id)

    def test_git_mismatch_fails_receiver_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            repo, base = self.make_repo(directory)
            handoff = self.create_handoff(directory, repo, base)

            (repo / "later.txt").write_text("later\n", encoding="utf-8")
            git(repo, "add", "later.txt")
            git(repo, "commit", "-qm", "later")

            result = run(
                "validate", str(handoff), "--check-git", str(repo), check=False
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("head_sha mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()

