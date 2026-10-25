import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location("sync", Path(__file__).with_name("sync.py"))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

class SyncTests(unittest.TestCase):
    def test_paths_and_pairing(self):
        self.assertEqual(sync.counterpart("nested/rules.en.md"), "nested/rules.tr.md")
        self.assertEqual(sync.counterpart("rules.tr.md"), "rules.en.md")
        for path in ("/tmp/a.en.md", "../a.en.md", ".github/a.en.md", "README.md"):
            self.assertFalse(sync.bilingual(path))

    def test_output_boundary(self):
        context = {"files": ["rules.en.md"]}
        result = {"files": [{"path": "rules.tr.md", "content": "Kurallar"}], "conflicts": [], "summary": "Çeviri"}
        sync.validate(result, context)
        for path in ("other.tr.md", ".github/workflows/a.yml", "../rules.tr.md"):
            result["files"][0]["path"] = path
            with self.assertRaises(AssertionError):
                sync.validate(result, context)

    def test_marker(self):
        pr = {"head": {"ref": sync.BRANCH}, "body": sync.MARKER + '\n<!-- sync-data: {"mode": "content"} -->'}
        self.assertEqual(sync.metadata(pr), {"mode": "content"})
        self.assertIsNone(sync.metadata({"body": "normal PR"}))

    def test_accepted_merge_does_not_translate_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            try:
                os.chdir(tmp)
                Path(".translation").mkdir()
                text = "dictionary"
                sha = sync.git_blob(text)
                sync.SNAPSHOT.write_text(text)
                sync.VERSION.write_text(sha)
                pr = {"merged_at": "2026-10-25", "merge_commit_sha": "accepted",
                      "head": {"ref": sync.BRANCH},
                      "body": sync.MARKER + '\n<!-- sync-data: {"mode": "content"} -->'}
                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo", "GITHUB_OUTPUT": "output"}), patch.object(sync, "pages", return_value=[pr]), patch.object(sync, "api", return_value={"content": sync.base64.b64encode(text.encode()).decode(), "sha": sha}), patch.object(sync, "git", return_value="accepted"):
                    sync.prepare()
                self.assertIn("needed=false", Path("output").read_text())
                self.assertFalse(Path(".run/context.json").exists())
            finally:
                os.chdir(old)

    def test_deleted_pairs_do_not_call_model(self):
        cases = [
            # Remove the only pair, or a pair alongside unchanged rule files.
            ("", "rules.en.md\nrules.tr.md", False),
            ("other.en.md\nother.tr.md", "rules.en.md\nrules.tr.md", False),
            # A surviving counterpart still requires review.
            ("rules.tr.md", "rules.en.md", True),
            # Real changes alongside the deleted pair still require translation.
            ("other.en.md", "rules.en.md\nrules.tr.md\nother.en.md", True),
        ]
        for files, changed, translate in cases:
            with self.subTest(files=files, changed=changed), tempfile.TemporaryDirectory() as tmp:
                old = os.getcwd()
                try:
                    os.chdir(tmp)
                    Path(".translation").mkdir()
                    text = "dictionary"
                    sha = sync.git_blob(text)
                    sync.SNAPSHOT.write_text(text)
                    sync.VERSION.write_text(sha)
                    def git(*args):
                        if args[0] == "rev-parse": return "head"
                        if args[0] == "rev-list": return "root"
                        if args[0] == "ls-files": return files
                        if args[0] == "diff": return changed
                        raise AssertionError(args)
                    source = {"content": sync.base64.b64encode(text.encode()).decode(), "sha": sha}
                    with patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo", "GITHUB_OUTPUT": "output"}), patch.object(sync, "pages", return_value=[]), patch.object(sync, "api", return_value=source), patch.object(sync, "git", side_effect=git):
                        sync.prepare()
                    result = Path("output").read_text()
                    if translate:
                        self.assertIn("translate=true", result)
                        context = json.loads(Path(".run/context.json").read_text())
                        self.assertNotIn("rules.tr.md", context["changed"])
                    else:
                        self.assertEqual(result, "needed=false\n")
                finally:
                    os.chdir(old)

    def test_prepare_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            try:
                os.chdir(tmp)
                Path(".translation").mkdir()
                sync.SNAPSHOT.write_text("test sözlük\n")
                sync.VERSION.write_text(sync.git_blob("test sözlük\n"))
                def git(*args):
                    if args[0] == "rev-parse": return "head"
                    if args[0] == "rev-list": return "root"
                    if args[0] == "ls-files": return "rules.en.md"
                    if args[0] == "diff": return "rules.en.md"
                    raise AssertionError(args)
                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "test/repo", "GITHUB_OUTPUT": "output"}), patch.object(sync, "pages", return_value=[]), patch.object(sync, "api", side_effect=sync.subprocess.CalledProcessError(1, "gh")), patch.object(sync, "git", side_effect=git):
                    sync.prepare()
                context = json.loads(Path(".run/context.json").read_text())
                self.assertTrue(context["fallback"])
                self.assertEqual(context["mode"], "content")
                self.assertIn("translate=true", Path("output").read_text())
            finally:
                os.chdir(old)

if __name__ == "__main__":
    unittest.main()
