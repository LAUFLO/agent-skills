---
name: shortfilm-pipeline
description: AI 短片/叙事视频制作工作流总编排。负责阶段路由（P0 剧本开发 → P1 拆场 → P2 分镜锁定 → P3 提示词编写 → P4 生成与台账 → P5 审稿修复）、门禁检查、项目资产目录与版本规则。按需调用子 skill：sw-workflow 及 sw-* 群（P0 剧本开发层）、leos 六部门（导演流程）、shortfilm-prompt（提示词文法）。用户说"跑流程/继续/接着上次的短片项目/这个剧本够不够分镜"或进入 AI 短片/叙事视频项目时加载本 skill；单镜小任务走快速通道。
---

# shortfilm-pipeline — AI 短片制作工作流总编排

## 0 · 职责边界

- 本 skill 只管：**阶段路由、门禁、资产规则、断点续接**。不自己写提示词、不自己拆场。
- 拆场 / 表演 / 摄影 / 审稿 / 台账 → 子 skill `leos-six-department-directing-team-skill-v1`
- 提示词文法（5 阶段结构 / 7 硬规则 / 负向提示词 / 模型坑位）→ 子 skill `shortfilm-prompt`
- 剧本开发（前提/结构/人物/场景/对白工艺，P0 层）→ 子 skill `sw-workflow` 及其调度的 sw-* 群（含 `sw-series-engine-bible`、`sw-chinese-series-practice`）

## 1 · 前置检查（进入流程时做一次）

1. 确认子 skill 可用（看 available skills 列表）。缺失则停下，输出安装指引——统一装进 OpenCode 原生全局 skills 目录 `C:\Users\Administrator\.config\opencode\skills\`：
   - leos：`git clone https://github.com/MasterLeos/leos-six-department-directing-team-skill-v1`，整包放到 `C:\Users\Administrator\.config\opencode\skills\leos-six-department-directing-team-skill-v1\`（SKILL.md 必须位于该目录根部，目录名即 skill ID）
   - shortfilm-prompt：`git clone https://github.com/jnMetaCode/ai-shortfilm-prompts`，把仓库内 `skills/shortfilm-prompt/` 拷到 `C:\Users\Administrator\.config\opencode\skills\shortfilm-prompt\`，并把仓库 `templates/` 拷进该目录（模板路径是相对 SKILL.md 解析的）
   - sw-* 子集（9 个）：`git clone https://github.com/jtydhr88/screenwriting-skills`，把仓库 `plugins/screenwriting/skills/` 下的 `sw-workflow`、`sw-premise-theme`、`sw-story-structure`、`sw-character-conflict`、`sw-dialogue`、`sw-scene-craft`、`sw-format-adaptation`、`sw-series-engine-bible`、`sw-chinese-series-practice` 九个整目录拷到 `C:\Users\Administrator\.config\opencode\skills\`（含各自 reference/terms 附属文件）
   - 装完需新开 OpenCode 会话（skill 在会话启动时被发现）
2. 扫描当前项目目录判断入口阶段：
   - 按**内容**判定入口，不按文件位置：素材仅为点子/粗糙草稿（无完整节拍与对白），或已存在 `01-plan/story-bible.md` → **P0**
   - 有完整剧本（具备场次节拍与对白；在 `01-plan/script-draft.md`、`00-source/` 或用户提供均可）→ **P1**
   - 已有 `02-storyboard/` 三件套 → **P3**
   - 已有 `03-prompts/` 但 `04-takes/` 空 → **P4**
   - 已有 `04-takes/` 成片但无 `05-review/` → **P5**
   - 各文件末尾有「阶段移交」行的，以该行为准，不猜
   - 空骨架目录 ≠ 阶段完成：入口判定只认"命名产物文件存在"（如 `02-storyboard/shotlist.md`），目录存在性不作为判定依据
3. 项目初始化（仅首次进入时）：项目根目录缺少资产骨架则自动预建：
   - 建目录：`00-source/` `01-plan/` `02-storyboard/`（含 `assets/subjects/`、`assets/scenes/`）`03-prompts/` `04-takes/` `05-review/`
   - 只建目录 + `00-source/` 放一行 README.md 用途说明，不预写任何假产物
   - **只增不删**：已有目录/文件一律不动；骨架目录名与已有内容冲突时停下，给"认领 / 改名 / 忽略"三选项由用户裁决，记入 `01-plan/` 备注
   - 用户素材归位走"复制 + 保留原件"，不移动不删除

## 2 · 阶段路由表

| 阶段 | 输入 | 加载的子 skill | 产出 | 门禁（全部满足才进下一阶段） |
|---|---|---|---|---|
| P0 剧本开发 | 点子/粗糙剧本 | `sw-workflow`（按其阶段表：前提→结构→人物→场景清单→处理台本；剧集项目走 S0–S7 表，按需调 `sw-series-engine-bible`/`sw-chinese-series-practice`） | `01-plan/story-bible.md`（P0 单文件状态机）+ `01-plan/script-draft.md`（定稿分场大纲/处理台本） | P0 纪律跟 sw-workflow（创作主线不拆 subagent、一次性交付不建 bible、甲方格式优先）；每场有价值转折、人物/卡片数达标；用户确认"剧本够分镜了" |
| P1 拆场 | 剧本（`01-plan/script-draft.md` 或用户提供） | leos（总导演+场记） | `01-plan/scene-XX/brief.md`（按 `templates/scene-brief.md` 填充）、`decisions.md` | 场次目的/主角/节奏/空间关系已锁定；用户逐场确认 |
| P2 分镜锁定 | 场次包 | leos（表演/镜内/摄影三部门简报）+ shortfilm-prompt 的 `templates/project-planner.md` + `agnes-media-generator`（参考图生成） | `02-storyboard/` 三件套（按 shortfilm-prompt `project-planner` 的列结构）、`assets/manifest.md`（按本 skill `templates/asset-manifest.md` 填充） | 主体登记每个复现角色 ≥2 瑕疵锚点；氛围段落定稿；shotlist 每镜 Exit/Entry 对齐；全片 ≤8 镜、单镜 ≤15s（超出后重 roll 成功率崩塌、多段拼接误差累积，见 shortfilm-prompt cheatsheet）；参考图（如需）按 §7 规格生成（定妆照 / 场景图五件套）、subagent 质检合格并登记 manifest；用户确认可先生成首尾镜 |
| P3 提示词编写 | 三件套 | shortfilm-prompt（5 阶段 + 7 硬规则） | `03-prompts/shot-XX-v001.md` | 每个提示词：主体描述从 subject-registry 复制、氛围段从 atmosphere-lock 复制；过 leos 校验脚本（若可用）+ shortfilm-prompt 30 秒清单；版本 vNNN 递增；提示词文件与 shotlist 行一对一（镜号即文件名），内容/运镜/时长与该 shotlist 行一致，改动画面内容先回 P2 改 shotlist 再递增版本，禁止在提示词里加 shotlist 之外的"戏" |
| P4 生成与台账 | 提示词 | leos（场记 Take 登记 + 局部修复原则）+ `agnes-media-generator`（Agnes Video 2.5 Flash，调用纪律见 §7） | `04-takes/shot-XX/` 素材 + `take-ledger.md`（按 `templates/take-ledger.md` 填充） | 先生成首尾两镜锁观感，漂移即停；每镜登记提示词版本 / video_id / seconds / aspect_ratio / seed（如有）/ Take 结论；重 roll 预算 ≈ 5–10 倍终选镜数 |
| P5 审稿修复 | 成片 | leos（六角色逐镜审稿） | `05-review/review.md`（按 `templates/review.md` 填充） | 审稿表为「角色 × 镜头 1..N」全覆盖，无问题的镜头也写"通过"；每镜有 保/过/修/废 结论；"修"的镜头走局部修复（一次只改一个变量）；场记/连续性行必查三一致性：提示词文件 ↔ shotlist 行、提示词版本 ↔ take-ledger、素材 ↔ 场次 brief |

**执行纪律**：每阶段开始时用 `skill` 工具显式加载对应子 skill，不凭记忆操作；阶段内子 skill 的规则优先于本 skill。各阶段产物文件按本 skill `templates/` 下对应模板填充（scene-brief / asset-manifest / take-ledger / review），不自创列结构。
- P0 首会话只执行 sw-workflow 的"启动"一节 + 创建 `01-plan/story-bible.md`（一屏内，不确定项标"（待确认）"）即停——不在单会话跑完整阶段表（防上下文超载与静默断流），后续会话按 bible 的"下一步："推进

## 3 · 快速通道（Fast Lane）

适用：单镜 ≤15s 或纯氛围单镜、不走完整叙事流程的小任务。

- 跳过 P1/P2，直接 **P3（shortfilm-prompt 单镜模式）→ P4**
- 仍需执行：30 秒清单自检、`03-prompts/` + `04-takes/` 目录规则、Take 台账（一行即可）
- 单镜任务可跳过 `02-storyboard/assets/`（不需要参考图时）
- 同一项目内快速通道产出的镜头，若后续要并入多镜叙事，必须回填 `02-storyboard/` 三件套再进 P5

## 4 · 资产图规则（路径均相对项目根目录）

```
my-film/
├── 00-source/            # 用户提供的原始素材（点子/粗糙剧本/参考素材），只读，不修改
├── 01-plan/
│   ├── scene-XX/         # 场次包：brief.md（按 templates/scene-brief.md）+ decisions.md（用户裁决）
│   ├── story-bible.md    # P0 状态机（sw-workflow 约定），P0 完成后冻结为存档
│   └── script-draft.md   # P0 产出：定稿分场大纲/处理台本
├── 02-storyboard/        # 全片一份、镜头级更新的"分镜三件套"
│   ├── shotlist.md       # 逐镜：景别/运镜/内容/Exit/Entry/时长
│   ├── subject-registry.md   # 主体登记表：编号固定，全片不复用改号
│   ├── atmosphere-lock.md    # 氛围段落：只写一次，逐字粘贴
│   └── assets/             # 参考图资产区（输入端，与三件套绑定）
│       ├── subjects/portrait1-v1.png   # 角色定妆图：脸+服装+关键道具，绑定 Portrait 编号
│       ├── scenes/scene-01-v1.png      # 定场/氛围参考图，绑定场次编号
│       └── manifest.md                 # 资产台账（按 templates/asset-manifest.md：编号/职责/版本/在线URL/质检/喂镜）
├── 03-prompts/shot-XX-vNNN.md   # 提示词只增版本、不覆盖旧版
├── 04-takes/shot-XX/     # 生成产出：Takes 素材 + take-ledger.md（按 templates/take-ledger.md；输出端，不放参考图）
└── 05-review/review.md   # 角色×镜头全覆盖审稿表（按 templates/review.md）
```

规则：
1. **三件套是唯一真相源**：提示词中的主体描述必须从 `subject-registry.md` 复制、氛围段必须从 `atmosphere-lock.md` 复制，禁止改写
2. **只读区**：`00-source/` 任何修改走 `01-plan/` 的修订记录
3. **阶段移交行**：每个阶段产出文件的末尾必须有一行：
   `> 阶段移交：[当前阶段] 完成于 [日期] → 下一步 [下一阶段]，入口条件 [已满足/缺什么]`
   开新会话续工只认这行 + 目录结构，不认会话记忆
4. **编号**：shot 两位数（01、02…）；提示词版本 v001 起递增；Take 用 T001 起递增
5. 文件缺失不代表阶段未做——先找用户确认再补建，不要静默重建覆盖
6. **参考图绑定编号**：一张参考图只承担一个主要职责（角色↔Portrait 编号、场景↔场次编号）；改图走版本追加（v1→v2），同时更新 subject-registry 与引用该图的提示词版本
7. **提示词引用**：需要参考图的镜头，提示词主体段写"参考上传图，100% 保留面部/服装"并指明 `manifest.md` 中的资产编号
8. **输入/输出分离**：`02-storyboard/assets/` 只存喂给模型的参考图（输入端）；`04-takes/` 只存生成结果（输出端）；两边文件不互相挪动
9. **P0 交接点**：分场大纲/处理台本是剧本开发层与制作层的边界——前提/结构/人物/对白归 sw-* 群；P0 完成后 `01-plan/story-bible.md` 冻结为 P0 存档，P1 起以本 skill 的资产图为准
10. **冲突处理**：初始化只增不删；骨架目录与已有内容冲突时停下给"认领/改名/忽略"三选项，用户裁决后记入 `01-plan/` 备注，后续会话不再重复询问；`00-source/` 归位用户素材一律"复制 + 保留原件"
11. **脚本-提示词一致性映射**：`03-prompts/shot-XX-vNNN.md` 与 `shotlist.md` 第 XX 行一一对应（镜号即文件名）；提示词的画面内容/运镜/时长必须与该行一致。leos 提示词导演的会话内纯文本在 pipeline 里一律物化为该版本化文件；要加戏先改 shotlist（P2 修订 + 登记），再递增提示词版本，禁止提示词单方面扩写

## 5 · 冲突裁决（写死，agent 不得自行裁量）

1. 提示词文法（结构、措辞、负向提示词、模型适配）→ **shortfilm-prompt** 说了算
2. 流程、审稿、台账、连续性、修复纪律 → **leos 六部门** 说了算
3. 资产目录、命名、版本、门禁、阶段路由 → **本 skill** 说了算
4. 时长/画幅/帧率/分辨率 → **只认用户明示**；未指定时询问，模板里的参考值仅供建议，不得自动填入。仅无人值守/测试环境允许不询问：取默认值（16:9、引擎默认）并逐条标注"默认，待用户确认"，不得让默认值静默通过门禁
5. 相机/镜头型号：先有摄影叙事动机（leos 摄影指导的设计结论），再按 shortfilm-prompt 把具体型号作为氛围段执行锚点写入；不得反向"先抄型号再补理由"
6. 剧本开发层（P0 阶段表、story-bible 体例、会话协议、"甲方格式优先"）→ **sw-workflow 及 sw-* 群**说了算；pipeline 不越权改写其内部规则
7. 资产生产规格与 Agnes 调用纪律（§7）→ **本 skill** 说了算；引擎参数细节（API 端点、轮询策略、ffmpeg 命令）归 `agnes-media-generator` 本体

## 6 · 会话与自动调用纪律

- 本流程由用户显式触发（"跑流程/继续/做这个剧本"）；子 skill 只在流程内被显式 `skill` 调用，避免 description 撞车抢跑
- 每完成一个阶段输出小结（该阶段产出 + 门禁状态 + 下一段预告），再进下一阶段
- 会话将中断时，先写好「阶段移交」行再收工

## 7 · 资产生成规格与 Agnes 集成（P2 参考图 / P4 生成）

默认引擎：图像与视频均经 `agnes-media-generator` skill（Agnes Image / Agnes Video 2.5 Flash）。

### 定妆照规格（`assets/subjects/`）

- 16:9 画幅：左侧为人物三视图，右侧为头部特写，背景纯色
- 流程：文生图产出 → subagent 视觉质检合格 → 登记 `manifest.md`（编号绑定 Portrait）

### 场景图规格（`assets/scenes/`，每场景五张一套）

1. 文生图生成 1 张基准场景图
2. 以基准图为参考，生成"往左转 90° / 往右转 90° / 背面"3 张（共 4 张）
3. 4 张作参考，生成 1 张俯视全局图
- 命名 `scene-XX-vN-01…05`（04/05 为第四视角与俯视）

### 引擎调用纪律

- 图生视频/关键帧的参考图（`images` / `first_frame`）：**直接用图像 API 返回的在线 URL**；本地生成的图片文件较大，禁止 Data URI 内嵌（避免 413）
- 单段时长 4–12s、720P；>12s 的内容按分镜边界分段生成，段间用 reference/keyframe 锁一致性，ffmpeg 归一化后拼接（具体命令与坑位见 agnes-media-generator）
- `take-ledger.md` 每 Take 记录：提示词版本 / video_id / seconds / aspect_ratio / seed（如用）

### 资产图视觉质检（subagent 规则）

- 需要"看图判断"定妆照/场景图是否合格时：**一律派 subagent 读图**（独立会话、图片计数清零，单个 subagent ≤4 张）；subagent 必须回文字结论（合格/不合格 + 哪张图 + 原因），主会话不直接读图
- 一套 5 张时拆两批（3+2）派两个独立 subagent；**禁止**续同一 subagent 会话再读下一批（图片计数会累计超限）
- 此条是全局"单会话 4 张图上限"规则在资产质检场景的执行规则
