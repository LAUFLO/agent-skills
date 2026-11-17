"""Shared validation, conservative legacy migration, redaction and rendering."""
import copy
import hashlib
import json
from pathlib import Path
import re

SCHEMA = json.loads((Path(__file__).resolve().parent.parent / "references/legacy-v2.schema.json").read_text(encoding="utf-8"))

class HandoverError(Exception):
    def __init__(self, message, code=2, **details):
        super().__init__(message)
        self.code, self.details = code, details


def fail(message, code=2, **details):
    raise HandoverError(message, code, **details)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=lambda _: fail("JSON 不允许 NaN 或 Infinity"))
    except json.JSONDecodeError as error:
        fail(f"JSON 格式错误：第 {error.lineno} 行，第 {error.colno} 列；未覆盖原文件")


def validate_schema(value, schema=None, location="state", root_schema=None):
    """Evaluate the JSON Schema keywords used by the bundled contract."""
    root_schema = SCHEMA if root_schema is None else root_schema
    schema = root_schema if schema is None else schema
    if "$ref" in schema:
        target = root_schema
        for part in schema["$ref"].split("/")[1:]:
            target = target[part]
        return validate_schema(value, target, location, root_schema)
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            try:
                validate_schema(value, branch, location, root_schema)
                return
            except HandoverError:
                pass
        fail(f"{location} 不符合字段结构或来源约定")
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    checks = {"object": isinstance(value, dict), "array": isinstance(value, list),
              "string": isinstance(value, str), "integer": type(value) is int,
              "null": value is None, "boolean": type(value) is bool}
    if types and not any(checks.get(kind, False) for kind in types):
        fail(f"{location} 类型不符合约定")
    if "enum" in schema and value not in schema["enum"]:
        fail(f"{location} 不在允许取值中")
    if "minimum" in schema and value < schema["minimum"]:
        fail(f"{location} 小于允许下限")
    if isinstance(value, str) and "minLength" in schema and len(value.strip()) < schema["minLength"]:
        fail(f"{location} 不能为空")
    if isinstance(value, dict):
        if any(key not in value for key in schema.get("required", [])):
            fail(f"{location} 缺少必需字段")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                validate_schema(value[key], child, f"{location}.{key}", root_schema)
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate_schema(item, schema["items"], f"{location}[{index}]", root_schema)


def validate_state(state):
    validate_schema(state)
    for collection in ("frontier", "gates", "lessons"):
        ids = [item["id"] for item in state[collection]]
        if len(ids) != len(set(ids)):
            fail(f"{collection} 存在重复 id；请合并到原记录")
    todo_ids = {todo["id"] for todo in state["frontier"]}
    for index, todo in enumerate(state["frontier"]):
        verification = todo["verification"]
        if verification["status"] == "passed" and not ((verification.get("method") or "").strip() and verification.get("evidence")):
            fail(f"frontier[{index}] 的验证通过记录必须附方法和证据引用")
        if todo["status"] == "verified" and verification["status"] != "passed":
            fail(f"frontier[{index}] 尚未验证通过，不能标记 verified")
        if todo["status"] in {"blocked", "cancelled"} and not (todo.get("reason") or "").strip():
            fail(f"frontier[{index}] 的阻塞或取消状态必须说明原因")
    for gate in state["gates"]:
        if not set(gate["blocked_todos"]).issubset(todo_ids):
            fail("gate 引用了不存在的 todo id")


def empty_state():
    return {"schema_version": 2, "version": 0, "updated_at": None, "phase": None,
            "frontier": [], "gates": [], "lessons": [], "next_focus": None, "suggested_next": None}


def migrate_legacy(raw):
    """Conservative in-memory migration; never infer user approval or test success."""
    state = copy.deepcopy(raw)
    state["schema_version"] = 2
    state.setdefault("updated_at", None)
    state.setdefault("phase", None)
    for key in ("frontier", "gates", "lessons"):
        state.setdefault(key, [])
        if not isinstance(state[key], list):
            fail(f"旧版 {key} 结构无法可靠迁移；请先人工核对，原文件未修改")
    phase = state["phase"]
    if isinstance(phase, (str, int)) and not isinstance(phase, bool):
        state["legacy_phase"] = phase
        state["phase"] = {"id": str(phase), "goal": None}
    elif isinstance(phase, dict):
        phase.setdefault("id", None)
        phase.setdefault("goal", None)
        if type(phase["id"]) is int:
            phase["id"] = str(phase["id"])
    aliases = {"todo": "pending", "open": "pending", "doing": "in_progress", "active": "in_progress",
               "done": "implemented", "completed": "implemented", "terminal": "implemented", "canceled": "cancelled"}
    for index, original in enumerate(state["frontier"]):
        todo = {"title": original} if isinstance(original, str) else copy.deepcopy(original)
        if not isinstance(todo, dict):
            fail("旧版 todo 结构无法可靠迁移；原文件未修改")
        todo.setdefault("title", todo.get("content", todo.get("description")))
        todo.setdefault("id", "legacy-" + digest(todo)[:12])
        if type(todo["id"]) is int:
            todo["id"] = str(todo["id"])
        old_status = todo.get("status", "terminal" if todo.get("terminal") is True else "pending")
        if not isinstance(old_status, str):
            fail("旧版 todo 状态无法可靠迁移；原文件未修改")
        todo["status"] = aliases.get(old_status, old_status)
        verification = todo.get("verification", {"status": "not_run"})
        if not isinstance(verification, dict) or verification.get("status") not in {"not_run", "passed", "failed"}:
            todo["legacy_verification"] = verification
            verification = {"status": "not_run"}
        if verification["status"] == "passed" and not (verification.get("method") and verification.get("evidence")):
            todo["legacy_verification"] = verification
            verification = {"status": "not_run"}
        todo["verification"] = verification
        if todo["status"] == "verified" and verification["status"] != "passed":
            todo["status"] = "implemented"
        if todo["status"] in {"blocked", "cancelled"}:
            todo.setdefault("reason", "旧记录未注明原因，待核实")
        if todo["status"] != old_status:
            todo["legacy_status"] = old_status
        state["frontier"][index] = todo
    for index, original in enumerate(state["lessons"]):
        lesson = {"content": original} if isinstance(original, str) else copy.deepcopy(original)
        if not isinstance(lesson, dict):
            fail("旧版 lesson 结构无法可靠迁移；原文件未修改")
        lesson.setdefault("id", "legacy-" + digest(lesson)[:12])
        lesson.setdefault("category", "engineering")
        lesson.setdefault("source", "legacy")
        state["lessons"][index] = lesson
    for gate in state["gates"]:
        if not isinstance(gate, dict):
            fail("旧版 gate 结构无法可靠迁移；原文件未修改")
        gate.setdefault("id", "legacy-" + digest(gate)[:12])
        gate.setdefault("reason", gate.get("content"))
        gate.setdefault("resolve", None)
        gate.setdefault("blocked_todos", [])
    focus = state.get("next_focus")
    state.setdefault("suggested_next", None)
    if focus is not None:
        if not (isinstance(focus, dict) and focus.get("source") == "user" and focus.get("basis")):
            state["legacy_next_focus"] = copy.deepcopy(focus)
            text = focus if isinstance(focus, str) else focus.get("text") if isinstance(focus, dict) else None
            if not isinstance(text, str) or not text.strip():
                fail("旧版 next_focus 无法可靠迁移；原文件未修改")
            if state["suggested_next"] is None:
                state["suggested_next"] = {"text": re.sub(r"^建议[：:]\s*", "", text), "source": "legacy", "basis": "旧记录未提供可核对的用户指示来源，尚未确认"}
            state["next_focus"] = None
    else:
        state["next_focus"] = None
    validate_state(state)
    return state


SECRET_KEYS = {"apikey", "password", "secret", "token", "accesstoken", "refreshtoken", "privatekey", "connectionstring", "databaseurl", "dburl", "dsn"}


SECRET_PATTERNS = [
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)(?:api[_ -]?key|password|secret|token|connection[_ -]?string)\s*[:=]\s*[\"']?[^\s\"'&,;]+"),
    re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@[^\s]+"),
    re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"),
    re.compile(r"(?<![A-Za-z0-9])(?:[1-9]\d{16}[\dXx]|1[3-9]\d{9})(?![A-Za-z0-9])")
]


def redact(value):
    count = 0

    def text(value):
        nonlocal count
        for pattern in SECRET_PATTERNS:
            value, changes = pattern.subn("<REDACTED>", value)
            count += changes
        return value

    def walk(item):
        nonlocal count
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                clean_key = text(key)
                if clean_key in result:
                    fail("脱敏后的字段名发生冲突；未写入")
                if re.sub(r"[^a-z]", "", key.lower()) in SECRET_KEYS and child not in (None, "<REDACTED>"):
                    result[clean_key] = "<REDACTED>"
                    count += 1
                else:
                    result[clean_key] = walk(child)
            return result
        if isinstance(item, list):
            return [walk(child) for child in item]
        return text(item) if isinstance(item, str) else item

    cleaned = walk(value)
    return cleaned, count


def line(value, limit=100):
    value = " ".join(str(value).split())
    return value if len(value) <= limit else value[:limit - 1] + "…"


def render_projections(state):
    marker = f'<!-- handover schema_version=3 state_version={state["version"]} state_sha256={digest(state)} -->\n'
    boot = ["# 功能接续", "功能：" + line(state.get("feature_id", "未知"), 35)]
    if state["next_focus"]:
        boot.append("用户确定的下一步：" + line(state["next_focus"]["text"], 100))
    if state["suggested_next"]:
        boot.append("待确认建议（不代表授权）：" + line(state["suggested_next"]["text"], 80))
    if state["phase"]:
        boot.append("阶段：" + line(state["phase"].get("goal") or state["phase"].get("id") or "未知", 70))
    active = [todo for todo in state["frontier"] if todo["status"] not in {"verified", "cancelled"}]
    for todo in active[:3]:
        boot.append(f'- {line(todo["id"], 20)} [{todo["status"]}] {line(todo["title"], 55)}')
    for gate in state["gates"][:2]:
        boot.append("阻塞：" + line(gate["reason"], 55))
    for lesson in state["lessons"][-3:]:
        boot.append(f'经验（{lesson["source"]}）：{line(lesson["content"], 45)}')
    footer = "完整事实与证据见 state.json；本轮用户指示优先。"
    while len("\n".join(boot + [footer])) > 500:
        boot.pop()
    boot_text = marker + "\n".join(boot + [footer]) + "\n"
    summary = ["# 功能概览", line(state.get("overview") or "尚未记录项目概览", 400), "", "## 下一步来源"]
    summary.append("用户确定：" + (line(state["next_focus"]["text"], 300) if state["next_focus"] else "未指定"))
    summary.append("待确认建议：" + (line(state["suggested_next"]["text"], 300) if state["suggested_next"] else "无"))
    summary.extend(["", "## 当前阶段", canonical(state["phase"]), "", "## 事项与验证"])
    for todo in state["frontier"]:
        summary.append(f'- {line(todo["id"])} [{todo["status"]}; 验证={todo["verification"]["status"]}] {line(todo["title"], 250)}')
        if todo.get("reason"):
            summary.append("  原因：" + line(todo["reason"], 250))
        for reference in todo["verification"].get("evidence", []):
            summary.append("  证据引用：" + line(reference, 250))
    summary.extend(["", "## 阻塞与解除方式"])
    for gate in state["gates"]:
        summary.append(f'- {line(gate["reason"], 250)}；解除：{line(gate["resolve"] or "待核实", 200)}')
    summary.extend(["", "## 经验与约定"])
    for lesson in state["lessons"]:
        summary.append(f'- [{lesson["category"]}/{lesson["source"]}] {line(lesson["content"], 350)}')
    summary.extend(["", "## 工件引用"] + ["- " + line(item, 300) for item in state.get("artifacts", [])])
    summary.append("\n本文件由 state.json 派生；修改请通过保存工具更新状态。")
    return {"boot-packet.md": boot_text, "feature_summary.md": marker + "\n".join(summary) + "\n"}
