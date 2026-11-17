#!/usr/bin/env python3
"""Context-bound handover storage. Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import handover_core as C
import handover_progress as P
import handover_layout as L
import handover_migrate as M

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "references/state.schema.json").read_text(encoding="utf-8"))
LOCAL = Path(".handover")
LEGACY_LOCAL = Path(".opencode/handover")
CORE = {"phase", "frontier", "gates", "lessons", "next_focus", "suggested_next"}
IDENTITY_KEYS = ("repository_id", "workspace_id", "branch_key")

def api():
    return SimpleNamespace(**globals())


def git(root, *arguments):
    try:
        result = subprocess.run(["git", "--no-optional-locks", "-C", str(root), *arguments],
                                capture_output=True, text=True, encoding="utf-8", timeout=10)
        return result.stdout.strip() if result.returncode == 0 else None
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        C.fail("Git 信息读取超时；未写入", 7)

def safe(base, relative=""):
    base = Path(base).resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base):
        C.fail("记录路径越出指定存储目录，已停止访问")
    return target

def local_base(root):
    return safe(root, str(LEGACY_LOCAL))

def context(value):
    root = Path(value).expanduser().resolve(strict=True)
    if not root.is_dir():
        C.fail("项目路径必须是目录")
    top = git(root, "rev-parse", "--show-toplevel")
    is_git = top is not None
    legacy_stores = []
    if is_git:
        root = Path(top).resolve(strict=True)
        common_name = git(root, "rev-parse", "--git-common-dir")
        git_dir = git(root, "rev-parse", "--absolute-git-dir")
        if common_name is None or git_dir is None:
            C.fail("Git 工作区身份无法确定；未写入", 7)
        common = (root / common_name).resolve()
        store = safe(common, ".handover")
        old_store = safe(common, "codex-handover")
        if old_store.exists():
            legacy_stores.append(str(old_store))
        branch = git(root, "symbolic-ref", "--quiet", "HEAD")
        head = git(root, "rev-parse", "--verify", "HEAD")
        if branch is None and head is None:
            C.fail("无法确定 Git 分支或 detached HEAD 身份", 7)
        branch_key = branch if branch else "detached/" + (head or "unknown")
        workspace_key = os.path.relpath(Path(git_dir).resolve(), common)
    else:
        common, branch, head, branch_key = root, None, None, "non-git"
        store = safe(root, str(LOCAL))
        workspace_key = "local"
    old_local = safe(root, str(LEGACY_LOCAL / "v3"))
    if old_local.exists():
        legacy_stores.append(str(old_local))
    entry = root / LOCAL
    if is_git and (entry.exists() or entry.is_symlink()) and entry.resolve() != store:
        if entry.resolve() != entry.absolute():
            C.fail("项目 .handover 入口指向其他目录；未使用不明存储", 7)
        if (entry / "repository.json").exists():
            legacy_stores.append(str(entry))
        elif any(item.name != "config.json" for item in entry.iterdir()):
            C.fail("已有 .handover 目录尚未识别，未覆盖", 8)
    repository_id = C.digest(os.path.normcase(str(common)))[:24]
    marker = safe(store, "repository.json")
    if not marker.exists() and is_git and (old_store / "repository.json").exists():
        marker = old_store / "repository.json"
    if not marker.exists() and not is_git and (old_local / "repository.json").exists():
        marker = old_local / "repository.json"
    if marker.exists():
        record = C.read_json(marker)
        if not isinstance(record, dict) or record.get("schema_version") != 3 or not isinstance(record.get("repository_id"), str) or not re.fullmatch(r"[0-9a-f]{24}", record["repository_id"]):
            C.fail("仓库身份记录无效；未重新初始化")
        repository_id = record["repository_id"]
    workspace_id = C.digest([repository_id, os.path.normcase(workspace_key)])[:24]
    identity = {"repository_id": repository_id, "workspace_id": workspace_id, "branch_key": C.digest(branch_key)}
    dirty = git(root, "status", "--porcelain=v1", "--untracked-files=normal") if is_git else None
    result = {"workspace_root": str(root), "storage_root": str(store), "entry_path": str(entry),
              "git_common_root": str(common) if is_git else None, "legacy_storage_roots": legacy_stores,
              "is_git": is_git, "branch_ref": branch, "head": head, "worktree_dirty": bool(dirty) if is_git else None, "identity": identity}
    result["context_token"] = C.digest({"identity": identity, "root": str(root), "head": head})
    return result

def assert_context(ctx, expected):
    if not expected or context(ctx["workspace_root"])["context_token"] != expected:
        C.fail("工作区、分支或 HEAD 已变化；请重新读取并核对当前功能，禁止沿用旧上下文保存", 7)

def mode(ctx):
    root = Path(ctx["workspace_root"])
    new_path = safe(ctx["storage_root"], "config.json")
    # A real local directory may precede creation of the Git entry.
    entry_config = Path(ctx["entry_path"]) / "config.json"
    if not new_path.exists() and entry_config.exists():
        new_path = entry_config
    def read_mode(path):
        value = C.read_json(path)
        if not isinstance(value, dict):
            C.fail("项目配置须为对象")
        mode_value = value.get("mode", "auto")
        if mode_value not in {"auto", "restore-only", "off"}:
            C.fail("mode 须为 auto、restore-only 或 off")
        return value, mode_value
    config, global_mode = read_mode(new_path) if new_path.exists() else ({}, "auto")
    overrides = config.get("workspaces", {})
    if not isinstance(overrides, dict):
        C.fail("workspaces 配置必须是对象")
    override = overrides.get(ctx["identity"]["workspace_id"])
    if override is not None:
        if not isinstance(override, dict) or override.get("mode") not in {"auto", "restore-only", "off"}:
            C.fail("工作区 mode 配置无效")
        local_mode = override["mode"]
    else:
        old = safe(local_base(root), "config.json")
        local_mode = read_mode(old)[1] if old.exists() else "auto"
    rank = {"off": 0, "restore-only": 1, "auto": 2}
    return min((global_mode, local_mode), key=rank.get)

def writable(ctx, expected):
    if mode(ctx) != "auto":
        C.fail("项目配置禁止写入交接记录", 4)
    assert_context(ctx, expected)
    M.guard(api(), ctx)
    if safe(ctx["storage_root"], "state.json").exists() or safe(ctx["storage_root"], "boot-packet.md").exists():
        C.fail("发现未知的根级旧状态或启动包；先核对归档，避免覆盖来源", 8)
    if safe(ctx["storage_root"], "project_summary.md").exists() and not any(safe(ctx["storage_root"], name).exists() for name in ("project.json", "repository.json", "progress.json")):
        C.fail("根目录只剩来源不明的摘要；先核对归档，不覆盖该文件", 8)

def feature_dir(ctx, feature):
    if not isinstance(feature, str) or not feature.strip() or len(feature) > 120:
        C.fail("必须明确提供 1 到 120 字符的 feature id")
    if C.redact(feature)[0] != feature:
        C.fail("功能 id 含需脱敏内容，请使用非私人标识")
    return safe(ctx["storage_root"], f'features/{P.feature_path_component(api(), feature)}/{P.context_id(api(), ctx["identity"])}')

@contextmanager
def locked(directory, timeout=5):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with safe(directory, ".handover.lock").open("a+b") as stream:
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    C.fail("其他会话正在保存；锁等待超时，未覆盖记录", 6)
                time.sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)

def atomic(directory, name, content):
    target = safe(directory, name)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".handover-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def write_json(directory, name, value):
    atomic(directory, name, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")

def ensure_repository(ctx):
    target = safe(ctx["storage_root"], "repository.json")
    if target.exists():
        if C.read_json(target).get("repository_id") != ctx["identity"]["repository_id"]:
            C.fail("仓库身份发生变化，未写入", 7)
    else:
        write_json(ctx["storage_root"], "repository.json", {"schema_version": 3, "layout_version": 4, "repository_id": ctx["identity"]["repository_id"]})

def fresh(ctx, feature):
    state = C.empty_state()
    state.update(schema_version=3, feature_id=feature, identity=copy.deepcopy(ctx["identity"]))
    return state

def validate_feature(state):
    C.validate_schema(state, SCHEMA, root_schema=SCHEMA)
    C.validate_state({**state, "schema_version": 2})
    if state["intake"]["kind"] == "existing-project" and not state["intake"]["references"]:
        C.fail("老项目首次接入须引用已核对的项目资料或 Git 现状")
    evidence = state.get("integration")
    if evidence is not None:
        if not isinstance(evidence, dict) or evidence.get("status") not in {"merged", "pending"}:
            C.fail("integration 记录格式无效")
        if evidence["status"] == "merged" and (evidence.get("source") not in {"user", "observed"} or not evidence.get("evidence")):
            C.fail("已合并声明须有用户或观察来源及证据引用")
    acceptance = state.get("acceptance")
    if acceptance is not None and (not isinstance(acceptance, dict) or acceptance.get("status") not in {"accepted", "pending", "rejected"} or
                                   acceptance.get("source") != "user" or not acceptance.get("basis")):
        C.fail("验收声明须有用户来源及依据")

def load_feature(ctx, feature):
    path = safe(feature_dir(ctx, feature), "state.json")
    if not path.exists():
        return fresh(ctx, feature), False
    state = C.read_json(path)
    validate_feature(state)
    if state["feature_id"] != feature or any(state["identity"].get(key) != ctx["identity"][key] for key in IDENTITY_KEYS):
        C.fail("记录与当前仓库、工作区、分支或功能不匹配；禁止自动重绑", 7)
    return state, True

def projection_status(directory, projections):
    result = {}
    for name, expected in projections.items():
        path = safe(directory, name)
        result[name] = "missing" if not path.exists() else "current" if path.read_text(encoding="utf-8-sig") == expected else "stale"
    return result

def inspect_project(ctx):
    root = Path(ctx["workspace_root"])
    entries = sorted(item.name for item in root.iterdir() if item.name not in {".git", ".opencode", ".handover"} and not item.name.startswith(".handover.archive-"))
    dirty = git(root, "status", "--porcelain=v1", "--untracked-files=normal") if ctx["is_git"] else None
    return {"kind": "existing-project" if entries or ctx["head"] else "new-project", "top_level_entries": entries[:100],
            "workspace_root": ctx["workspace_root"],
            "head": ctx["head"], "branch_ref": ctx["branch_ref"], "dirty_paths": dirty.splitlines()[:100] if dirty else [],
            "instruction_files": [name for name in ("AGENTS.override.md", "AGENTS.md") if (root / name).is_file()],
            "note": "目录与 Git 现状不是历史任务或测试通过证明"}

def legacy_probe(ctx, record=None, full=False, source_context=None):
    base = local_base(Path(ctx["workspace_root"]))
    files, kind = {}, None
    state_path = safe(base, "state.json")
    if source_context:
        source = safe(ctx["storage_root"], source_context)
        if source.name != "state.json" or not source.is_relative_to(safe(ctx["storage_root"], "features")) or not source.exists():
            C.fail("source-context 须为本仓库列出的功能状态")
        raw = C.read_json(source)
        validate_feature(raw)
        if raw["identity"]["repository_id"] != ctx["identity"]["repository_id"]:
            C.fail("不能直接接续其他仓库的功能", 7)
        kind, files = "context-record", {"state.json": source}
    elif state_path.exists():
        kind, files = "legacy-state", {"state.json": state_path}
        for name in ("boot-packet.md", "project_summary.md"):
            if safe(base, name).exists():
                files[name] = safe(base, name)
    elif any(safe(base, name).exists() for name in ("boot-packet.md", "project_summary.md")):
        kind = "orphan-summaries"
        files = {name:safe(base,name) for name in ("boot-packet.md","project_summary.md") if safe(base,name).exists()}
    else:
        report = M.preview(api(), ctx)
        compatible = [item for item in report["stores"] if item["compatible_identity"]]
        if compatible and not record:
            return {"kind":"migrated-store" if report["status"]=="migrated" else "layout-store",
                    "signature":report["source_signature"],"stores":report["stores"],"review_required":report["status"]!="migrated"}
        candidates = []
        for root_value in M.roots(api(), ctx):
            root = Path(root_value)
            for item in list(root.glob("contexts/*/*/*/state.json"))+list(root.glob("features/*/*/state.json")):
                candidates.append((root,item))
        matching = [(root,item) for root,item in candidates if str(item.relative_to(root))==record or item.relative_to(root).as_posix()==record] if record else candidates
        if matching:
            if len(matching)!=1:
                return {"kind":"local-record-selection-required","records":[{"store":str(root),"record":item.relative_to(root).as_posix()} for root,item in matching]}
            root,source = matching[0]
            kind,files = "local-v4" if "features" in source.relative_to(root).parts else "local-v3", {"state.json":safe(root,str(source.relative_to(root)))}
        elif report["stores"]:
            return {"kind":"local-project","stores":report["stores"],"signature":report["source_signature"],"review_required":True}
    if kind is None:
        return {"kind":"none"}
    signature = C.digest({name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()})
    result = {"kind":kind,"signature":signature,"files":{name:str(path) for name,path in files.items()},"review_required":True}
    if "state.json" in files:
        try:
            raw=C.read_json(files["state.json"])
            if not isinstance(raw,dict):
                C.fail("旧状态不是对象")
            version=raw.get("schema_version",1)
            if type(version) is not int or version not in {1,2,3}:
                C.fail("旧格式版本未知")
            state=C.migrate_legacy(raw) if version==1 else raw
            validate_feature(state) if version==3 else C.validate_state(state)
            if full:
                result["state"]=C.redact(state)[0]
        except (C.HandoverError,TypeError,KeyError):
            result["kind"]="invalid-legacy-state"
            result["error"]="旧状态无法可靠读取，原文件保留，禁止空状态覆盖"
    if full and kind=="orphan-summaries":
        result["documents"]=C.redact({name:path.read_text(encoding="utf-8-sig") for name,path in files.items()})[0]
    if not source_context and result["kind"] not in {"invalid-legacy-state"}:
        for existing in safe(ctx["storage_root"],"features").glob("*/*/state.json"):
            try:
                imported=C.read_json(existing).get("imported_from",{})
                if imported.get("signature")==signature:
                    result["kind"]="archived-source"
                    result["review_required"]=False
                    break
            except (C.HandoverError,AttributeError):
                pass
    return result

def feature_listing(ctx, all_contexts=False):
    root = safe(ctx["storage_root"], "features")
    result = []
    for path in sorted(root.glob("*/*/state.json")):
        path = safe(root, str(path.relative_to(root)))
        try:
            state = C.read_json(path)
            validate_feature(state)
            if not all_contexts and any(state["identity"].get(key) != ctx["identity"][key] for key in IDENTITY_KEYS):
                continue
            result.append({"feature_id": state["feature_id"], "context_id": P.context_id(api(), state["identity"]),
                           "version": state["version"], "identity": state["identity"],
                           "branch_ref": state.get("recorded_context", {}).get("branch_ref"),
                           "overview": C.line(state.get("overview") or state["feature_id"], 120), "state_path": str(path)})
        except C.HandoverError:
            result.append({"error": "该功能记录无效，未当成空记录处理", "state_path": str(path)})
    return result

def validate_project(record, ctx):
    if not isinstance(record, dict) or record.get("schema_version") != 3 or type(record.get("version")) is not int or record["version"] < 0:
        C.fail("项目共享信息格式或版本无效")
    if record.get("repository_id") != ctx["identity"]["repository_id"]:
        C.fail("项目共享信息属于其他仓库", 7)
    if any(key in record for key in CORE):
        C.fail("功能进度和下一步不得混入项目共享信息")
    if not isinstance(record.get("overview"), (str, type(None))) or not isinstance(record.get("facts"), list):
        C.fail("项目共享信息须包含 overview 和 facts")
    P.validate_plan(api(), record)
    seen = set()
    for fact in record["facts"]:
        if not isinstance(fact, dict) or any(not isinstance(fact.get(key), str) or not fact[key].strip() for key in ("id", "content", "basis")):
            C.fail("共享事实须包含 id、content 和 basis")
        if fact.get("source") not in {"user", "observed"} or not isinstance(fact.get("references"), list) or not fact["references"]:
            C.fail("共享事实仅接受用户确定或已观察的事实，须有引用")
        if any(not isinstance(item, str) or not item.strip() for item in fact["references"]) or fact["id"] in seen:
            C.fail("共享事实引用为空或 id 重复")
        seen.add(fact["id"])

def load_project(ctx):
    path = safe(ctx["storage_root"], "project.json")
    if not path.exists():
        return {"schema_version": 3, "version": 0, "updated_at": None, "repository_id": ctx["identity"]["repository_id"], "overview": None, "facts": []}, False
    record = C.read_json(path)
    validate_project(record, ctx)
    return record, True

def project_projection(record):
    lines = [f'<!-- handover project_version={record["version"]} project_sha256={C.digest(record)} -->', "# 项目共享信息",
             C.line(record["overview"] or "尚未记录项目概览", 500)]
    for fact in record["facts"]:
        lines.append(f'- [{fact["source"]}] {C.line(fact["content"], 500)}；依据：{C.line(fact["basis"], 300)}；引用：{C.line(", ".join(fact["references"]), 500)}')
    lines.append("功能进度与下一步请读取当前工作区、分支和功能的记录。")
    return {"project_summary.md": "\n".join(lines) + "\n"}

def status(ctx, feature=None, full=False, all_contexts=False, legacy=False, record=None, source_context=None):
    result = {**ctx, "mode": mode(ctx)}
    if result["mode"] == "off":
        return result
    project, exists = load_project(ctx)
    progress = P.inspect(api(), ctx, full)
    result["project"] = {"exists": exists, "version": project["version"], "summary": {"project_summary.md": progress.get("summary", "missing")}}
    result["progress"] = progress
    if full:
        result["project"]["record"] = project
    result["available_features"] = feature_listing(ctx, all_contexts)
    result["legacy"] = legacy_probe(ctx, record, legacy, source_context)
    result["migration"] = M.preview(api(), ctx)
    if feature is not None:
        state, exists = load_feature(ctx, feature)
        result.update(feature_id=feature, exists=exists, version=state["version"], state_path=str(safe(feature_dir(ctx, feature), "state.json")))
        result["projections"] = projection_status(feature_dir(ctx, feature), C.render_projections(state)) if exists else {}
        result["head_changed_since_save"] = exists and state.get("recorded_context", {}).get("head") != ctx["head"]
        if full:
            result["state"] = state
    assert_context(ctx, ctx["context_token"])
    return result


def finish_save(ctx, token, timeout=5, allow_archive=False):
    entry = L.publish(api(), ctx, allow_archive)
    progress = P.refresh(api(), ctx, token, timeout)
    return {"progress": progress, "entry": entry}


def save_feature(ctx, feature, candidate, expected, token, session=None, timeout=5, adoption=None, agent=None):
    if isinstance(candidate, dict) and agent:
        candidate = {**candidate, "last_agent": agent}
    try:
        result = _save_feature(ctx, feature, candidate, expected, token, session, timeout, adoption)
    except C.HandoverError as error:
        if error.details.get("committed"):
            try:
                error.details.update(finish_save(ctx, token, timeout, bool(adoption)))
            except (OSError, C.HandoverError):
                error.details["progress_status"] = "stale"
        raise
    if result["action"] != "unchanged":
        try:
            result.update(finish_save(ctx, token, timeout, bool(adoption) or bool(candidate.get("intake", {}).get("legacy_review"))))
        except (OSError, C.HandoverError) as error:
            C.fail("功能状态已提交，总览或目录入口未完成；按返回版本修复，不重放保存", 5,
                   committed=True, feature_id=feature, version=result["version"], storage_root=ctx["storage_root"], cause=str(error))
    return result


def save_project(ctx, candidate, expected, token, timeout=5):
    try:
        result = _save_project(ctx, candidate, expected, token, timeout)
    except C.HandoverError as error:
        if error.details.get("committed"):
            error.details["progress_status"] = "stale"
        raise
    if result["action"] != "unchanged":
        try:
            result.update(finish_save(ctx, token, timeout))
        except (OSError, C.HandoverError) as error:
            C.fail("项目计划已提交，总览或入口未完成；可执行 refresh", 5, committed=True, project_version=result["project_version"], cause=str(error))
    return result


def repair(ctx, feature, expected, token, timeout=5, project=False):
    writable(ctx, token)
    if project:
        current, exists = load_project(ctx)
        expected_revision(current["version"], expected)
        if not exists:
            C.fail("尚无项目记录")
        result = {"action": "repaired", "version": current["version"]}
    else:
        result = _repair(ctx, feature, expected, token, timeout)
    result.update(finish_save(ctx, token, timeout))
    return result

def expected_revision(actual, expected):
    if type(expected) is not int or expected < 0:
        C.fail("写入必须提供非负整数 expected-version")
    if actual != expected:
        C.fail("版本冲突；请重新读取并核对差异，禁止仅修改版本号重试覆盖", 3, expected_version=expected, actual_version=actual)

def facts(record):
    return {key: value for key, value in record.items() if key not in {"version", "updated_at", "recorded_context", "last_session", "last_agent"}}

def _save_feature(ctx, feature, candidate, expected, token, session=None, timeout=5, adoption=None):
    writable(ctx, token)
    if not isinstance(candidate, dict) or not CORE.issubset(candidate):
        C.fail("须提供六个完整核心字段；先按功能读取 status --full")
    if (type(candidate.get("schema_version", 3)) is not int or candidate.get("schema_version", 3) != 3) and adoption is None:
        C.fail("旧状态须核对后使用 adopt；不能直接作为新功能保存", 8)
    if "feature_id" in candidate and candidate["feature_id"] != feature and adoption is None:
        C.fail("输入属于另一个功能", 7)
    if "identity" in candidate and (not isinstance(candidate["identity"], dict) or any(candidate["identity"].get(key) != ctx["identity"][key] for key in IDENTITY_KEYS)) and adoption is None:
        C.fail("输入属于其他工作区或分支", 7)
    directory = feature_dir(ctx, feature)
    with locked(directory, timeout):
        writable(ctx, token)
        current, exists = load_feature(ctx, feature)
        expected_revision(current["version"], expected)
        if "version" in candidate and adoption is None:
            expected_revision(current["version"], candidate["version"])
        if adoption is not None and exists:
            C.fail("导入目标已有记录；禁止覆盖，请选择目标或核对合并", 8)
        legacy = legacy_probe(ctx, adoption.get("record") if adoption else None, source_context=adoption.get("source_context") if adoption else None)
        if adoption:
            if legacy.get("signature") != adoption["signature"] or legacy["kind"] not in {"legacy-state", "orphan-summaries", "local-v3", "local-v4", "context-record"}:
                C.fail("旧记录已变化或无法可靠导入；未写入", 8)
        elif not exists and legacy["kind"] not in {"none", "migrated-store", "archived-source"}:
            review = candidate.get("intake", {}).get("legacy_review", {})
            if review.get("signature") != legacy.get("signature") or review.get("decision") != "separate-feature" or not review.get("basis"):
                C.fail("发现旧记录或残留摘要；须先核对导入，或明确记录这是独立新功能", 8)
        merged = {**copy.deepcopy(current), **copy.deepcopy(candidate), "schema_version": 3, "feature_id": feature,
                  "identity": copy.deepcopy(ctx["identity"]), "version": current["version"], "updated_at": current["updated_at"]}
        if not exists and "intake" not in candidate:
            C.fail("首次接入须记录 intake：项目类型、核对依据及引用", 8)
        if not exists and adoption is None:
            intake_kind = merged.get("intake", {}).get("kind")
            if intake_kind not in {"new-project", "existing-project", "new-feature"}:
                C.fail("普通保存不能冒充旧记录导入或摘要恢复", 8)
            if intake_kind == "new-project" and inspect_project(ctx)["kind"] != "new-project":
                initial = merged["intake"].get("initial_inspection", {})
                if not (isinstance(initial, dict) and initial.get("kind") == "new-project" and initial.get("top_level_entries") == [] and
                        initial.get("head") is None and initial.get("workspace_root") == ctx["workspace_root"]):
                    C.fail("项目已有文件或提交，须核对老项目；本轮新建项目可附最初的空目录检查结果", 8)
        if adoption:
            merged["imported_from"] = {key: value for key, value in legacy.items() if key not in {"state", "documents"}}
            merged["intake"]["kind"] = "summary-recovery" if legacy["kind"] == "orphan-summaries" else "legacy-import"
        merged, redactions = C.redact(merged)
        validate_feature(merged)
        if exists and C.canonical(facts(merged)) == C.canonical(facts(current)):
            return {"action": "unchanged", "feature_id": feature, "version": current["version"]}
        old_todos = {todo["id"]: todo for todo in current["frontier"]}
        for todo in merged["frontier"]:
            verification = todo["verification"]
            if adoption:
                verification.setdefault("checked_context", None)
                verification.setdefault("checked_head", None)
                verification["origin"] = "context-import" if legacy["kind"] == "context-record" else "legacy"
            elif verification["status"] == "passed" and verification != old_todos.get(todo["id"], {}).get("verification"):
                verification["checked_context"] = token
                verification["checked_head"] = ctx["head"]
        merged["version"] += 1
        merged["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        merged["recorded_context"] = C.redact({key: ctx[key] for key in ("workspace_root", "branch_ref", "head", "context_token", "worktree_dirty")})[0]
        merged["last_session"] = C.redact(session)[0]
        ensure_repository(ctx)
        if adoption:
            contents = {name: C.read_json(Path(path)) if name == "state.json" else Path(path).read_text(encoding="utf-8-sig") for name, path in legacy["files"].items()}
            write_json(directory, "evidence/import-source.json", C.redact(contents)[0])
            if legacy_probe(ctx, adoption.get("record"), source_context=adoption.get("source_context")).get("signature") != adoption["signature"]:
                C.fail("导入期间旧记录发生变化；原记录未覆盖", 8)
        assert_context(ctx, token)
        write_json(directory, "state.json", merged)
        try:
            for name, content in C.render_projections(merged).items():
                atomic(directory, name, content)
            if redactions:
                atomic(directory, f'evidence/redaction-v{merged["version"]}.md', "本次保存已脱敏；未记录敏感明文。\n")
        except OSError:
            C.fail("状态已提交，摘要生成失败；按返回版本执行 repair", 5, committed=True, version=merged["version"], feature_id=feature)
        return {"action": "imported" if adoption else "saved", "feature_id": feature, "version": merged["version"], "redactions": redactions}

def _save_project(ctx, candidate, expected, token, timeout=5):
    writable(ctx, token)
    if not isinstance(candidate, dict) or not {"overview", "facts"}.issubset(candidate):
        C.fail("共享信息输入须包含 overview、facts")
    if "repository_id" in candidate and candidate["repository_id"] != ctx["identity"]["repository_id"]:
        C.fail("输入的项目共享信息属于其他仓库", 7)
    with locked(ctx["storage_root"], timeout):
        writable(ctx, token)
        current, _ = load_project(ctx)
        expected_revision(current["version"], expected)
        if "version" in candidate:
            expected_revision(current["version"], candidate["version"])
        merged = {**current, **candidate, "schema_version": 3, "repository_id": ctx["identity"]["repository_id"],
                  "version": current["version"], "updated_at": current["updated_at"]}
        merged, redactions = C.redact(merged)
        validate_project(merged, ctx)
        if C.canonical(facts(merged)) == C.canonical(facts(current)):
            return {"action": "unchanged", "project_version": current["version"]}
        merged["version"] += 1
        merged["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ensure_repository(ctx)
        assert_context(ctx, token)
        write_json(ctx["storage_root"], "project.json", merged)
        try:
            for name, content in project_projection(merged).items():
                atomic(ctx["storage_root"], name, content)
            if redactions:
                atomic(ctx["storage_root"], f'evidence/project-redaction-v{merged["version"]}.md', "项目共享信息已脱敏。\n")
        except OSError:
            C.fail("项目共享信息已提交，摘要失败；可执行 project-repair", 5, committed=True, project_version=merged["version"])
        return {"action": "saved", "project_version": merged["version"]}

def _repair(ctx, feature, expected, token, timeout=5, project=False):
    writable(ctx, token)
    directory = Path(ctx["storage_root"]) if project else feature_dir(ctx, feature)
    with locked(directory, timeout):
        writable(ctx, token)
        record, exists = load_project(ctx) if project else load_feature(ctx, feature)
        expected_revision(record["version"], expected)
        if not exists:
            C.fail("尚无记录，不能重建摘要")
        if C.canonical(C.redact(record)[0]) != C.canonical(record):
            C.fail("原记录含待脱敏内容，请先通过保存工具处理")
        projections = project_projection(record) if project else C.render_projections(record)
        states = projection_status(directory, projections)
        for name, content in projections.items():
            if states[name] != "current":
                assert_context(ctx, token)
                atomic(directory, name, content)
        return {"action": "repaired", "version": record["version"], "files": [name for name in states if states[name] != "current"]}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "inspect", "save", "adopt", "repair", "project-save", "project-repair", "refresh", "migrate"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--feature")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--all-contexts", action="store_true")
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--legacy-record")
    parser.add_argument("--source-signature")
    parser.add_argument("--source-context", help="review/import one listed context state, relative to storage_root")
    parser.add_argument("--input")
    parser.add_argument("--expected-version", type=int)
    parser.add_argument("--expected-context")
    parser.add_argument("--session-id")
    parser.add_argument("--agent", help="provenance only; never used as a feature or context id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--lock-timeout", type=float, default=5)
    args = parser.parse_args(argv)
    try:
        if not 0 <= args.lock_timeout <= 30:
            C.fail("lock-timeout 须为 0 到 30 秒")
        ctx = context(args.root)
        if args.action == "status":
            result = status(ctx, args.feature, args.full, args.all_contexts, args.legacy, args.legacy_record, args.source_context)
        elif args.action == "inspect":
            result = {**ctx, "mode": mode(ctx)}
            if result["mode"] != "off":
                result["inspection"] = inspect_project(ctx)
                result["legacy"] = legacy_probe(ctx, args.legacy_record)
        elif args.action == "refresh":
            result = finish_save(ctx, args.expected_context, args.lock_timeout)
        elif args.action == "migrate":
            import handover_migrate as M
            result = M.run(api(), ctx, args.expected_context, args.source_signature, args.dry_run, args.lock_timeout)
        else:
            if args.action in {"save", "adopt", "project-save"}:
                if not args.input:
                    C.fail("保存或导入须提供 input 文件或标准输入")
                candidate = json.loads(sys.stdin.read()) if args.input == "-" else C.read_json(Path(args.input))
            if args.action == "project-save":
                result = save_project(ctx, candidate, args.expected_version, args.expected_context, args.lock_timeout)
            elif args.action in {"repair", "project-repair"}:
                result = repair(ctx, args.feature, args.expected_version, args.expected_context, args.lock_timeout, args.action == "project-repair")
            else:
                adoption = {"signature": args.source_signature, "record": args.legacy_record, "source_context": args.source_context} if args.action == "adopt" else None
                if adoption and not args.source_signature:
                    C.fail("adopt 须提供核对过的 source-signature", 8)
                result = save_feature(ctx, args.feature, candidate, args.expected_version, args.expected_context, args.session_id, args.lock_timeout, adoption, args.agent)
        print(json.dumps({"ok": True, **result}, ensure_ascii=False, allow_nan=False))
        return 0
    except C.HandoverError as error:
        print(json.dumps({"ok": False, "error": str(error), **error.details}, ensure_ascii=False))
        return error.code
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        print(json.dumps({"ok": False, "error": "文件、编码或记录结构异常；未以空记录强制覆盖原数据"}, ensure_ascii=False))
        return 5


if __name__ == "__main__":
    sys.exit(main())
