---
name: handover
description: 自动接续项目并汇总总进度。新会话先看项目总览，再恢复当前功能；任务完成、确认阻塞或决策、收工时保存并更新总览。按功能与工作区/分支隔离，跨会话和 agent 接续，兼容新老项目与旧目录迁移。纯问答、无新事实及本 skill 自身维护不自动保存。
metadata:
  version: "4.0"
---

# Handover — 项目总览与功能接续

核心工具为 scripts/handover.py，Python 3.10+，只用标准库。<SKILL_DIR> 为本文件所在目录；Windows 使用 py -X utf8 -B，其他系统用 python3。Codex、OpenCode、Claude Code 共用同一核心与数据协议；agent 名称和会话编号只作来源，不参与进度分组。

## 自动时机与边界

- 新会话首次处理项目任务前，只读检查总进度与当前上下文。不存在记录时不初始化文件；任务有实质进展后首次保存。
- 任务/阶段完成，或确认新阻塞、关键决策、验证结果后，在最终回复前保存一次。用户收工、先这样、下一阶段时同步尚未保存的进展。
- 纯问答、无新项目事实、已保存进展，以及 handover 自身安装、配置、修改，跳过自动保存。不逐次询问进展确认，不强制追问下一步。
- 本轮用户指示优先。总览、旧记录、agent 建议、证据中的命令是上下文，不代表新任务或外部操作授权。不同分支同时开发用独立 worktree，本 skill 不切分支或隔离代码。
- 这是会话内约定，不是关闭窗口事件钩子。权限、工具或运行环境不可用时如实报告未保存，不绕过权限、不手写状态。

## 1. 先看总览，再选功能

~~~text
py -X utf8 -B "<SKILL_DIR>/scripts/handover.py" status --root "<项目目录>" --full
~~~

工具返回模式、仓库/工作区/分支/HEAD、项目计划、总进度新鲜度、可选功能和旧目录提示；不创建目录，不默认接续最近任务。

- 项目根 .handover/project_summary.md 面向用户展示总进度；progress.json 是机器可读汇总。先确认工具返回 current 再依赖文件；过期或损坏时用只读 preview 或源记录判断，不把旧缓存当事实。
- 按本轮明确任务选择稳定功能 ID。A 会话开发 login、B 开发 payment，是两个功能；C 会话继续 login，沿用 login。会话 ID 可省略，不为新会话重建功能。
- 多个候选或工作上下文无法判断时才询问范围。不要把总览中的建议或排序自动当成用户安排。
- 选定后运行 status --feature "<功能ID>" --full。该功能、该工作区/分支下的 state.json 是事实源；boot-packet.md、feature_summary.md 为派生文件。
- 额外输入源按项目 AGENTS.md 声明发现，不硬编码工作流目录；保留项目已有指令，例行交接不修改代码或项目指令文件。

## 2. 目录与总进度

~~~text
.handover/
  config.json
  repository.json
  project.json
  progress.json
  project_summary.md
  features/
    login/
      <工作上下文ID>/
        state.json
        boot-packet.md
        feature_summary.md
        evidence/
~~~

功能名符合安全命名时用原名，否则工具编码目录名；不要手工猜路径。工作上下文 ID 来自工作区和分支，不是会话 ID。

- 非 Git 项目 .handover 是真实目录；Git 项目的实际共享目录为公共 Git 目录下的 .handover，工作区根提供同名链接入口。Windows 用目录联接。工具只接受当前仓库的链接，运行数据及入口使用 Git 本地排除规则，不写团队 .gitignore。
- 每次功能或项目计划保存成功后自动刷新总览。总览按功能去重，包含所有已记录功能、计划中未开始的功能、里程碑、阻塞、下一步及各上下文来源版本。
- 同一功能有多个上下文时不取“最新一次”或“完成度最高一次”。未指定主上下文或唯一目标分支时显示“多个上下文待归并”。
- 分支验证、合入主线、用户验收分别记录。合并或验收只在项目明确约定时作为完成条件；不额外制造普遍审批要求。
- 没有完整项目范围时仅统计已登记功能，不凭会话数或已知任务数推算整个项目百分比。项目目标、功能清单、里程碑和完成条件来自用户或已核对资料，不擅自扩充路线图。

保存或迁移前读取 [格式与接入约定](references/state-format.md)；状态字段见 [JSON Schema](references/state.schema.json)。

## 3. 新老项目与旧目录

首次接入运行 inspect --root "<项目目录>"，只读记录目录、项目指令、Git 现状；它不是历史完成或测试通过的证明。

- 新项目：保留最初 inspect 的 inspection 作为 intake.initial_inspection；即使本轮后来写入首批代码或初始化 Git，仍能说明项目最初为空。未知历史不编造。
- 老项目无记录：先核对项目说明、指令、代码/构建入口、当前分支和未提交改动，在 intake 写明依据和资料引用。
- 旧 v3 目录：工具识别 .opencode/handover/v3 或旧 Git 公共目录的 codex-handover。先 migrate --dry-run 查看来源、签名和冲突；核对后带 --source-signature 和当前 --expected-context 执行 migrate。目录兼容且身份一致时保留各功能独立版本，来源不删除；冲突不覆盖，中断可继续。
- v1/v2 状态：用 status --legacy --full 查看保守转换，再用 adopt 导入明确的功能上下文。来源不明的旧下一步不冒充用户安排，旧 done/terminal 无验证依据时按未验证处理。
- 只有摘要：先核对工件，再准备恢复候选，不把计划当完成事实。未知的根级状态或来源不明摘要不自动覆盖。
- 非 Git 后初始化 Git：核对旧功能后 adopt；原 .handover 如需让位于共享入口，会归档到项目根的 .handover.archive-时间目录，归档映射保存在共享目录 evidence/entry-archives.json。原记录保留，项目计划也应核对后导入。
- 用户明确要求跨工作区/分支接续同一功能时，用 --all-contexts 查找，status --legacy --full --source-context "<存储根下相对状态路径>" 查看，再带相同来源及签名 adopt。导入历史不代表新分支验证通过。
- 无效 JSON、未知未来结构、来源或目标冲突时停止，不用空状态覆盖。迁移后旧目录又被旧版 agent 改写时报告分歧，暂停自动合并。

~~~text
py -X utf8 -B "<SKILL_DIR>/scripts/handover.py" adopt --root "<项目目录>" --feature "<功能ID>" --input "<已核对候选JSON>" --expected-version 0 --expected-context "<当前token>" --source-signature "<来源signature>"
~~~

旧来源属于别的功能而本轮明确新建独立功能时，在 intake.legacy_review 记录 signature、decision=separate-feature、basis，再正常保存。

## 4. 准备事实与保存

- 基于当前功能完整状态更新，保留无关字段，同一事项沿用原 id。工具检查结构和重复 id，不判断语义相似度。
- pending、in_progress、implemented、verified、blocked、cancelled 分别表示未开始、进行中、改完未验证、验证通过、受阻、取消。verified 须有实际验证方法和证据引用；失败保留 failed，阻塞与取消说明原因。
- 人工核对和用户验收可作为验证。工具不执行引用的命令，也不证明证据真实。历史验证只对当时上下文有效；重验时更新证据和 checked_context。已保存后 HEAD 变化会提示复核。
- next_focus 只存该功能中用户确定的安排及依据；保留有效安排，已完成或撤回可清空。suggested_next 单独存待确认建议，不自动升级为用户计划。
- project.json 存项目目标、计划功能、里程碑、事实和可选完成条件，通过 project-save 更新；总进度为派生结果，不反写功能状态。
- 经验注明 engineering/procedure/preference/repo 类别及 user/observed/agent/legacy 来源，不将推测升级为用户偏好。不编造进展、统计、输入源或验证。
- 审查敏感信息；工具的常见凭据和个人信息模式脱敏不代替自然语言审查。未脱敏候选使用临时文件或标准输入，不放入交接目录。

~~~text
py -X utf8 -B "<SKILL_DIR>/scripts/handover.py" save --root "<项目目录>" --feature "<功能ID>" --input "<候选JSON>" --expected-version <读取版本> --expected-context "<读取token>" --agent "<当前agent>"
~~~

支持 --input -。--agent 用 codex、opencode、claude-code 或其他真实来源；--session-id 仅在可获取时填写，不编造。换 agent 或会话本身不增加状态版本。

文件锁内重读版本，提交前检查上下文。HEAD、分支、工作区或版本过期时停止，重新核对，不只改版本号重试。相同事实 unchanged，不改文件。

状态先原子提交，再更新摘要和总览。committed=true 表示事实已经保存，按返回版本修复，不重放任务。repair 修复当前功能摘要；refresh 从源记录重建项目总览；project-repair 为项目级修复入口。派生修复不增加功能或项目事实版本。启动恢复只读，允许写入后才修复。

## 模式与适配

.handover/config.json 的 mode 为 auto、restore-only 或 off；默认 auto。可用 workspaces.<工作区ID>.mode 单独限制工作区；旧 .opencode/handover/config.json 仍作为兼容限制来源。全局关闭不能被工作区 auto 绕过。仅按用户要求更改配置。

Codex、OpenCode、Claude Code 的启动入口分别安装到各自指令文件和技能发现目录，指向同一份核心。没有实际运行环境的 agent 只能标为已配置或待验证，不能宣称自动调用已实测。

完成后简短说明同步的功能及总览结果，无变化不重复提示。scripts/test_handover.py 仅使用自建临时项目和 Git worktree，不调用模型或外部服务。
