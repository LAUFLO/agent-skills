# 中文 Agent Skills

这个仓库集中存放可复用的中文 Agent Skill。

## 包含的 Skill

### pixel-winforms-ui

为 Windows WinForms 应用建立纯白背景、粗像素边框、统一控件、DPI、多屏和无闪烁刷新规范，并提供可复制的 C# 主题模板。

### auto-gen-testcase-from-req

从系统需求文档生成可追溯、可直接执行的标准 Markdown 功能测试用例。

该目录从本机现有 Skill 原样同步，不在本仓库发布过程中修改其内容。

### handover

会话接续与项目控制面 Skill（原 trae-kanban 重构），让新会话一秒接续。适用于 `/handover`、会话交接、状态同步、看板更新、收工等场景。

- 单一路径 `.opencode/handover/`，单一真相源 `state.json`
- 语义去重 `contentHash`、版本原子写、按 `frontier` 关键词过滤 `lessons`
- 输入源动态发现（路径来自 AGENTS.md 约定）；boot-packet/project_summary 只读投影不反写

核心机制：Frontier（待办）+ Gate（阻塞）+ Evidence（证据），配合进展信号规范，支持跨 `worktree` 与多项目复用。

### shortfilm-pipeline

AI 短片 / 叙事视频制作工作流总编排 Skill：六阶段路由（P0 剧本开发 → P1 拆场 → P2 分镜锁定 → P3 提示词编写 → P4 生成与台账 → P5 审稿修复）、门禁检查与项目资产目录规则，按需调用 `sw-workflow` 及 sw-* 群（P0 剧本开发层）、`leos-six-department-directing-team-skill-v1`（导演流程）、`shortfilm-prompt`（提示词文法）子 Skill 群；单镜小任务可走快速通道。

- P0 上游剧本开发：只有点子或粗糙剧本时，路由 `sw-workflow`（前提 → 结构 → 人物 → 场景清单 → 处理台本，剧集走 S0–S7 表）产出 `01-plan/script-draft.md`，P0 状态机 `01-plan/story-bible.md` 完成后冻结为存档
- 阶段门禁：各阶段有明确产出目录（`00-source` 至 `05-review`）与出口条件，「阶段移交」行支持跨会话断点续接
- 分镜三件套（subject-registry / atmosphere-lock / shotlist）为唯一真相源；参考图资产绑定编号、版本只增不改
- 冲突裁决写死：提示词文法归 shortfilm-prompt，流程/审稿/台账归 leos，剧本开发层归 sw-workflow，资产/门禁归本 skill；时长/画幅/分辨率只认用户明示

## 使用方式

将目标 Skill 文件夹复制到本机 Skill 目录，例如：

```text
%USERPROFILE%\.codex\skills\
```

重新打开客户端后即可按 Skill 的触发描述使用。
