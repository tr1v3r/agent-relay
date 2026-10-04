"""Deterministic Git contracts. These tests do not execute or grade a model."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from git_fixtures import FIXTURE_IDS, SPECIAL_PATHS, build_fixture


def names(repo, *revisions, cached=False):
    args = ["diff", "--name-only", "-z", "--find-renames"]
    if cached:
        args.append("--cached")
    return set(filter(None, repo.git(*args, *revisions, "--").split(b"\0")))


def numstat(raw):
    """Read numstat -z; rename records have an empty path then old/new tokens."""
    tokens = iter(raw.split(b"\0")[:-1])
    rows = []
    for token in tokens:
        added, deleted, path = token.split(b"\t", 2)
        old = None
        if not path:
            old, path = next(tokens), next(tokens)
        rows.append((added, deleted, old, path))
    return rows


def stats(repo, *revisions):
    return numstat(repo.git("diff", "--numstat", "-z", "--find-renames", *revisions, "--"))


class GitContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agent-relay-test-")
        self.addCleanup(self.tmp.cleanup)

    def fixture(self, name):
        return build_fixture(name, Path(self.tmp.name) / name)

    def test_all_registered_fixtures_build(self):
        for name in FIXTURE_IDS:
            with self.subTest(fixture=name):
                self.fixture(name)

    def test_divergent_branch_and_endpoint_are_different(self):
        r = self.fixture("divergent")
        base, target = r.refs["base"], r.refs["target"]
        mb = r.text("merge-base", "--all", base, target)
        self.assertEqual(mb, r.refs["root"])
        self.assertEqual(names(r, mb, target), {b"feature.txt"})
        self.assertEqual(names(r, base, target), {b"feature.txt", b"main-only.txt"})
        self.assertEqual(r.git("diff", base, target), r.git("diff", base + ".." + target))
        self.assertEqual(r.git("diff", mb, target), r.git("diff", base + "..." + target))
        self.assertEqual(r.text("rev-list", "--count", base + ".." + target), "2")
        self.assertEqual(r.text("rev-list", "--count", base + "..." + target), "3")
        self.assertEqual(stats(r, mb, target), [(b"2", b"0", None, b"feature.txt")])

    def test_frozen_ids_survive_moving_ref(self):
        r = self.fixture("divergent")
        base = r.text("rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
        r.point("refs/remotes/origin/main", r.refs["target"])
        self.assertEqual(names(r, base, r.refs["target"]), {b"feature.txt", b"main-only.txt"})
        self.assertEqual(names(r, "refs/remotes/origin/main", r.refs["target"]), set())

    def test_single_commit_root_and_explicit_merge_parents(self):
        r = self.fixture("commits")
        root, one, merge = (r.refs[k] for k in ("root", "one", "merge"))
        empty = r.git("hash-object", "-t", "tree", "--stdin", input=b"").decode().strip()
        self.assertEqual(names(r, empty, root), {b"common.txt"})
        self.assertEqual(names(r, one + "^", one), {b"one.txt"})
        self.assertEqual(names(r, merge + "^1", merge), {b"side.txt"})
        self.assertEqual(names(r, merge + "^2", merge), {b"one.txt"})
        # A single commit's history is C alone, not parent..C's reachable set.
        self.assertEqual(r.text("rev-list", "--no-walk", merge), merge)
        self.assertEqual(r.text("rev-list", "--count", merge + "^1.." + merge), "2")

    def test_deletion_and_remote_default(self):
        r = self.fixture("deletion")
        self.assertEqual(r.text("symbolic-ref", "refs/remotes/origin/HEAD"), "refs/remotes/origin/main")
        self.assertEqual(stats(r, r.refs["base"], r.refs["target"]), [(b"0", b"1", None, b"fallback.txt")])

    def test_wip_layers_union_and_net_cancellation(self):
        r = self.fixture("wip")
        head = r.refs["base"]
        staged = names(r, head, cached=True)
        unstaged = names(r)
        untracked = set(filter(None, r.git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0")))
        self.assertEqual(staged, {b"common.txt", b"staged.txt"})
        self.assertEqual(unstaged, {b"common.txt", b".gitignore"})
        self.assertEqual(untracked, {b"untracked-one.txt", b"untracked-two.txt"})
        self.assertEqual(len(staged | unstaged | untracked), 5)
        self.assertEqual(names(r, head), {b"staged.txt", b".gitignore"})
        self.assertEqual(sum(int(row[0]) for row in stats(r, head)), 2)
        self.assertEqual(sum(int(row[1]) for row in stats(r, head)), 0)
        self.assertEqual(r.git("diff", "--numstat", head, "--", "common.txt"), b"")
        self.assertNotEqual(r.git("diff", "--cached", "--numstat", head, "--", "common.txt"), b"")
        self.assertEqual(r.run("check-ignore", ".agents/handoff/report.md").returncode, 0)

    def test_wip_staged_rename_then_unstaged_deletion(self):
        r = self.fixture("empty")
        r.git("mv", "--", "common.txt", "moved.txt")
        path = r.path / "moved.txt"
        self.assertEqual(path.resolve(), r.path / "moved.txt")
        path.unlink()
        staged = numstat(r.git("diff", "--cached", "--numstat", "-z", "--find-renames", "HEAD", "--"))
        unstaged = stats(r)
        self.assertEqual(staged, [(b"0", b"0", b"common.txt", b"moved.txt")])
        self.assertEqual(unstaged, [(b"0", b"1", None, b"moved.txt")])
        touched = {path for row in staged + unstaged for path in row[2:] if path is not None}
        self.assertEqual(touched, {b"common.txt", b"moved.txt"})
        self.assertEqual(stats(r, "HEAD"), [(b"0", b"1", None, b"common.txt")])
        # The unstaged deletion's old content lives in the index under the new path.
        self.assertEqual(r.git("show", ":moved.txt"), b"original\n")
        self.assertNotEqual(r.run("show", "HEAD:moved.txt", check=False).returncode, 0)

    def test_rename_binary_generated(self):
        r = self.fixture("artifacts")
        rows = stats(r, r.refs["base"], r.refs["target"])
        self.assertEqual(len(rows), 5)
        self.assertIn((b"0", b"0", b"old.txt", b"new.txt"), rows)
        binary = [row for row in rows if row[0] == b"-"]
        self.assertEqual(len(binary), 2)
        text = [row for row in rows if row[0] != b"-"]
        self.assertEqual(sum(int(row[0]) for row in text), 150)
        self.assertEqual(sum(int(row[1]) for row in text), 0)
        self.assertEqual(r.git("check-attr", "-z", "linguist-generated", "--", "generated.pb.go"),
                         b"generated.pb.go\0linguist-generated\0true\0")

    def test_nul_paths_and_literal_pathspec(self):
        r = self.fixture("special-paths")
        self.assertEqual(names(r, r.refs["root"], r.refs["target"]),
                         {name.encode() for name in SPECIAL_PATHS})
        self.assertEqual(len(stats(r, r.refs["root"], r.refs["target"])), len(SPECIAL_PATHS))
        for name in SPECIAL_PATHS:
            with self.subTest(path=name):
                raw = r.git("--literal-pathspecs", "diff", "--numstat", "-z",
                            r.refs["root"], r.refs["target"], "--", name)
                self.assertEqual(numstat(raw), [(b"1", b"0", None, name.encode())])

    def test_untracked_special_paths_and_rename_nul_record(self):
        r = self.fixture("special-paths")
        source, target = SPECIAL_PATHS[1], "renamed\nwith\ttab.txt"
        r.git("mv", "--", source, target)
        rows = numstat(r.git("diff", "--cached", "--numstat", "-z", "--find-renames", "HEAD", "--"))
        self.assertEqual(rows, [(b"0", b"0", source.encode(), target.encode())])
        r.write("untracked\nwith\ttab.txt", "untracked\n")
        self.assertEqual(r.git("ls-files", "--others", "--exclude-standard", "-z"),
                         b"untracked\nwith\ttab.txt\0")

    def test_invalid_empty_and_unborn_are_distinct(self):
        r = self.fixture("empty")
        self.assertNotEqual(r.run("rev-parse", "--verify", "missing^{commit}", check=False).returncode, 0)
        self.assertEqual(names(r, "HEAD", "HEAD"), set())
        self.assertEqual(r.text("rev-list", "--count", "HEAD..HEAD"), "0")
        unborn = self.fixture("unborn")
        self.assertNotEqual(unborn.run("rev-parse", "--verify", "HEAD^{commit}", check=False).returncode, 0)
        self.assertEqual(names(unborn, cached=True), {b"staged.txt"})

    def test_empty_tree_diff_can_have_nonempty_history(self):
        r = self.fixture("net-zero-history")
        self.assertEqual(names(r, r.refs["root"], "HEAD"), set())
        self.assertEqual(r.text("rev-list", "--count", r.refs["root"] + "..HEAD"), "2")

    def test_unrelated_snapshot_and_multiple_merge_bases(self):
        r = self.fixture("unrelated")
        result = r.run("merge-base", "--all", r.refs["root"], r.refs["other"], check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(names(r, r.refs["root"], r.refs["other"]), {b"common.txt", b"other.txt"})
        crossed = self.fixture("criss-cross")
        bases = set(crossed.text("merge-base", "--all", "left", "right").splitlines())
        self.assertEqual(bases, {crossed.refs["a"], crossed.refs["b"]})

    def test_shallow_history_is_not_proof_of_unrelated_roots(self):
        r = self.fixture("commits")
        shallow = Path(self.tmp.name) / "shallow"
        subprocess.run(["git", "-c", "protocol.file.allow=always", "clone", "--depth=1",
                        "--no-local", r.path.as_uri(), str(shallow)], env=r.env,
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def git(*args):
            return subprocess.run(["git", "-C", str(shallow), *args], env=r.env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(git("rev-parse", "--is-shallow-repository").stdout, b"true\n")
        self.assertNotEqual(git("rev-parse", "--verify", "HEAD^1^{commit}").returncode, 0)
        # Shallow traversal hides parents: this output alone cannot identify a root.
        self.assertEqual(len(git("rev-list", "--parents", "-n", "1", "HEAD").stdout.split()), 1)

    def test_fixture_refuses_existing_destination(self):
        path = Path(self.tmp.name) / "existing"
        path.mkdir()
        marker = path / "keep.txt"
        marker.write_text("preserved")
        with self.assertRaises(FileExistsError):
            build_fixture("empty", path)
        self.assertEqual(marker.read_text(), "preserved")


if __name__ == "__main__":
    unittest.main()
