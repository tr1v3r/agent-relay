"""Validate dataset structure/linkage only; no model is invoked or graded."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from git_fixtures import FIXTURE_IDS


class Datasets(unittest.TestCase):
    def test_all_datasets(self):
        paths = sorted((ROOT / "evals").glob("*.json"))
        self.assertTrue(paths, "no evaluation datasets found")
        for path in paths:
            with self.subTest(dataset=path.name):
                data = json.loads(path.read_text(encoding="utf-8"))
                # Trigger datasets use skill-creator's query/should_trigger list.
                if isinstance(data, list):
                    self.assertTrue(data)
                    queries = set()
                    for item in data:
                        self.assertIsInstance(item, dict)
                        self.assertIsInstance(item.get("query"), str)
                        self.assertTrue(item["query"].strip())
                        self.assertIs(type(item.get("should_trigger")), bool)
                        self.assertNotIn(item["query"], queries)
                        queries.add(item["query"])
                    continue
                self.assertIsInstance(data, dict)
                self.assertEqual(data.get("skill_name"), "agent-relay")
                self.assertEqual(data.get("dataset_type", "behavior"), "behavior")
                cases = data.get("evals")
                self.assertIsInstance(cases, list)
                self.assertTrue(cases)
                ids = set()
                for item in cases:
                    self.assertIsInstance(item, dict)
                    ident = item.get("id")
                    self.assertIn(type(ident), (str, int))
                    if isinstance(ident, str):
                        self.assertTrue(ident.strip())
                    self.assertNotIn(ident, ids)
                    ids.add(ident)
                    for field in ("prompt", "expected_output"):
                        self.assertIsInstance(item.get(field), str)
                        self.assertTrue(item[field].strip())
                    self.assertIsInstance(item.get("files"), list)
                    for file in item["files"]:
                        self.assertIsInstance(file, str)
                        location = (ROOT / file).resolve()
                        self.assertTrue(location.is_relative_to(ROOT), "files must stay inside repository")
                        self.assertTrue(location.is_file(), f"missing input file: {file}")
                    self.assertIsInstance(item.get("expectations"), list)
                    self.assertTrue(item["expectations"])
                    for expectation in item["expectations"]:
                        self.assertIsInstance(expectation, str)
                        self.assertTrue(expectation.strip())
                    # Optional/null fixture means guidance-only, not executable coverage.
                    if item.get("fixture") is not None:
                        self.assertIn(item["fixture"], FIXTURE_IDS)


if __name__ == "__main__":
    unittest.main()
