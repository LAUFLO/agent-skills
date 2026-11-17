"""Publish the neutral project entry without deleting legacy records."""
import base64
from datetime import datetime
import os
from pathlib import Path
import subprocess


def _link(store, entry):
    if os.name == "nt":
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        script = "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path " + quote(entry) + " -Target " + quote(store) + " | Out-Null"
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                                capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise OSError("无法建立项目 .handover 目录入口")
    else:
        entry.symlink_to(store, target_is_directory=True)


def publish(api, ctx, allow_archive=False):
    if not ctx["is_git"]:
        return {"entry": ctx["entry_path"], "storage": ctx["storage_root"]}
    root, entry, store = Path(ctx["workspace_root"]), Path(ctx["entry_path"]), Path(ctx["storage_root"])
    archive = None
    with api.locked(store):
        if entry.exists() or entry.is_symlink():
            if entry.resolve() == store.resolve():
                return {"entry": str(entry), "storage": str(store)}
            if entry.is_symlink() or entry.resolve() != entry.absolute():
                api.C.fail("现有 .handover 链接不属于本仓库，未改写", 7)
            if not entry.is_dir():
                api.C.fail("现有 .handover 不是目录，未改写", 8)
            config_only = all(item.name == "config.json" for item in entry.iterdir())
            if not allow_archive and not config_only:
                api.C.fail("项目根已有真实 .handover；请核对迁移后再建立共享入口", 8)
            # Both source and destination are explicitly within this workspace.
            archive = api.safe(root, ".handover.archive-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            if entry.parent.resolve() != root.resolve() or archive.parent != root.resolve() or archive.exists():
                api.C.fail("归档路径边界不符合预期", 8)
            ledger_path = api.safe(store, "evidence/entry-archives.json")
            ledger = api.C.read_json(ledger_path) if ledger_path.exists() else {"entries": []}
            ledger["entries"].append({"original": str(entry), "archive": str(archive), "workspace_id": ctx["identity"]["workspace_id"]})
            api.write_json(store, "evidence/entry-archives.json", ledger)
            old_config = entry / "config.json"
            if old_config.exists() and not api.safe(store, "config.json").exists():
                config = api.C.read_json(old_config)
                api.write_json(store, "config.json", api.C.redact(config)[0])
            entry.rename(archive)
            migration_path = api.safe(store, "evidence/layout-migration.json")
            if migration_path.exists():
                migration = api.C.read_json(migration_path)
                updated_sources = {}
                for key, source in migration.get("sources", {}).items():
                    if Path(source["root"]).absolute() == entry.absolute():
                        source = {**source, "root": str(archive)}
                        key = api.C.digest(str(archive))[:16]
                    updated_sources[key] = source
                migration["sources"] = updated_sources
                migration["source_signature"] = api.C.digest(updated_sources)
                api.write_json(store, "evidence/layout-migration.json", migration)
        try:
            _link(store, entry)
        except (OSError, subprocess.TimeoutExpired):
            if entry.exists() and entry.resolve() == store.resolve():
                pass
            else:
                if archive is not None and not entry.exists():
                    archive.rename(entry)
                raise OSError("项目 .handover 入口创建失败；事实源在返回的 storage_root，原数据已保留")
        common = Path(ctx["git_common_root"])
        exclude = api.safe(common, "info/exclude")
        previous = exclude.read_text(encoding="utf-8-sig") if exclude.exists() else ""
        patterns = ["/.handover", "/.handover.archive-*"]
        updated = previous
        for pattern in patterns:
            if pattern not in previous.splitlines():
                updated = updated.rstrip("\n") + "\n" + pattern + "\n"
        if updated != previous:
            api.atomic(exclude.parent, exclude.name, updated)
    return {"entry": str(entry), "storage": str(store), "archived_entry": str(archive) if archive else None}
