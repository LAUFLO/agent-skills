# 格式、汇总与迁移约定

## 三类标识

功能 ID 是稳定用户目标，如 login、payment。同一功能可跨会话和 agent 接续。工作上下文由工作区及分支决定；会话 ID 和 agent 名称只记录来源，不参与目录分组，也不重复计数。

Git 公共元数据目录中的 .handover 是共享存储，工作区根 .handover 是经过归属检查的入口；非 Git 项目直接使用项目内 .handover。目录布局版本为 4，功能事实的 schema_version 保持 3，修订号 version 仍独立递增，不创建 v4 子目录。

根目录：

- repository.json：仓库身份与布局版本。
- config.json：模式及可选工作区限制。
- project.json：项目目标、计划、约定，独立事实版本。
- progress.json：自动汇总，可重建，不是事实源。
- project_summary.md：用户日常查看的总进度。
- features/<功能>/<工作上下文>/：state.json、boot-packet.md、feature_summary.md、evidence。

工具返回实际路径。安全的小写功能名使用原名，否则编码。分支重命名不自动合并旧上下文，复制其他功能的 JSON 也不能仅改参数就覆盖目标。

## 功能状态输入

已有功能先读取原状态，不用示例重置：

~~~json
{
  "schema_version":3,
  "phase":null,
  "frontier":[
    {"id":"t1","title":"修改已完成，尚未验证","status":"implemented","verification":{"status":"not_run"}}
  ],
  "gates":[],
  "lessons":[],
  "next_focus":null,
  "suggested_next":null,
  "intake":{
    "kind":"existing-project",
    "basis":"已读项目说明并核对 Git 现状",
    "references":["README.md","git:HEAD"]
  }
}
~~~

工具补入 feature_id、identity、version、updated_at、recorded_context、last_session 等元数据。version 可省略；提供时须等于 expected-version。context_token 绑定工作区、分支、HEAD 和目录，提交或切换后须重新读取。锁只协调交接写入，不锁 Git checkout。

intake.kind 为 new-project、existing-project、new-feature、legacy-import、summary-recovery。老项目首次接入须有资料引用；新项目本轮写入代码后，可附最初 inspect 返回的 inspection 到 intake.initial_inspection，保留最初为空的依据。普通保存不能冒充导入。

状态：

| 值 | 含义 |
|---|---|
| pending | 未开始 |
| in_progress | 进行中 |
| implemented | 修改完成，验证未完成或未通过 |
| verified | 实际验证通过 |
| blocked | 受阻，须有 reason |
| cancelled | 取消，须有 reason |

verification.status 为 not_run、passed、failed；passed 须有 method 和非空 evidence 引用。真实人工核对、验收也可作为验证。引用不是可自动执行的命令，工具不证明引用真实。

通过记录绑定 checked_context、checked_head；原样沿用时保留旧验证环境。重新验证时更新证据或明确给出当前 checked_context。导入记录保留 legacy/context-import 来源，未知环境不冒充当前上下文。

frontier、gates、lessons 组内 id 唯一。gate 要有 id/reason/resolve/blocked_todos，引用存在的 todo。lesson 要有 id/content/category/source，类别 engineering、procedure、preference、repo，来源 user、observed、agent、legacy。

next_focus 只接受 source=user 和明确 basis；agent 建议放 suggested_next，source=agent 或 legacy。用户仍有功能内未完成安排时，总览不会只因现有 todo 全 verified 就自动判为完成。

## 项目计划与总进度

最小 project-save 输入为 {"overview":null,"facts":[]}。已核对 fact 必填 id/content/source/basis/references，来源仅 user 或 observed，引用非空。不要把功能 frontier 或 next_focus 混入项目记录。

可选计划示例：

~~~json
{
  "overview":"首个可用版本",
  "facts":[],
  "scope_complete":true,
  "goals":[{"id":"g1","title":"交付可用版本"}],
  "features":[
    {"id":"login","title":"用户登录","target_branch":"main"},
    {"id":"payment","title":"支付"}
  ],
  "milestones":[{"id":"m1","title":"首发","feature_ids":["login","payment"]}]
}
~~~

scope_complete 仅在用户范围或项目规格足够完整时设置，不能根据现有会话数推断。计划功能即使尚无状态，也显示未开始；未列入计划但已经开发的功能仍显示，并使整体百分比保持未知。

同一功能的多个上下文只算一个功能。需要明确 primary_context（工具返回的上下文 ID），或存在唯一匹配 target_branch 的上下文，才能按该上下文判断完成；否则显示待归并，保留各分支明细，不取最新或最高状态。

完成条件可选 completion.require_merge、completion.require_acceptance。配置 target_branch 时默认需要合入该分支；不配置合并/验收要求时不擅自新增门禁。Git 合并判断要求保存时没有未提交改动，并能证明保存提交已进入目标分支；分支验证通过不等于已合并。必要时可记录有 user/observed 来源及 evidence 的 integration 声明。

显式要求用户验收时，acceptance 使用 status=accepted、source=user、basis；未要求时不强制追问用户。取消独立显示，不当作验证通过；计划范围变更通过 project-save 表达。

progress.json 按功能分组，包含各上下文状态、阻塞、用户安排、待确认建议、源修订与哈希，以及目标、里程碑、总计。源记录或相关 Git 分支变化会使汇总过期。多个 writer 不同功能可独立保存，汇总在项目锁内重新读取，避免漏掉其他功能。

总览自动更新于功能或项目保存后；源事实与派生文件不能一次原子提交，committed=true 时事实保留。refresh 可重建总览，不改变源版本。派生缓存即使格式有效但内容与源不一致，也标为过期并可重建。

## 已知旧目录

- .opencode/handover/state.json 及旧摘要：先只读检查，再按功能 adopt，目标已有状态不覆盖。
- .opencode/handover/v3 和旧 Git 公共目录 codex-handover：migrate --dry-run 查看来源签名、数量和身份；核对后 migrate --source-signature ... --expected-context ...。
- 目录迁移复制已知记录，保留源文件和未知字段，目标内容不同拒绝覆盖；不更改既有事实修订号。中断时 .migration.pending.json 阻止普通写入，同一来源可继续迁移。
- 旧 v1 done/terminal 缺验证依据时保守转 implemented；来源不明的下一步作为 legacy 建议。未知格式和损坏状态不被空记录重置。
- 只有摘要时结合工件核对重建，不把计划当完成。未知的 .handover 根级 state/boot 或来源不明摘要需要先核对归档。
- 非 Git 后初始化 Git或显式跨上下文接续，先查看再 adopt；来源身份不同不能整目录静默重绑。新 Git 入口需要让位时将原真实 .handover 保留到 .handover.archive-时间，并记录归档映射。
- 迁移后的旧目录又有变化会暂停自动合并，避免旧 agent 与新核心写入两份进度。所有 agent 应指向同一份当前核心。

迁移前文件、脱敏来源快照和新事实分别保留，敏感明文不复制到新管理文件。原有源文件不自动删除。目录入口由工具验证，不接受指向其他仓库或任意目录的链接。

## 模式与命令

config.json 支持 mode=auto、restore-only、off；workspaces.<工作区ID>.mode 可单独限制。项目级 off/restore-only 不能被工作区 auto 放宽。旧配置作为兼容限制来源；只有明确工作区配置才替代对应旧限制，不能自行绕过。

status、inspect、migrate --dry-run 只读。save、project-save、adopt 使用事实修订和当前 token。repair 修复功能摘要；refresh 重建项目汇总；project-repair 校验项目版本后刷新总览。所有写入受模式约束。

退出码：0 成功/无变化；2 数据校验；3 修订或迁移冲突；4 模式禁止；5 文件/派生异常；6 锁超时；7 上下文/身份不匹配；8 接入或迁移待核对。agent 和 session 参数只作来源，不能增加功能数量或单独触发事实修订。
