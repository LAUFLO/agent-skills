"""Project-wide derived progress; authoritative facts remain in feature states."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

LABELS = {
    "pending": "未开始", "in_progress": "开发中", "needs_verification": "待验证",
    "needs_fix": "验证失败待修复", "verified": "验证通过", "complete": "已完成",
    "blocked": "受阻", "cancelled": "已取消", "unknown": "信息不足",
    "needs_reconciliation": "多个上下文待归并", "awaiting_merge": "待合并",
    "awaiting_acceptance": "待验收", "needs_review": "提交已变化待复核"
}
INTEGRATION = {"merged": "已合并", "unmerged": "未合并", "uncommitted": "含未提交改动",
               "unknown": "待核对", "not_required": "未要求合并"}


def feature_path_component(api, feature):
    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", feature) and len(feature) <= 64 and feature not in {
        "con", "prn", "aux", "nul", *("com" + str(n) for n in range(1, 10)), *("lpt" + str(n) for n in range(1, 10))
    }:
        return feature
    return "feature-" + api.C.digest(feature)[:24]


def context_id(api, identity):
    return api.C.digest([identity["workspace_id"], identity["branch_key"]])[:24]


def validate_plan(api, project):
    """Validate optional user plan; no invented percentage denominator."""
    features = project.get("features", [])
    milestones = project.get("milestones", [])
    goals = project.get("goals", [])
    if not isinstance(features, list) or not isinstance(milestones, list) or not isinstance(goals, list):
        api.C.fail("项目 features、milestones、goals 必须是数组")
    if "scope_complete" in project and type(project["scope_complete"]) is not bool:
        api.C.fail("scope_complete 必须为布尔值")
    ids = set()
    for feature in features:
        if not isinstance(feature, dict) or any(not isinstance(feature.get(key), str) or not feature[key].strip() for key in ("id", "title")):
            api.C.fail("项目功能清单须有非空 id 和 title")
        if feature["id"] in ids:
            api.C.fail("项目功能清单 id 重复")
        ids.add(feature["id"])
        if "primary_context" in feature and feature["primary_context"] is not None and not re.fullmatch(r"[0-9a-f]{24}", feature["primary_context"]):
            api.C.fail("primary_context 必须为工具列出的工作上下文 ID")
        if "target_branch" in feature and feature["target_branch"] is not None and not isinstance(feature["target_branch"], str):
            api.C.fail("target_branch 必须是分支名或 null")
        completion = feature.get("completion", {})
        if not isinstance(completion, dict) or any(type(value) is not bool for key, value in completion.items() if key in {"require_merge", "require_acceptance"}):
            api.C.fail("功能完成条件必须使用布尔值")
    for collection, is_milestone in ((goals, False), (milestones, True)):
        seen = set()
        for item in collection:
            if not isinstance(item, dict) or any(not isinstance(item.get(key), str) or not item[key].strip() for key in ("id", "title")) or item["id"] in seen:
                api.C.fail("项目目标或里程碑缺少 id/title 或 id 重复")
            seen.add(item["id"])
            if is_milestone:
                references = item.get("feature_ids", [])
                if not isinstance(references, list) or any(value not in ids for value in references):
                    api.C.fail("里程碑只能引用项目功能清单中的 id")


def reference(api, ctx, branch):
    if not branch:
        return None
    ref = branch if branch.startswith("refs/heads/") else "refs/heads/" + branch
    return api.git(ctx["workspace_root"], "rev-parse", "--verify", ref) if ctx["is_git"] else None


def collect(api, ctx):
    project, _ = api.load_project(ctx)
    root = Path(ctx["storage_root"])
    states, errors, sources, refs = [], [], {}, {}
    for path in sorted(root.glob("features/*/*/state.json")):
        path = api.safe(root, str(path.relative_to(root)))
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        sources[relative] = hashlib.sha256(data).hexdigest()
        try:
            state = json.loads(data.decode("utf-8-sig"))
            api.validate_feature(state)
            if state["identity"]["repository_id"] != ctx["identity"]["repository_id"]:
                api.C.fail("功能记录属于其他仓库")
            expected = root / "features" / feature_path_component(api, state["feature_id"]) / context_id(api, state["identity"]) / "state.json"
            if path != expected.resolve():
                api.C.fail("功能记录与目录中的上下文身份不匹配")
            states.append((relative, state))
            branch = state.get("recorded_context", {}).get("branch_ref")
            if branch and ctx["is_git"]:
                refs[branch] = reference(api, ctx, branch)
        except (api.C.HandoverError, ValueError, UnicodeError, TypeError, KeyError):
            errors.append({"state_path": relative, "error": "状态无效，未忽略或重置；总完成情况须复核"})
    for definition in project.get("features", []):
        branch = definition.get("target_branch")
        if branch and ctx["is_git"]:
            refs[branch] = reference(api, ctx, branch)
    legacy = {}
    receipt = api.safe(ctx["storage_root"], "evidence/layout-migration.json")
    if receipt.exists():
        for key, source in api.C.read_json(receipt).get("sources", {}).items():
            root_value = Path(source["root"])
            legacy[key] = api.M.source_snapshot(api, root_value) if root_value.exists() else None
    manifest = {"project_hash": api.C.digest(project), "states": sources, "branch_heads": refs, "legacy_sources": legacy}
    return project, states, errors, manifest


def context_progress(api, ctx, relative, state, refs):
    todos = state["frontier"]
    active = [todo for todo in todos if todo["status"] != "cancelled"]
    active_ids = {todo["id"] for todo in active if todo["status"] != "verified"}
    gates = [gate for gate in state["gates"] if not gate["blocked_todos"] or set(gate["blocked_todos"]) & active_ids]
    if gates or any(todo["status"] == "blocked" for todo in active):
        status = "blocked"
    elif any(todo["verification"]["status"] == "failed" for todo in active):
        status = "needs_fix"
    elif not active:
        status = "cancelled" if todos else "unknown"
    elif all(todo["status"] == "pending" for todo in active):
        status = "pending"
    elif all(todo["status"] == "verified" for todo in active):
        status = "verified"
    elif all(todo["status"] in {"implemented", "verified"} for todo in active):
        status = "needs_verification"
    else:
        status = "in_progress"
    recorded = state.get("recorded_context", {})
    if status == "verified":
        for todo in active:
            proof = todo["verification"]
            if proof.get("checked_context") != recorded.get("context_token") or proof.get("checked_head") != recorded.get("head"):
                status = "needs_verification"
                break
        branch = recorded.get("branch_ref")
        if branch and branch in refs and refs[branch] != recorded.get("head"):
            status = "needs_review"
        if state["next_focus"] is not None:
            status = "in_progress"
    blockers = [gate["reason"] for gate in gates] + [todo["reason"] for todo in active if todo["status"] == "blocked"]
    return {"context_id": context_id(api, state["identity"]), "state_path": relative, "version": state["version"],
            "identity": state["identity"], "branch_ref": recorded.get("branch_ref"), "saved_head": recorded.get("head"),
            "worktree_dirty": recorded.get("worktree_dirty"), "status": status, "blockers": blockers,
            "next_focus": state["next_focus"], "suggested_next": state["suggested_next"],
            "last_session": state.get("last_session"), "last_agent": state.get("last_agent"),
            "acceptance": state.get("acceptance"), "integration_evidence": state.get("integration")}


def integration(api, ctx, selected, definition, refs):
    target = definition.get("target_branch")
    required = definition.get("completion", {}).get("require_merge", bool(target))
    if not required:
        return "not_required"
    recorded = selected.get("integration_evidence")
    if isinstance(recorded, dict) and recorded.get("status") == "merged" and recorded.get("source") in {"user", "observed"} and recorded.get("evidence"):
        if not target or recorded.get("target_branch") == target:
            return "merged"
    if selected["worktree_dirty"] is True:
        return "uncommitted"
    if selected["worktree_dirty"] is not False:
        return "unknown"
    head, target_head = selected.get("saved_head"), refs.get(target)
    if not ctx["is_git"] or not target or not head or not target_head or not re.fullmatch(r"[0-9a-f]{40,64}", head):
        return "unknown"
    return "merged" if api.git(ctx["workspace_root"], "merge-base", "--is-ancestor", head, target_head) is not None else "unmerged"


def build(api, ctx, project, states, errors, manifest):
    grouped = {}
    for relative, state in states:
        grouped.setdefault(state["feature_id"], []).append(context_progress(api, ctx, relative, state, manifest["branch_heads"]))
    definitions = {item["id"]: item for item in project.get("features", [])}
    rows = []
    for feature_id in sorted(set(definitions) | set(grouped)):
        definition = definitions.get(feature_id, {})
        contexts = grouped.get(feature_id, [])
        primary = definition.get("primary_context")
        selected = next((item for item in contexts if item["context_id"] == primary), None) if primary else contexts[0] if len(contexts) == 1 else None
        if not primary and len(contexts) > 1 and definition.get("target_branch"):
            target = definition["target_branch"]
            target = target if target.startswith("refs/heads/") else "refs/heads/" + target
            candidates = [item for item in contexts if item["branch_ref"] == target]
            selected = candidates[0] if len(candidates) == 1 else None
        status = selected["status"] if selected else "pending" if not contexts else "needs_reconciliation"
        merged = integration(api, ctx, selected, definition, manifest["branch_heads"]) if selected else "unknown"
        if status == "verified":
            if definition.get("completion", {}).get("require_merge", bool(definition.get("target_branch"))) and merged != "merged":
                status = "awaiting_merge"
            elif definition.get("completion", {}).get("require_acceptance") and not (
                isinstance(selected["acceptance"], dict) and selected["acceptance"].get("status") == "accepted" and selected["acceptance"].get("source") == "user" and selected["acceptance"].get("basis")
            ):
                status = "awaiting_acceptance"
            else:
                status = "complete"
        rows.append({"feature_id": feature_id, "title": definition.get("title", feature_id), "planned": feature_id in definitions,
                     "status": status, "integration": merged, "selected_context": selected["context_id"] if selected else None,
                     "context_count": len(contexts), "contexts": contexts,
                     "blockers": selected["blockers"] if selected else list(dict.fromkeys(value for item in contexts for value in item["blockers"]))})
    by_id = {row["feature_id"]: row for row in rows}
    milestones = []
    for milestone in project.get("milestones", []):
        feature_ids = milestone.get("feature_ids", [])
        completed = sum(by_id[value]["status"] == "complete" for value in feature_ids)
        milestones.append({**milestone, "completed": completed, "total": len(feature_ids),
                           "status": "complete" if feature_ids and completed == len(feature_ids) else "in_progress" if feature_ids else "unknown"})
    counts = dict(Counter(row["status"] for row in rows))
    complete_scope = bool(project.get("scope_complete")) and bool(definitions) and not errors and set(grouped).issubset(definitions)
    planned_complete = sum(row["status"] == "complete" for row in rows if row["planned"])
    return {"schema_version": 1, "repository_id": ctx["identity"]["repository_id"], "source_signature": api.C.digest(manifest),
            "sources": manifest, "features": rows, "milestones": milestones, "goals": project.get("goals", []),
            "invalid_records": errors,
            "totals": {"known_features": len(rows), "planned_features": len(definitions), "completed_features": counts.get("complete", 0),
                       "contexts": len(states), "invalid_records": len(errors), "status_counts": counts, "scope_complete": complete_scope,
                       "completion_ratio": planned_complete / len(definitions) if complete_scope else None}}


def render(api, project, progress):
    def cell(value):
        return api.C.line(value, 150).replace("|", "\\|")
    totals = progress["totals"]
    lines = [f'<!-- handover progress_revision={progress["revision"]} source_signature={progress["source_signature"]} -->',
             "# 项目总进度", cell(project.get("overview") or "尚未记录项目概览"),
             f'更新时间：{progress["generated_at"]}',
             f'已记录功能 {totals["known_features"]} 项；完成 {totals["completed_features"]} 项；工作上下文 {totals["contexts"]} 个。']
    if totals["completion_ratio"] is None:
        lines.append("项目完整范围尚未确认；以上为已登记范围，不推算整个项目的完成百分比。")
    else:
        lines.append(f'已确认计划完成比例：{totals["completion_ratio"]:.0%}')
    lines += ["", "| 功能 | 状态 | 主线集成 | 上下文数 | 阻塞 |", "|---|---|---|---:|---|"]
    for row in progress["features"]:
        lines.append(f'| {cell(row["title"])} | {LABELS[row["status"]]} | {INTEGRATION[row["integration"]]} | {row["context_count"]} | {cell("；".join(row["blockers"]) or "无")} |')
    lines += ["", "## 目标与里程碑"]
    for goal in progress["goals"]:
        lines.append("- 目标：" + cell(goal["title"]))
    for item in progress["milestones"]:
        lines.append(f'- {cell(item["title"])}：{item["completed"]}/{item["total"]}')
    lines += ["", "## 功能明细与下一步"]
    for row in progress["features"]:
        lines.append(f'### {cell(row["title"])}')
        for item in row["contexts"]:
            lines.append(f'- {item["context_id"]}；{cell(item["branch_ref"] or "非 Git")}；{LABELS[item["status"]]}；状态：{cell(item["state_path"])}')
            if item["next_focus"]:
                lines.append("  用户安排：" + cell(item["next_focus"]["text"]))
            if item["suggested_next"]:
                lines.append("  待确认建议：" + cell(item["suggested_next"]["text"]))
    lines += ["", "## 项目约定"]
    for fact in project.get("facts", []):
        lines.append(f'- [{fact["source"]}] {cell(fact["content"])}；引用：{cell(", ".join(fact["references"]))}')
    if progress["invalid_records"]:
        lines += ["", "## 需处理的问题"] + ["- " + cell(item["state_path"]) + "：" + item["error"] for item in progress["invalid_records"]]
    lines += ["", "本总览由项目计划和各功能状态生成；修改事实请更新对应源记录。"]
    return "\n".join(lines) + "\n"


def inspect(api, ctx, full=False):
    project, states, errors, manifest = collect(api, ctx)
    path = api.safe(ctx["storage_root"], "progress.json")
    if not path.exists():
        return {"status": "missing", "known_features": len({state["feature_id"] for _, state in states}), "invalid_records": errors}
    try:
        progress = api.C.read_json(path)
        if not isinstance(progress, dict) or progress.get("schema_version") != 1:
            return {"status": "stale", "error": "汇总格式无效，可从事实源重建"}
        expected = build(api, ctx, project, states, errors, manifest)
        payload = {key: value for key, value in progress.items() if key not in {"revision", "generated_at"}}
        valid_payload = api.C.canonical(payload) == api.C.canonical(expected)
        stale = not valid_payload or type(progress.get("revision")) is not int or not isinstance(progress.get("generated_at"), str)
        summary = api.safe(ctx["storage_root"], "project_summary.md")
        summary_state = "missing" if not summary.exists() else "current" if summary.read_text(encoding="utf-8-sig") == render(api, project, progress) else "stale"
        result = {"status": "stale" if stale else "current", "summary": summary_state, "revision": progress["revision"], "totals": progress["totals"]}
        if full:
            result["record" if not stale else "preview"] = progress if not stale else expected
        return result
    except (api.C.HandoverError, TypeError, KeyError, ValueError):
        return {"status": "stale", "error": "汇总损坏，可从事实源重建"}


def refresh(api, ctx, token, timeout=5):
    api.writable(ctx, token)
    with api.locked(ctx["storage_root"], timeout):
        api.writable(ctx, token)
        for _ in range(3):
            project, states, errors, manifest = collect(api, ctx)
            signature = api.C.digest(manifest)
            expected = build(api, ctx, project, states, errors, manifest)
            target = api.safe(ctx["storage_root"], "progress.json")
            previous = None
            if target.exists():
                try:
                    previous = api.C.read_json(target)
                except api.C.HandoverError:
                    pass
            if (isinstance(previous, dict) and type(previous.get("revision")) is int and isinstance(previous.get("generated_at"), str) and
                    api.C.canonical({key:value for key,value in previous.items() if key not in {"revision", "generated_at"}}) == api.C.canonical(expected)):
                progress = previous
                action = "unchanged"
            else:
                progress = expected
                progress["revision"] = previous.get("revision", 0) + 1 if isinstance(previous, dict) and type(previous.get("revision")) is int else 1
                progress["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                action = "refreshed"
            if collect(api, ctx)[3] != manifest:
                continue
            api.assert_context(ctx, token)
            if action != "unchanged":
                api.write_json(ctx["storage_root"], "progress.json", progress)
            summary = render(api, project, progress)
            path = api.safe(ctx["storage_root"], "project_summary.md")
            if not path.exists() or path.read_text(encoding="utf-8-sig") != summary:
                api.atomic(ctx["storage_root"], "project_summary.md", summary)
            return {"action": action, "revision": progress["revision"], "totals": progress["totals"]}
        api.C.fail("其他功能持续更新，汇总暂时过期；稍后执行 refresh，事实源已保留", 5)
