#!/usr/bin/env python3
"""Offline Git fixtures, NOT an agent runner or a production fact collector."""
import argparse
import json
import os
from pathlib import Path
import subprocess

FIXTURE_IDS = (
    "divergent", "deletion", "wip", "artifacts", "empty", "commits",
    "special-paths", "unrelated", "unborn", "criss-cross", "net-zero-history",
)
SPECIAL_PATHS = ("space name.txt", "tab\tname.txt", "line\nname.txt", "中文.txt",
                 "-leading.txt", ":(glob)*.txt")


class Repository:
    def __init__(self, path):
        self.path = Path(path).resolve()
        # Refuse existing destinations; never overwrite a user's checkout.
        self.path.mkdir(parents=True, exist_ok=False)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update({
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "Fixture", "GIT_COMMITTER_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2001-01-01T00:00:00+0000",
            "GIT_COMMITTER_DATE": "2001-01-01T00:00:00+0000",
            "LC_ALL": "C", "TZ": "UTC",
        })
        self.git("init", "--initial-branch=main", "--template=")
        for key, value in (("core.autocrlf", "false"), ("core.filemode", "false"),
                           ("core.hooksPath", os.devnull), ("commit.gpgSign", "false"),
                           ("core.attributesFile", os.devnull), ("core.excludesFile", os.devnull)):
            self.git("config", key, value)
        self.refs = {}

    def run(self, *args, input=None, check=True):
        return subprocess.run(["git", "--no-pager", *args], cwd=self.path,
                              env=self.env, input=input, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=check)

    def git(self, *args, input=None):
        return self.run(*args, input=input).stdout

    def text(self, *args):
        return self.git(*args).decode("utf-8").strip()

    def write(self, name, content):
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))

    def commit(self, label):
        self.git("add", "--all", "--", ".")
        self.git("commit", "--allow-empty", "-m", label)
        sha = self.text("rev-parse", "HEAD")
        self.refs[label] = sha
        return sha

    def point(self, name, sha):
        self.git("update-ref", name, sha)


def build_fixture(name, path):
    if name not in FIXTURE_IDS:
        raise ValueError("unknown fixture: " + name)
    repo = Repository(path)
    if name == "unborn":
        repo.write("staged.txt", "staged\n")
        repo.git("add", "--", "staged.txt")
        repo.write("untracked.txt", "not committed\n")
        return repo
    repo.write("common.txt", "original\n")
    root = repo.commit("root")
    repo.point("refs/remotes/origin/main", root)
    repo.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    if name == "divergent":
        repo.write("main-only.txt", "main\n")
        base = repo.commit("base")
        repo.point("refs/remotes/origin/main", base)
        repo.git("checkout", "-b", "feature/payment-retry", root)
        repo.write("feature.txt", "feature\n")
        repo.commit("feature-one")
        repo.write("feature.txt", "feature\nsecond\n")
        repo.commit("target")
    elif name == "deletion":
        repo.write("fallback.txt", "fallback\n")
        base = repo.commit("base")
        repo.point("refs/remotes/origin/main", base)
        repo.git("checkout", "-b", "fix/remove-fallback")
        repo.git("rm", "--", "fallback.txt")
        repo.commit("target")
    elif name == "wip":
        repo.write(".gitignore", "ignored.txt\n.agents/handoff/\n")
        repo.commit("base")
        repo.write("common.txt", "staged replacement\n")
        repo.write("staged.txt", "staged only\n")
        repo.git("add", "--", "common.txt", "staged.txt")
        repo.write("common.txt", "original\n")
        repo.write(".gitignore", "ignored.txt\n.agents/handoff/\n# unstaged\n")
        repo.write("untracked-one.txt", "not in totals\n")
        repo.write("untracked-two.txt", "not in totals either\n")
        repo.write("ignored.txt", "ignored\n")
    elif name == "artifacts":
        repo.write("old.txt", "rename me\n")
        repo.write("one.bin", b"\0old")
        repo.write("two.bin", b"\0old")
        repo.write(".gitattributes", "generated.pb.go linguist-generated=true\n")
        base = repo.commit("base")
        repo.point("refs/remotes/origin/main", base)
        repo.git("checkout", "-b", "release")
        repo.git("mv", "--", "old.txt", "new.txt")
        repo.write("one.bin", b"\0new")
        repo.write("two.bin", b"\0newer")
        repo.write("generated.pb.go", "// generated\n" * 100)
        repo.write("package-lock.json", "lock entry\n" * 50)
        repo.commit("target")
    elif name == "commits":
        repo.write("one.txt", "one\n")
        one = repo.commit("one")
        repo.git("checkout", "-b", "side", root)
        repo.write("side.txt", "side\n")
        repo.commit("side")
        repo.git("checkout", "main")
        repo.git("merge", "--no-ff", "side", "-m", "merge")
        repo.refs["merge"] = repo.text("rev-parse", "HEAD")
        repo.refs["one"] = one
    elif name == "special-paths":
        for index, filename in enumerate(SPECIAL_PATHS):
            repo.write(filename, f"{index}\n")
        repo.commit("target")
    elif name == "unrelated":
        repo.git("checkout", "--orphan", "other")
        repo.git("rm", "-rf", "--", ".")
        repo.write("other.txt", "other root\n")
        repo.commit("other")
    elif name == "criss-cross":
        tree = repo.text("rev-parse", "HEAD^{tree}")
        def node(label, parents):
            args = ["commit-tree", tree]
            for parent in parents:
                args.extend(["-p", parent])
            sha = repo.git(*args, input=(label + "\n").encode()).decode().strip()
            repo.refs[label] = sha
            return sha
        a = node("a", [root])
        b = node("b", [root])
        left = node("left", [a, b])
        right = node("right", [b, a])
        repo.point("refs/heads/left", left)
        repo.point("refs/heads/right", right)
    elif name == "net-zero-history":
        repo.write("common.txt", "changed\n")
        repo.commit("change")
        repo.write("common.txt", "original\n")
        repo.commit("restore")
    return repo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", choices=FIXTURE_IDS)
    parser.add_argument("destination", type=Path, help="new, nonexistent directory")
    args = parser.parse_args()
    repo = build_fixture(args.fixture, args.destination)
    print(json.dumps({"fixture": args.fixture, "path": str(repo.path), "refs": repo.refs},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
