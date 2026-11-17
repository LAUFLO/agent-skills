# 中文 Agent Skills

这个仓库集中存放可复用的中文 Agent Skill，当前包含两个：

- `auto-gen-testcase-from-req`：需求文档 → 可执行功能测试用例
- `handover`：会话接续与项目控制面

## 包含的 Skill

### auto-gen-testcase-from-req

从系统需求文档生成可追溯、可直接执行的标准 Markdown 功能测试用例。

该目录从本机现有 Skill 原样同步，不在本仓库发布过程中修改其内容。

### handover

会话接续与项目控制面 Skill（v4.0），自动接续项目并汇总总进度：新会话先看总览，再按明确任务恢复当前功能；任务完成、确认阻塞或决策、收工时保存并更新总览。适用于 `/handover`、会话交接、状态同步、收工、下一阶段等场景。

- 核心为 `scripts/handover.py`，Python 3.10+ 且仅用标准库；Codex / OpenCode / Claude Code 共用同一核心与数据协议
- 项目根 `.handover/` 存放配置与状态（Git 项目实际存到公共 Git 目录，工作区根提供同名链接入口）；`project_summary.md` 面向用户展示总进度，`progress.json` 为机器可读汇总
- 按功能 ID 与「工作区 / 分支」隔离，工作上下文 ID 来自工作区和分支而非会话 ID，支持跨会话、跨 agent、多 worktree 接续
- 状态机：pending / in_progress / implemented / verified / blocked / cancelled；用户确定的安排存 `next_focus`，待确认建议单独存 `suggested_next`
- 兼容新老项目：`inspect` 记录初始现状，`migrate` / `adopt` 识别并迁移旧 v3 / v2 / v1 目录，冲突不覆盖、来源不删除
- 模式 `auto` / `restore-only` / `off`；原子写、版本与上下文校验、常见凭据脱敏

## 使用方式

将目标 Skill 文件夹复制到本机 Skill 目录，例如：

```text
%USERPROFILE%\.codex\skills\
```

重新打开客户端后即可按 Skill 的触发描述使用。
