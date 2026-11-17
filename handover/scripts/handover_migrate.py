"""Preview and copy known v3 layouts; never overwrite diverging target facts."""
import copy
import hashlib
import json
from pathlib import Path


def source_snapshot(api, root):
    root = Path(root).resolve()
    paths = list(root.glob("contexts/*/*/*/state.json")) + list(root.glob("features/*/*/state.json"))
    for name in ("project.json", "repository.json", "config.json"):
        if api.safe(root, name).exists():
            paths.append(api.safe(root, name))
    files = {}
    for path in sorted(set(paths)):
        path = api.safe(root, str(path.relative_to(root)))
        files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def roots(api, ctx):
    values = list(ctx.get("legacy_storage_roots", []))
    archives = api.safe(ctx["storage_root"], "evidence/entry-archives.json")
    if archives.exists():
        for item in api.C.read_json(archives).get("entries", []):
            archive = Path(item["archive"])
            if archive.exists() and item.get("workspace_id") == ctx["identity"]["workspace_id"]:
                values.append(str(archive))
    return sorted(set(value for value in values if Path(value).exists() and Path(value).resolve() != Path(ctx["storage_root"]).resolve()))


def preview(api, ctx):
    stores = []
    sources = {}
    for value in roots(api, ctx):
        root = Path(value)
        marker = api.safe(root, "repository.json")
        if not marker.exists():
            continue
        record = api.C.read_json(marker)
        snapshot = source_snapshot(api, root)
        source_id = api.C.digest(str(root))[:16]
        sources[source_id] = {"root": str(root), "files": snapshot}
        stores.append({"source_root": str(root), "records": sum(name.endswith("/state.json") for name in snapshot),
                       "compatible_identity": record.get("repository_id") == ctx["identity"]["repository_id"]})
    receipt = api.safe(ctx["storage_root"], "evidence/layout-migration.json")
    migrated = api.C.read_json(receipt).get("source_signature") if receipt.exists() else None
    signature = api.C.digest(sources) if sources else None
    return {"stores": stores, "sources": sources, "source_signature": signature,
            "status": "none" if not sources else "migrated" if migrated == signature else "review_required",
            "pending": api.safe(ctx["storage_root"], ".migration.pending.json").exists()}


def guard(api, ctx):
    if ctx.get("migration_operation"):
        return
    if api.safe(ctx["storage_root"], ".migration.pending.json").exists():
        api.C.fail("目录迁移尚未完成；先按已核对来源继续 migrate，不覆盖部分记录", 8)
    receipt = api.safe(ctx["storage_root"], "evidence/layout-migration.json")
    if receipt.exists():
        old = api.C.read_json(receipt)
        for source in old.get("sources", {}).values():
            root = Path(source["root"])
            if not root.exists() or source_snapshot(api, root) != source["files"]:
                api.C.fail("迁移后的旧目录再次变化或无法核对；请检查旧 agent 写入，暂停自动合并", 8)


def run(api, ctx, token, signature, dry_run=False, timeout=5):
    report = preview(api, ctx)
    if dry_run:
        return {"action": "migration-preview", **report}
    work = {**ctx, "migration_operation": True}
    api.writable(work, token)
    if not report["sources"]:
        api.C.fail("未发现可迁移的旧版目录")
    if signature != report["source_signature"]:
        api.C.fail("迁移来源签名已变化；请重新预览核对", 8)
    if any(not store["compatible_identity"] for store in report["stores"]):
        api.C.fail("来源工作区身份不同；请按功能 adopt 并核对项目计划，不能整目录自动重绑", 8)
    with api.locked(ctx["storage_root"], timeout):
        api.writable(work, token)
        again = preview(api, ctx)
        if again["source_signature"] != signature:
            api.C.fail("迁移来源已变化，未写入", 8)
        planned = {}
        for source in report["sources"].values():
            root = Path(source["root"])
            for name in source["files"]:
                path = api.safe(root, name)
                if name.endswith("/state.json"):
                    state = api.C.read_json(path)
                    api.validate_feature(state)
                    if state["identity"]["repository_id"] != ctx["identity"]["repository_id"]:
                        api.C.fail("来源功能属于其他仓库，未迁移", 7)
                    directory = api.safe(ctx["storage_root"], "features/" + api.P.feature_path_component(api, state["feature_id"]) + "/" + api.P.context_id(api, state["identity"]))
                    relative = (directory / "state.json").relative_to(Path(ctx["storage_root"])).as_posix()
                    data = api.C.redact(copy.deepcopy(state))[0]
                elif name == "project.json":
                    data = api.C.redact(api.C.read_json(path))[0]
                    api.validate_project(data, ctx)
                    relative = "project.json"
                else:
                    continue
                if relative in planned and api.C.canonical(planned[relative]) != api.C.canonical(data):
                    api.C.fail("多个旧目录含冲突记录，需核对合并", 8)
                target = api.safe(ctx["storage_root"], relative)
                if target.exists() and api.C.canonical(api.C.read_json(target)) != api.C.canonical(data):
                    api.C.fail("新旧记录不一致，迁移不会覆盖目标事实", 3, target=relative)
                planned[relative] = data
        api.write_json(ctx["storage_root"], ".migration.pending.json", {"source_signature": signature, "targets": sorted(planned)})
        api.ensure_repository(ctx)
        for relative, data in planned.items():
            target = api.safe(ctx["storage_root"], relative)
            if not target.exists():
                api.write_json(ctx["storage_root"], relative, data)
            if relative.endswith("/state.json"):
                for name, content in api.C.render_projections(data).items():
                    expected = api.safe(target.parent, name)
                    if not expected.exists() or expected.read_text(encoding="utf-8-sig") != content:
                        api.atomic(target.parent, name, content)
        if preview(api, ctx)["source_signature"] != signature:
            api.C.fail("迁移期间旧目录变化；保留已复制记录并暂停，需重新核对", 8)
        api.write_json(ctx["storage_root"], "evidence/layout-migration.json", {"source_signature": signature, "sources": report["sources"], "targets": sorted(planned)})
        api.safe(ctx["storage_root"], ".migration.pending.json").unlink()
    derived = api.finish_save(work, token, timeout, True)
    return {"action": "migrated", "records": sum(name.endswith("/state.json") for name in planned), **derived}
