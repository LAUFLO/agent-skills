#!/usr/bin/env python3
"""Isolated persistence and real Git/worktree regression tests."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).with_name("handover.py").resolve()
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("handover_under_test", SCRIPT)
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class HandoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="handover-v4-test-")
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        self.hooks = self.base / "empty-hooks"
        self.hooks.mkdir()

    def tearDown(self):
        self.assertEqual(self.base.parent, Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.base.name.startswith("handover-v4-test-"))
        self.temp.cleanup()

    def git(self, *args, root=None):
        result = subprocess.run(["git", "-c", f"core.hooksPath={self.hooks}", "-c", "commit.gpgsign=false",
                                 "-c", "user.name=Handover test", "-c", "user.email=handover@example.invalid",
                                 "-C", str(root or self.root), *args], capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def repo(self, commit=True):
        self.git("init", "-b", "main")
        if commit:
            (self.root / "README.md").write_text("existing project", encoding="utf-8")
            self.git("add", "README.md")
            self.git("commit", "-m", "fixture")

    def ctx(self, root=None):
        return H.context(root or self.root)

    def directory(self, feature="one", root=None):
        return H.feature_dir(self.ctx(root), feature)

    def proposal(self, root=None):
        ctx = self.ctx(root)
        state = H.fresh(ctx, "one")
        state["overview"] = "test feature"
        state["frontier"] = [{"id": "t1", "title": "implement change", "status": "implemented", "verification": {"status": "not_run"}}]
        state["next_focus"] = {"text": "check layout first", "source": "user", "basis": "explicit user instruction"}
        state["suggested_next"] = {"text": "consider keyboard support", "source": "agent", "basis": "unconfirmed improvement"}
        intake = H.inspect_project(ctx)
        state["intake"] = {"kind": intake["kind"], "basis": "checked workspace and user scope", "references": ["README.md"] if intake["kind"] == "existing-project" else []}
        return state

    def cli(self, action, payload=None, expected=None, feature="one", root=None, token=None, extra=()):
        root = root or self.root
        command = [sys.executable, "-X", "utf8", "-B", str(SCRIPT), action, "--root", str(root)]
        if feature is not None:
            command += ["--feature", feature]
        if expected is not None:
            command += ["--expected-version", str(expected)]
        if action not in {"status", "inspect"}:
            command += ["--expected-context", token or self.ctx(root)["context_token"]]
        if payload is not None:
            command += ["--input", "-"]
        process = subprocess.run(command + list(extra), input=json.dumps(payload) if payload is not None else None,
                                 capture_output=True, text=True, encoding="utf-8", timeout=30, creationflags=FLAGS)
        self.assertTrue(process.stdout.strip(), process.stderr)
        return process.returncode, json.loads(process.stdout)

    def saved(self, feature="one", root=None):
        state = self.proposal(root)
        state["feature_id"] = feature
        code, result = self.cli("save", state, 0, feature, root)
        self.assertEqual(code, 0, result)
        code, result = self.cli("status", feature=feature, root=root, extra=["--full"])
        self.assertEqual(code, 0, result)
        return result["state"]

    def test_hash_identifiers_are_not_mistaken_for_phone_numbers(self):
        identifier = "ab13800138000cd1234567890ef"
        cleaned, _ = H.C.redact({"repository_id": identifier, "phone": "13800138000"})
        self.assertEqual(cleaned["repository_id"], identifier)
        self.assertEqual(cleaned["phone"], "<REDACTED>")

    def snapshot(self, directory=None):
        directory = directory or Path(self.ctx()["storage_root"])
        return {str(path.relative_to(directory)): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in directory.rglob("*") if path.is_file()} if directory.exists() else {}

    def legacy(self, schema=1):
        base = self.root / H.LEGACY_LOCAL
        base.mkdir(parents=True, exist_ok=True)
        state = {"version": 7, "phase": 2, "frontier": [{"id": "old", "content": "previous completion", "status": "terminal"}],
                 "gates": [], "lessons": [{"content": "old lesson"}], "next_focus": "deploy next", "custom": {"keep": 42}}
        if schema == 2:
            state = H.C.migrate_legacy(state)
        (base / "state.json").write_text(json.dumps(state), encoding="utf-8")
        return base

    def import_legacy(self):
        report = self.cli("status", extra=["--full", "--legacy"])[1]["legacy"]
        state = report["state"]
        state["intake"] = {"kind": "legacy-import", "basis": "reviewed legacy scope", "references": list(report["files"].values())}
        return self.cli("adopt", state, 0, extra=["--source-signature", report["signature"]])

    def test_empty_startup_is_read_only(self):
        code, report = self.cli("status", extra=["--full"])
        self.assertEqual(code, 0, report)
        self.assertFalse(report["exists"])
        self.assertFalse((self.root / ".handover").exists())

    def test_fresh_process_resumes_same_feature_across_sessions(self):
        state = self.saved()
        before = self.snapshot()
        self.assertEqual(self.cli("status", extra=["--full"])[1]["state"], state)
        self.assertEqual(self.cli("save", state, 1, extra=["--session-id", "another-chat"])[1]["action"], "unchanged")
        self.assertEqual(before, self.snapshot())

    def test_user_plan_and_suggestion_cannot_be_confused(self):
        state = self.saved()
        state["next_focus"]["source"] = "agent"
        before = self.snapshot()
        self.assertEqual(self.cli("save", state, 1)[0], 2)
        self.assertEqual(before, self.snapshot())
        state["next_focus"] = {"text": "fix payment first", "source": "user", "basis": "new user instruction"}
        self.assertEqual(self.cli("save", state, 1)[0], 0)
        restored = self.cli("status", extra=["--full"])[1]["state"]
        self.assertEqual(restored["next_focus"]["text"], "fix payment first")
        self.assertEqual(restored["suggested_next"]["source"], "agent")

    def test_verification_requires_proof_and_is_context_bound(self):
        state = self.proposal()
        todo = state["frontier"][0]
        todo["status"] = "verified"
        self.assertEqual(self.cli("save", state, 0)[0], 2)
        todo["verification"] = {"status": "passed", "method": "manual inspection", "evidence": ["checked.txt"]}
        (self.root / "checked.txt").write_text("passed", encoding="utf-8")
        state["intake"] = {"kind": "existing-project", "basis": "checked fixture", "references": ["checked.txt"]}
        self.assertEqual(self.cli("save", state, 0)[0], 0)
        restored = self.cli("status", extra=["--full"])[1]["state"]
        self.assertEqual(restored["frontier"][0]["verification"]["checked_context"], self.ctx()["context_token"])

    def test_two_features_on_same_branch_have_independent_revisions(self):
        self.repo()
        first = self.saved("login")
        second = self.saved("payment")
        self.assertEqual(first["version"], second["version"])
        self.assertNotEqual(self.directory("login"), self.directory("payment"))
        report = self.cli("status", feature=None, extra=["--full"])[1]
        self.assertNotIn("state", report)
        self.assertEqual({item["feature_id"] for item in report["available_features"]}, {"login", "payment"})

    def test_branch_switch_rejects_old_context_and_separates_state(self):
        self.repo()
        original = self.saved()
        old = self.ctx()
        self.git("switch", "-c", "feature/payment")
        report = self.cli("status", extra=["--full"])[1]
        self.assertFalse(report["exists"])
        self.assertEqual(self.cli("save", original, 0, token=old["context_token"])[0], 7)
        self.saved()
        self.git("switch", "main")
        self.assertEqual(self.cli("status", extra=["--full"])[1]["state"], original)

    def test_switch_after_lock_check_is_detected_before_state_commit(self):
        self.repo()
        state = self.saved()
        ctx = self.ctx()
        original_bytes = (self.directory() / "state.json").read_bytes()
        original_check = H.assert_context
        calls = 0
        def switch_then_check(current, expected):
            nonlocal calls
            calls += 1
            if calls == 3:
                self.git("switch", "-c", "other")
            return original_check(current, expected)
        state["overview"] = "must not overwrite main"
        with patch.object(H, "assert_context", side_effect=switch_then_check):
            with self.assertRaises(H.C.HandoverError) as raised:
                H.save_feature(ctx, "one", state, 1, ctx["context_token"])
        self.assertEqual(raised.exception.code, 7)
        self.git("switch", "main")
        self.assertEqual((self.directory() / "state.json").read_bytes(), original_bytes)

    def test_head_change_requires_refresh_and_preserves_historical_proof(self):
        self.repo()
        state = self.proposal()
        (self.root / "checked.txt").write_text("manual check passed", encoding="utf-8")
        state["frontier"][0]["status"] = "verified"
        state["frontier"][0]["verification"] = {"status": "passed", "method": "manual review", "evidence": ["checked.txt"]}
        self.assertEqual(self.cli("save", state, 0)[0], 0)
        state = self.cli("status", extra=["--full"])[1]["state"]
        old = self.ctx()
        self.git("commit", "--allow-empty", "-m", "next commit")
        self.assertEqual(self.cli("save", state, 1, token=old["context_token"])[0], 7)
        report = self.cli("status", extra=["--full"])[1]
        self.assertTrue(report["head_changed_since_save"])
        state["overview"] = "record latest work"
        self.assertEqual(self.cli("save", state, 1)[0], 0)
        restored = self.cli("status", extra=["--full"])[1]["state"]
        self.assertEqual(restored["frontier"][0]["verification"]["checked_head"], old["head"])

    def test_detached_head_has_its_own_context(self):
        self.repo()
        original = self.saved()
        self.git("checkout", "--detach", "HEAD")
        report = self.cli("status", extra=["--full"])[1]
        self.assertIsNone(report["branch_ref"])
        self.assertFalse(report["exists"])
        self.saved()
        self.git("switch", "main")
        self.assertEqual(self.cli("status", extra=["--full"])[1]["state"], original)

    def test_worktrees_share_project_facts_and_isolate_feature_progress(self):
        self.repo()
        other = self.base / "payment-worktree"
        self.git("worktree", "add", "-b", "feature/payment", str(other))
        main_ctx, other_ctx = self.ctx(), self.ctx(other)
        self.assertEqual(main_ctx["storage_root"], other_ctx["storage_root"])
        self.assertNotEqual(main_ctx["identity"]["workspace_id"], other_ctx["identity"]["workspace_id"])
        self.saved("one")
        self.saved("one", other)
        shared = {"overview": "shared architecture", "facts": [{"id": "f1", "content": "project convention", "source": "observed", "basis": "read project docs", "references": ["README.md"]}]}
        self.assertEqual(self.cli("project-save", shared, 0, feature=None)[0], 0)
        report = self.cli("status", root=other, extra=["--full"])[1]
        self.assertEqual(report["project"]["record"]["overview"], "shared architecture")
        self.assertEqual(len(report["available_features"]), 1)
        self.assertEqual(len(self.cli("status", root=other, extra=["--all-contexts"])[1]["available_features"]), 2)

    def test_explicit_cross_worktree_resume_preserves_source_context(self):
        self.repo()
        self.saved("login")
        source = self.directory("login") / "state.json"
        original = source.read_bytes()
        other = self.base / "resume"
        self.git("worktree", "add", "-b", "resume", str(other))
        relative = str(source.relative_to(Path(self.ctx()["storage_root"])))
        report = self.cli("status", feature="login", root=other, extra=["--full", "--legacy", "--source-context", relative])[1]
        self.assertFalse(report["exists"])
        state = report["legacy"]["state"]
        state["intake"] = {"kind": "legacy-import", "basis": "user explicitly requested this feature in another worktree", "references": [str(source)]}
        code, result = self.cli("adopt", state, 0, feature="login", root=other,
                                extra=["--source-context", relative, "--source-signature", report["legacy"]["signature"]])
        self.assertEqual(code, 0, result)
        imported = self.cli("status", feature="login", root=other, extra=["--full"])[1]["state"]
        self.assertEqual(imported["imported_from"]["kind"], "context-record")
        self.assertEqual(imported["frontier"][0]["verification"]["origin"], "context-import")
        self.assertEqual(source.read_bytes(), original)

    def test_shared_project_writers_from_worktrees_compete_on_one_revision(self):
        self.repo()
        other = self.base / "other"
        self.git("worktree", "add", "-b", "other", str(other))
        processes = []
        try:
            for root, name in [(self.root, "A"), (other, "B")]:
                command = [sys.executable, "-X", "utf8", "-B", str(SCRIPT), "project-save", "--root", str(root),
                           "--expected-version", "0", "--expected-context", self.ctx(root)["context_token"], "--input", "-"]
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, encoding="utf-8", creationflags=FLAGS)
                process.stdin.write(json.dumps({"overview": name, "facts": []}))
                process.stdin.close()
                process.stdin = None
                processes.append(process)
            outputs = [process.communicate(timeout=30) for process in processes]
            self.assertEqual(sorted(process.returncode for process in processes), [0, 3], outputs)
            self.assertEqual(self.cli("status", root=other)[1]["project"]["version"], 1)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def test_copied_foreign_branch_state_is_not_silently_rebound(self):
        self.repo()
        self.saved()
        original = (self.directory() / "state.json").read_bytes()
        self.git("switch", "-c", "other")
        destination = self.directory()
        destination.mkdir(parents=True)
        (destination / "state.json").write_bytes(original)
        self.assertEqual(self.cli("status", extra=["--full"])[0], 7)
        self.assertEqual((destination / "state.json").read_bytes(), original)

    def test_corrupt_v3_state_is_not_overwritten(self):
        self.saved()
        target = self.directory() / "state.json"
        for raw in [b"{broken", b'{"schema_version":99,"version":1}']:
            target.write_bytes(raw)
            self.assertEqual(self.cli("save", self.proposal(), 1)[0], 2)
            self.assertEqual(target.read_bytes(), raw)

    def test_project_summary_repair_preserves_project_revision(self):
        self.assertEqual(self.cli("project-save", {"overview": "shared facts", "facts": []}, 0, feature=None)[0], 0)
        directory = Path(self.ctx()["storage_root"])
        original = (directory / "project.json").read_bytes()
        (directory / "project_summary.md").write_text("outdated", encoding="utf-8")
        self.assertEqual(self.cli("project-repair", expected=1, feature=None)[0], 0)
        self.assertEqual((directory / "project.json").read_bytes(), original)

    def test_tracked_legacy_file_in_new_worktree_requires_review(self):
        self.repo()
        self.legacy(2)
        self.git("add", ".opencode/handover/state.json")
        self.git("commit", "-m", "legacy fixture")
        other = self.base / "other"
        self.git("worktree", "add", "-b", "other", str(other))
        report = self.cli("status", root=other)[1]
        self.assertEqual(report["legacy"]["kind"], "legacy-state")
        self.assertFalse(report["exists"])
        self.assertEqual(self.cli("save", self.proposal(other), 0, root=other)[0], 8)

    def test_new_git_repository_without_commits_can_start(self):
        self.repo(commit=False)
        self.assertIsNone(self.ctx()["head"])
        self.assertEqual(self.ctx()["branch_ref"], "refs/heads/main")
        self.saved()

    def test_old_project_intake_requires_existing_evidence(self):
        (self.root / "README.md").write_text("mature codebase", encoding="utf-8")
        inspection = self.cli("inspect", feature=None)[1]["inspection"]
        self.assertEqual(inspection["kind"], "existing-project")
        state = self.proposal()
        state["intake"]["kind"] = "new-project"
        self.assertEqual(self.cli("save", state, 0)[0], 8)
        state["intake"]["kind"], state["intake"]["references"] = "existing-project", []
        self.assertEqual(self.cli("save", state, 0)[0], 2)
        state["intake"]["references"] = ["README.md"]
        self.assertEqual(self.cli("save", state, 0)[0], 0)
        self.assertEqual((self.root / "README.md").read_text(encoding="utf-8"), "mature codebase")

    def test_v1_import_is_conservative_and_preserves_original(self):
        base = self.legacy()
        original = (base / "state.json").read_bytes()
        report = self.cli("status", extra=["--legacy", "--full"])[1]
        self.assertFalse(report["exists"])
        self.assertIsNone(report["legacy"]["state"]["next_focus"])
        self.assertEqual(report["legacy"]["state"]["frontier"][0]["status"], "implemented")
        self.assertEqual(self.import_legacy()[0], 0)
        self.assertEqual((base / "state.json").read_bytes(), original)
        imported = self.cli("status", extra=["--full"])[1]["state"]
        self.assertEqual(imported["custom"], {"keep": 42})
        self.assertEqual(imported["version"], 1)
        self.assertEqual(imported["suggested_next"]["source"], "legacy")
        self.assertEqual(imported["frontier"][0]["verification"]["origin"], "legacy")

    def test_v2_import_keeps_extra_fields_and_original(self):
        base = self.legacy(2)
        original = (base / "state.json").read_bytes()
        self.assertEqual(self.import_legacy()[0], 0)
        self.assertEqual((base / "state.json").read_bytes(), original)
        self.assertEqual(self.cli("status", extra=["--full"])[1]["state"]["custom"], {"keep": 42})

    def test_orphan_summaries_are_preserved_until_reviewed_recovery(self):
        base = self.root / H.LEGACY_LOCAL
        base.mkdir(parents=True)
        source = base / "boot-packet.md"
        source.write_text("historical summary with uncertain progress", encoding="utf-8")
        report = self.cli("status", extra=["--legacy", "--full"])[1]
        self.assertEqual(report["legacy"]["kind"], "orphan-summaries")
        self.assertEqual(self.cli("save", self.proposal(), 0)[0], 8)
        state = self.proposal()
        state["intake"] = {"kind": "summary-recovery", "basis": "reviewed current code and summary; no invented tests", "references": [str(source)]}
        code, result = self.cli("adopt", state, 0, extra=["--source-signature", report["legacy"]["signature"]])
        self.assertEqual(code, 0, result)
        self.assertEqual(source.read_text(encoding="utf-8"), "historical summary with uncertain progress")

    def test_changed_legacy_source_is_not_imported_from_old_signature(self):
        base = self.legacy()
        report = self.cli("status", extra=["--legacy", "--full"])[1]["legacy"]
        state = report["state"]
        state["intake"] = {"kind": "legacy-import", "basis": "reviewed old record", "references": ["state.json"]}
        with (base / "state.json").open("a", encoding="utf-8") as stream:
            stream.write(" ")
        self.assertEqual(self.cli("adopt", state, 0, extra=["--source-signature", report["signature"]])[0], 8)
        self.assertFalse((self.directory() / "state.json").exists())

    def test_corrupt_or_future_legacy_records_are_not_reset(self):
        base = self.root / H.LEGACY_LOCAL
        base.mkdir(parents=True)
        for data in ['{bad', '{"schema_version":99,"version":1}', '{"version":true}']:
            (base / "state.json").write_text(data, encoding="utf-8")
            report = self.cli("status")[1]["legacy"]
            self.assertEqual(report["kind"], "invalid-legacy-state")
            self.assertEqual(self.cli("adopt", self.proposal(), 0, extra=["--source-signature", report["signature"]])[0], 8)
            self.assertEqual((base / "state.json").read_text(encoding="utf-8"), data)

    def test_initializing_git_after_non_git_progress_has_reviewed_import(self):
        self.saved()
        old_dir = self.directory()
        old_bytes = (old_dir / "state.json").read_bytes()
        self.repo()
        report = self.cli("status", extra=["--legacy", "--full"])[1]
        self.assertEqual(report["legacy"]["kind"], "local-v4")
        self.assertFalse(report["exists"])
        state = report["legacy"]["state"]
        state["intake"] = {"kind": "legacy-import", "basis": "same project initialized Git", "references": [str(old_dir)]}
        code, result = self.cli("adopt", state, 0, extra=["--source-signature", report["legacy"]["signature"]])
        self.assertEqual(code, 0, result)
        archive = Path(result["entry"]["archived_entry"])
        old_relative = old_dir.relative_to(self.root / ".handover")
        self.assertEqual((archive / old_relative / "state.json").read_bytes(), old_bytes)

    def test_project_modes_prevent_writes_including_import_and_repair(self):
        state = self.saved()
        config = self.root / H.LOCAL / "config.json"
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text('{"mode":"restore-only"}', encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(self.cli("status", extra=["--full"])[1]["state"], state)
        self.assertEqual(self.cli("save", state, 1)[0], 4)
        self.assertEqual(self.cli("repair", expected=1)[0], 4)
        self.assertEqual(self.cli("project-save", {"overview": "x", "facts": []}, 0, feature=None)[0], 4)
        self.assertEqual(self.snapshot(), before)
        config.write_text('{"mode":"off"}', encoding="utf-8")
        self.assertNotIn("state", self.cli("status", extra=["--full"])[1])

    def test_shared_facts_reject_agent_guesses_and_feature_progress(self):
        bad = {"overview": "x", "facts": [{"id": "x", "content": "guess", "source": "agent", "basis": "guess", "references": ["x"]}]}
        self.assertEqual(self.cli("project-save", bad, 0, feature=None)[0], 2)
        bad = {"overview": "x", "facts": [], "next_focus": None}
        self.assertEqual(self.cli("project-save", bad, 0, feature=None)[0], 2)

    def test_stale_projections_repair_without_state_revision(self):
        self.saved()
        directory = self.directory()
        original = (directory / "state.json").read_bytes()
        with (directory / "boot-packet.md").open("a", encoding="utf-8") as stream:
            stream.write("stale")
        (directory / "feature_summary.md").unlink()
        before = self.snapshot()
        report = self.cli("status")[1]
        self.assertEqual(set(report["projections"].values()), {"stale", "missing"})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.cli("repair", expected=1)[0], 0)
        self.assertEqual((directory / "state.json").read_bytes(), original)

    def test_atomic_failure_preserves_last_good_state(self):
        state = self.saved()
        before = self.snapshot()
        state["overview"] = "new change"
        original = H.os.replace
        def fail_replace(source, destination):
            if Path(destination).name == "state.json":
                raise OSError("simulated failure")
            return original(source, destination)
        ctx = self.ctx()
        with patch.object(H.os, "replace", side_effect=fail_replace):
            with self.assertRaises(OSError):
                H.save_feature(ctx, "one", state, 1, ctx["context_token"])
        self.assertEqual(self.snapshot(), before)

    def test_projection_failure_reports_commit_and_is_repairable(self):
        ctx, state = self.ctx(), self.proposal()
        original = H.atomic
        def fail_projection(directory, name, content):
            if name == "boot-packet.md":
                raise OSError("simulated summary failure")
            return original(directory, name, content)
        with patch.object(H, "atomic", side_effect=fail_projection):
            with self.assertRaises(H.C.HandoverError) as raised:
                H.save_feature(ctx, "one", state, 0, ctx["context_token"])
        self.assertTrue(raised.exception.details["committed"])
        self.assertEqual(self.cli("repair", expected=1)[0], 0)

    def test_redaction_in_state_and_import_snapshot(self):
        base = self.legacy(2)
        state = json.loads((base / "state.json").read_text(encoding="utf-8"))
        state["password"] = "synthetic-secret"
        state["custom_email"] = "person@example.invalid"
        (base / "state.json").write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(self.import_legacy()[0], 0)
        for path in self.directory().rglob("*"):
            if path.is_file():
                self.assertNotIn(b"synthetic-secret", path.read_bytes())
                self.assertNotIn(b"person@example.invalid", path.read_bytes())
        self.assertIn("synthetic-secret", (base / "state.json").read_text(encoding="utf-8"))

    def test_parallel_writers_cannot_overwrite_one_feature_revision(self):
        state, processes = self.saved(), []
        try:
            for name in ["chat A", "chat B"]:
                proposal = copy.deepcopy(state)
                proposal["overview"] = name
                command = [sys.executable, "-X", "utf8", "-B", str(SCRIPT), "save", "--root", str(self.root), "--feature", "one",
                           "--expected-version", "1", "--expected-context", self.ctx()["context_token"], "--input", "-"]
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, encoding="utf-8", creationflags=FLAGS)
                process.stdin.write(json.dumps(proposal))
                process.stdin.close()
                process.stdin = None
                processes.append(process)
            results = [process.communicate(timeout=30) for process in processes]
            self.assertEqual(sorted(process.returncode for process in processes), [0, 3], results)
            self.assertEqual(self.cli("status")[1]["version"], 2)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def test_lock_exclusion_and_release_when_holder_is_killed(self):
        state = self.saved()
        helper = "import sys;sys.path.insert(0,sys.argv[1]);import handover as h\nwith h.locked(h.Path(sys.argv[2])):\n print('locked',flush=True)\n sys.stdin.read()\n"
        process = subprocess.Popen([sys.executable, "-X", "utf8", "-B", "-c", helper, str(SCRIPT.parent), str(self.directory())],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", creationflags=FLAGS)
        try:
            self.assertEqual(process.stdout.readline().strip(), "locked")
            state["overview"] = "after lock"
            self.assertEqual(self.cli("save", state, 1, extra=["--lock-timeout", "0.1"])[0], 6)
        finally:
            process.kill()
            process.communicate(timeout=5)
        self.assertEqual(self.cli("save", state, 1)[0], 0)

    def test_foreign_identity_or_feature_payload_is_rejected(self):
        state = self.saved()
        self.assertEqual(self.cli("save", state, 0, feature="other")[0], 7)
        state["identity"]["workspace_id"] = "foreign"
        self.assertEqual(self.cli("save", state, 1)[0], 7)

    def test_boot_budget_preserves_user_plan_and_suggestion_labels(self):
        state = self.proposal()
        state["lessons"] = [{"id": str(index), "content": "long lesson " * 100, "category": "engineering", "source": "observed"} for index in range(10)]
        self.assertEqual(self.cli("save", state, 0)[0], 0)
        body = (self.directory() / "boot-packet.md").read_text(encoding="utf-8").split("\n", 1)[1]
        self.assertLessEqual(len(body.rstrip("\n")), 500)
        self.assertIn("用户确定的下一步", body)
        self.assertIn("待确认建议（不代表授权）", body)

    def verified(self, feature="login", root=None):
        root = root or self.root
        proof = root / (feature + "-checked.txt")
        proof.write_text("manual check passed", encoding="utf-8")
        state = self.proposal(root)
        state["feature_id"], state["next_focus"] = feature, None
        state["intake"]["references"] = [proof.name]
        state["frontier"][0]["status"] = "verified"
        state["frontier"][0]["verification"] = {"status": "passed", "method": "manual review", "evidence": [proof.name]}
        code, result = self.cli("save", state, 0, feature=feature, root=root)
        self.assertEqual(code, 0, result)
        return self.cli("status", feature=feature, root=root, extra=["--full"])[1]["state"]

    def progress(self, root=None):
        code, report = self.cli("status", feature=None, root=root, extra=["--full"])
        self.assertEqual(code, 0, report)
        return report["progress"]["record"]

    def legacy_store(self, git_repo=True):
        if git_repo:
            self.repo()
        ctx = self.ctx()
        base = Path(ctx["git_common_root"]) / "codex-handover" if git_repo else self.root / H.LEGACY_LOCAL / "v3"
        base.mkdir(parents=True)
        (base / "repository.json").write_text(json.dumps({"schema_version": 3, "repository_id": ctx["identity"]["repository_id"]}), encoding="utf-8")
        for feature in ("login", "payment"):
            state = self.proposal()
            state.update(feature_id=feature, version=1, updated_at="2026-11-17T00:00:00+00:00", custom={"keep": 42})
            state["recorded_context"] = {key: ctx[key] for key in ("workspace_root", "branch_ref", "head", "context_token")}
            identity = ctx["identity"]
            directory = base / "contexts" / identity["workspace_id"] / H.C.digest(identity["branch_key"])[:24] / H.C.digest(feature)[:24]
            directory.mkdir(parents=True)
            (directory / "state.json").write_text(json.dumps(state), encoding="utf-8")
        project = H.load_project(ctx)[0]
        project.update(version=1, overview="legacy project", custom={"keep": True})
        (base / "project.json").write_text(json.dumps(project), encoding="utf-8")
        return base

    def test_grouped_files_live_directly_under_neutral_entry(self):
        self.saved("login")
        directory = self.directory("login")
        self.assertEqual(directory.parent.name, "login")
        self.assertEqual(directory.parent.parent.name, "features")
        self.assertEqual(directory.parent.parent.parent, self.root / ".handover")
        for name in ("state.json", "boot-packet.md", "feature_summary.md"):
            self.assertTrue((directory / name).exists())
        self.assertTrue((self.root / ".handover/project_summary.md").exists())
        self.assertFalse((self.root / ".opencode").exists())

    def test_project_overview_combines_A_and_B_features(self):
        self.verified("login")
        state = self.proposal()
        state["feature_id"] = "payment"
        state["frontier"][0].update(status="blocked", reason="waiting for payment API")
        self.assertEqual(self.cli("save", state, 0, feature="payment", extra=["--agent", "opencode", "--session-id", "chat-B"])[0], 0)
        result = self.progress()
        rows = {row["feature_id"]: row for row in result["features"]}
        self.assertEqual(rows["login"]["status"], "complete")
        self.assertEqual(rows["payment"]["status"], "blocked")
        self.assertEqual(result["totals"]["known_features"], 2)
        summary = (self.root / ".handover/project_summary.md").read_text(encoding="utf-8")
        self.assertIn("login", summary)
        self.assertIn("payment", summary)
        self.assertIn("waiting for payment API", summary)

    def test_switching_agents_or_chats_does_not_duplicate_feature(self):
        state = self.saved("login")
        state["overview"] = "continued in another chat"
        self.assertEqual(self.cli("save", state, 1, feature="login", extra=["--agent", "claude-code", "--session-id", "chat-C"])[0], 0)
        result = self.progress()
        self.assertEqual(result["totals"]["known_features"], 1)
        self.assertEqual(result["totals"]["contexts"], 1)
        self.assertEqual(result["features"][0]["contexts"][0]["last_agent"], "claude-code")

    def test_user_remaining_plan_prevents_automatic_feature_completion(self):
        state = self.verified()
        state["next_focus"] = {"text": "also add login recovery", "source": "user", "basis": "user extended this feature"}
        self.assertEqual(self.cli("save", state, 1, feature="login")[0], 0)
        self.assertEqual(self.progress()["features"][0]["status"], "in_progress")

    def test_confirmed_plan_includes_unstarted_features_and_milestones(self):
        self.verified("login")
        project = {"overview": "release plan", "facts": [], "scope_complete": True,
                   "features": [{"id": "login", "title": "Login"}, {"id": "payment", "title": "Payment"}],
                   "goals": [{"id": "g1", "title": "Ship a usable product"}],
                   "milestones": [{"id": "m1", "title": "First release", "feature_ids": ["login", "payment"]}]}
        self.assertEqual(self.cli("project-save", project, 0, feature=None)[0], 0)
        result = self.progress()
        self.assertEqual(result["totals"]["completion_ratio"], 0.5)
        self.assertEqual(result["milestones"][0]["completed"], 1)
        rows = {row["feature_id"]: row for row in result["features"]}
        self.assertEqual(rows["payment"]["status"], "pending")

    def test_unknown_project_scope_has_no_invented_percentage(self):
        self.verified()
        result = self.progress()
        self.assertEqual(result["totals"]["completed_features"], 1)
        self.assertIsNone(result["totals"]["completion_ratio"])
        self.assertFalse(result["totals"]["scope_complete"])

    def test_multiple_contexts_count_once_and_require_reconciliation(self):
        self.repo()
        other = self.base / "parallel"
        self.git("worktree", "add", "-b", "parallel", str(other))
        self.saved("login")
        self.saved("login", other)
        result = self.progress()
        self.assertEqual(result["totals"]["known_features"], 1)
        self.assertEqual(result["totals"]["contexts"], 2)
        self.assertEqual(result["features"][0]["status"], "needs_reconciliation")
        project = {"overview": "selected integration context", "facts": [],
                   "features": [{"id": "login", "title": "Login", "primary_context": H.P.context_id(H.api(), self.ctx()["identity"])}]}
        self.assertEqual(self.cli("project-save", project, 0, feature=None)[0], 0)
        self.assertEqual(self.progress()["features"][0]["status"], "needs_verification")

    def test_merge_is_separate_from_branch_verification(self):
        self.repo()
        self.git("switch", "-c", "feature/login")
        (self.root / "login.txt").write_text("login implemented", encoding="utf-8")
        self.git("add", "login.txt")
        self.git("commit", "-m", "login feature")
        state = self.proposal()
        state.update(feature_id="login", next_focus=None)
        state["frontier"][0]["status"] = "verified"
        state["frontier"][0]["verification"] = {"status": "passed", "method": "checked committed fixture", "evidence": ["git:" + self.ctx()["head"]]}
        self.assertEqual(self.cli("save", state, 0, feature="login")[0], 0)
        project = {"overview": "merge before completion", "facts": [], "scope_complete": True,
                   "features": [{"id": "login", "title": "Login", "target_branch": "main"}]}
        self.assertEqual(self.cli("project-save", project, 0, feature=None)[0], 0)
        self.assertEqual(self.progress()["features"][0]["status"], "awaiting_merge")
        self.git("switch", "main")
        self.git("merge", "--ff-only", "feature/login")
        self.assertEqual(self.cli("status", feature=None)[1]["progress"]["status"], "stale")
        state_bytes = (H.feature_dir(H.context(self.root), "login") / "state.json")
        self.assertEqual(self.cli("refresh", feature=None)[0], 0)
        result = self.progress()
        self.assertEqual(result["features"][0]["status"], "complete")
        self.assertEqual(result["features"][0]["integration"], "merged")

    def test_uncommitted_work_is_not_reported_as_merged(self):
        self.repo()
        state = self.verified("login")
        project = {"overview": "requires integration", "facts": [],
                   "features": [{"id": "login", "title": "Login", "target_branch": "main"}]}
        self.assertEqual(self.cli("project-save", project, 0, feature=None)[0], 0)
        row = self.progress()["features"][0]
        self.assertEqual(row["integration"], "uncommitted")
        self.assertEqual(row["status"], "awaiting_merge")

    def test_user_acceptance_is_only_required_when_explicitly_configured(self):
        state = self.verified()
        project = {"overview": "user acceptance required", "facts": [],
                   "features": [{"id": "login", "title": "Login", "completion": {"require_acceptance": True}}]}
        self.assertEqual(self.cli("project-save", project, 0, feature=None)[0], 0)
        self.assertEqual(self.progress()["features"][0]["status"], "awaiting_acceptance")
        state["acceptance"] = {"status": "accepted", "source": "user", "basis": "user accepted this feature"}
        self.assertEqual(self.cli("save", state, 1, feature="login")[0], 0)
        self.assertEqual(self.progress()["features"][0]["status"], "complete")

    def test_stale_total_can_be_rebuilt_without_changing_feature(self):
        state = self.saved()
        ctx = self.ctx()
        state["overview"] = "committed before overview refresh"
        H._save_feature(ctx, "one", state, 1, ctx["context_token"])
        directory = self.directory()
        before = (directory / "state.json").read_bytes()
        self.assertEqual(self.cli("status", feature=None)[1]["progress"]["status"], "stale")
        self.assertEqual(self.cli("refresh", feature=None)[0], 0)
        self.assertEqual((directory / "state.json").read_bytes(), before)
        self.assertEqual(self.cli("status", feature=None)[1]["progress"]["status"], "current")

    def test_overview_failure_reports_fact_commit_and_can_recover(self):
        ctx, state = self.ctx(), self.proposal()
        with patch.object(H.P, "refresh", side_effect=OSError("simulated overview failure")):
            with self.assertRaises(H.C.HandoverError) as raised:
                H.save_feature(ctx, "one", state, 0, ctx["context_token"])
        self.assertTrue(raised.exception.details["committed"])
        self.assertEqual(self.cli("status")[1]["version"], 1)
        self.assertEqual(self.cli("refresh", feature=None)[0], 0)
        self.assertEqual(self.progress()["totals"]["known_features"], 1)

    def test_damaged_overview_does_not_destroy_feature_facts(self):
        self.saved()
        state_bytes = (self.directory() / "state.json").read_bytes()
        (self.root / ".handover/progress.json").write_text("{bad", encoding="utf-8")
        self.assertEqual(self.cli("status", feature=None)[1]["progress"]["status"], "stale")
        self.assertEqual(self.cli("refresh", feature=None)[0], 0)
        self.assertEqual((self.directory() / "state.json").read_bytes(), state_bytes)

    def test_invalid_feature_is_reported_and_prevents_complete_percentage(self):
        self.verified()
        project = {"overview": "complete plan", "facts": [], "scope_complete": True,
                   "features": [{"id": "login", "title": "Login"}]}
        self.assertEqual(self.cli("project-save", project, 0, feature=None)[0], 0)
        (self.directory("login") / "state.json").write_text("{bad", encoding="utf-8")
        self.assertEqual(self.cli("refresh", feature=None)[0], 0)
        result = self.progress()
        self.assertEqual(result["totals"]["invalid_records"], 1)
        self.assertIsNone(result["totals"]["completion_ratio"])

    def test_parallel_different_features_both_reach_total_progress(self):
        processes = []
        try:
            for feature in ("login", "payment"):
                state = self.proposal()
                state["feature_id"] = feature
                command = [sys.executable, "-X", "utf8", "-B", str(SCRIPT), "save", "--root", str(self.root),
                           "--feature", feature, "--expected-version", "0", "--expected-context", self.ctx()["context_token"], "--input", "-"]
                process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, encoding="utf-8", creationflags=FLAGS)
                process.stdin.write(json.dumps(state))
                process.stdin.close()
                process.stdin = None
                processes.append(process)
            outputs = [process.communicate(timeout=30) for process in processes]
            self.assertEqual([process.returncode for process in processes], [0, 0], outputs)
            self.assertEqual(self.progress()["totals"]["known_features"], 2)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def test_git_entry_points_to_shared_neutral_store_and_is_locally_ignored(self):
        self.repo()
        self.saved("login")
        entry = self.root / ".handover"
        self.assertEqual(entry.resolve(), Path(self.ctx()["git_common_root"]) / ".handover")
        self.assertEqual(self.git("status", "--porcelain"), "")
        other = self.base / "entry-worktree"
        self.git("worktree", "add", "-b", "entry-worktree", str(other))
        self.saved("payment", other)
        self.assertEqual((other / ".handover").resolve(), entry.resolve())
        self.assertEqual(self.progress(other)["totals"]["known_features"], 2)

    def test_v3_migration_previews_and_preserves_originals(self):
        source = self.legacy_store()
        original = self.snapshot(source)
        code, report = self.cli("migrate", feature=None, extra=["--dry-run"])
        self.assertEqual(code, 0, report)
        self.assertFalse(Path(self.ctx()["storage_root"]).exists())
        code, result = self.cli("migrate", feature=None, extra=["--source-signature", report["source_signature"]])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.snapshot(source), original)
        self.assertEqual(self.progress()["totals"]["known_features"], 2)
        self.assertEqual(self.cli("status", feature="login", extra=["--full"])[1]["state"]["custom"], {"keep": 42})
        code, again = self.cli("migrate", feature=None, extra=["--source-signature", report["source_signature"]])
        self.assertEqual(code, 0, again)
        self.assertEqual(self.cli("status", feature="login")[1]["version"], 1)

    def test_non_git_v3_layout_migrates_to_dot_handover(self):
        source = self.legacy_store(git_repo=False)
        original = self.snapshot(source)
        report = self.cli("migrate", feature=None, extra=["--dry-run"])[1]
        self.assertEqual(self.cli("migrate", feature=None, extra=["--source-signature", report["source_signature"]])[0], 0)
        self.assertEqual(self.snapshot(source), original)
        self.assertEqual(self.progress()["totals"]["known_features"], 2)

    def test_old_writer_changes_after_migration_are_detected(self):
        source = self.legacy_store()
        report = self.cli("migrate", feature=None, extra=["--dry-run"])[1]
        self.assertEqual(self.cli("migrate", feature=None, extra=["--source-signature", report["source_signature"]])[0], 0)
        old_file = next(source.glob("contexts/*/*/*/state.json"))
        old = json.loads(old_file.read_text(encoding="utf-8"))
        old["overview"] = "old agent wrote again"
        old_file.write_text(json.dumps(old), encoding="utf-8")
        state = self.cli("status", feature="login", extra=["--full"])[1]["state"]
        state["overview"] = "must not blindly merge"
        self.assertEqual(self.cli("save", state, 1, feature="login")[0], 8)
        self.assertEqual(self.cli("status", feature=None)[1]["progress"]["status"], "stale")

    def test_migration_conflict_does_not_overwrite_target(self):
        self.legacy_store()
        target = self.directory("login")
        target.mkdir(parents=True)
        state = self.proposal()
        state.update(feature_id="login", version=2, overview="newer target")
        (target / "state.json").write_text(json.dumps(state), encoding="utf-8")
        before = (target / "state.json").read_bytes()
        report = self.cli("migrate", feature=None, extra=["--dry-run"])[1]
        self.assertEqual(self.cli("migrate", feature=None, extra=["--source-signature", report["source_signature"]])[0], 3)
        self.assertEqual((target / "state.json").read_bytes(), before)

    def test_interrupted_layout_migration_can_resume_idempotently(self):
        self.legacy_store()
        ctx = self.ctx()
        report = H.M.preview(H.api(), ctx)
        original = H.write_json
        def fail_second(directory, name, value):
            if name.startswith("features/payment/") and name.endswith("state.json"):
                raise OSError("simulated interruption")
            return original(directory, name, value)
        with patch.object(H, "write_json", side_effect=fail_second):
            with self.assertRaises(OSError):
                H.M.run(H.api(), ctx, ctx["context_token"], report["source_signature"])
        self.assertTrue((Path(ctx["storage_root"]) / ".migration.pending.json").exists())
        self.assertEqual(self.cli("save", self.proposal(), 0)[0], 8)
        code, result = self.cli("migrate", feature=None, extra=["--source-signature", report["source_signature"]])
        self.assertEqual(code, 0, result)
        self.assertEqual(self.progress()["totals"]["known_features"], 2)

    def test_unknown_root_level_state_is_preserved(self):
        store = self.root / ".handover"
        store.mkdir()
        original = '{"foreign_agent":"keep this"}'
        (store / "state.json").write_text(original, encoding="utf-8")
        self.assertEqual(self.cli("save", self.proposal(), 0)[0], 8)
        self.assertEqual((store / "state.json").read_text(encoding="utf-8"), original)

    def test_new_project_can_save_after_creating_its_first_code(self):
        initial = self.cli("inspect", feature=None)[1]["inspection"]
        self.assertEqual(initial["kind"], "new-project")
        (self.root / "app.py").write_text("print('new project')", encoding="utf-8")
        state = self.proposal()
        state["intake"] = {"kind": "new-project", "basis": "empty workspace at task start; created first file this turn",
                           "references": ["app.py"], "initial_inspection": initial}
        code, result = self.cli("save", state, 0)
        self.assertEqual(code, 0, result)
        self.assertEqual(self.progress()["totals"]["known_features"], 1)

    def test_structurally_damaged_or_forged_total_is_rebuilt_from_sources(self):
        self.saved()
        path = self.root / ".handover/progress.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        damaged = {"schema_version": 1, "source_signature": original["source_signature"]}
        path.write_text(json.dumps(damaged), encoding="utf-8")
        self.assertEqual(self.cli("status", feature=None)[1]["progress"]["status"], "stale")
        self.assertEqual(self.cli("refresh", feature=None)[0], 0)
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged["features"][0]["status"] = "complete"
        forged["totals"]["completed_features"] = 1
        path.write_text(json.dumps(forged), encoding="utf-8")
        self.assertEqual(self.cli("status", feature=None)[1]["progress"]["status"], "stale")
        self.assertEqual(self.cli("refresh", feature=None)[0], 0)
        self.assertEqual(self.progress()["totals"]["completed_features"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
