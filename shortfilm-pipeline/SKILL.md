---
name: shortfilm-pipeline
description: AI 短片/叙事视频制作工作流总编排。负责阶段路由（P1 拆场 → P2 分镜锁定 → P3 提示词编写 → P4 生成与台账 → P5 审稿修复）、门禁检查、项目资产目录与版本规则。按需调用子 skill：leos 六部门（导演流程）与 shortfilm-prompt（提示词文法）。用户说"跑流程/继续/制作这个剧本"或进入 AI 短片项目时加载本 skill；小任务走快速通道。
---

# shortfilm-pipeline — AI 短片制作工作流总编排

## 0 · 职责边界

- 本 skill 只管：**阶段路由、门禁、资产规则、断点续接**。不自己写提示词、不自己拆场。
- 拆场 / 表演 / 摄影 / 审稿 / 台账 → 子 skill `leos-six-department-directing-team-skill-v1`
- 提示词文法（5 阶段结构 / 7 硬规则 / 负向提示词 / 模型坑位）→ 子 skill `shortfilm-prompt`

## 1 · 前置检查（进入流程时做一次）

1. 确认两个子 skill 的 ID 在当前会话可用（看 available skills 列表）。缺失则停下，输出安装指引——统一装进 OpenCode 原生全局 skills 目录 `C:\Users\Administrator\.config\opencode\skills\`：
   - leos：`git clone https://github.com/MasterLeos/leos-six-department-directing-team-skill-v1`，整包放到 `C:\Users\Administrator\.config\opencode\skills\leos-six-department-directing-team-skill-v1\`（SKILL.md 必须位于该目录根部，目录名即 skill ID）
   - shortfilm-prompt：`git clone https://github.com/jnMetaCode/ai-shortfilm-prompts`，把仓库内 `skills/shortfilm-prompt/` 拷到 `C:\Users\Administrator\.config\opencode\skills\shortfilm-prompt\`，并把仓库 `templates/` 拷进该目录（模板路径是相对 SKILL.md 解析的）
   - 装完需新开 OpenCode 会话（skill 在会话启动时被发现）
2. 扫描当前项目目录判断入口阶段：
   - 只有剧本（`00-source/` 或散落的脚本文件）→ **P1**
   - 已有 `02-storyboard/` 三件套 → **P3**
   - 已有 `03-prompts/` 但 `04-takes/` 空 → **P4**
   - 已有 `04-takes/` 成片但无 `05-review/` → **P5**
   - 各文件末尾有「阶段移交」行的，以该行为准，不猜

## 2 · 阶段路由表

| 阶段 | 输入 | 加载的子 skill | 产出 | 门禁（全部满足才进下一阶段） |
|---|---|---|---|---|
| P1 拆场 | 剧本 | leos（总导演+场记） | `01-plan/scene-XX/brief.md`、`decisions.md` | 场次目的/主角/节奏/空间关系已锁定；用户逐场确认 |
| P2 分镜锁定 | 场次包 | leos（表演/镜内/摄影三部门简报）+ shortfilm-prompt 的 `templates/project-planner.md` | `02-storyboard/shotlist.md`、`subject-registry.md`、`atmosphere-lock.md`、`assets/manifest.md` | 主体登记每个复现角色 ≥2 瑕疵锚点；氛围段落定稿；shotlist 每镜 Exit/Entry 对齐；全片 ≤8 镜、单镜 ≤15s；参考图（如需）已产出并登记 manifest；用户确认可先生成首尾镜 |
| P3 提示词编写 | 三件套 | shortfilm-prompt（5 阶段 + 7 硬规则） | `03-prompts/shot-XX-v001.md` | 每个提示词：主体描述从 subject-registry 复制、氛围段从 atmosphere-lock 复制；过 leos 校验脚本（若可用）+ shortfilm-prompt 30 秒清单；版本 vNNN 递增 |
| P4 生成与台账 | 提示词 | leos（场记 Take 登记 + 局部修复原则） | `04-takes/shot-XX/` 素材 + `take-ledger.md` | 先生成首尾两镜锁观感，漂移即停；每镜登记提示词版本/Take 结论/耗时；重 roll 预算 ≈ 5–10 倍终选镜数 |
| P5 审稿修复 | 成片 | leos（六角色逐镜审稿） | `05-review/review.md` | 审稿表为「角色 × 镜头 1..N」全覆盖，无问题的镜头也写"通过"；每镜有 保/过/修/废 结论；"修"的镜头走局部修复（一次只改一个变量） |

**执行纪律**：每阶段开始时用 `skill` 工具显式加载对应子 skill，不凭记忆操作；阶段内子 skill 的规则优先于本 skill。

## 3 · 快速通道（Fast Lane）

适用：单镜 ≤15s 或纯氛围单镜、不走完整叙事流程的小任务。

- 跳过 P1/P2，直接 **P3（shortfilm-prompt 单镜模式）→ P4**
- 仍需执行：30 秒清单自检、`03-prompts/` + `04-takes/` 目录规则、Take 台账（一行即可）
- 单镜任务可跳过 `02-storyboard/assets/`（不需要参考图时）
- 同一项目内快速通道产出的镜头，若后续要并入多镜叙事，必须回填 `02-storyboard/` 三件套再进 P5

## 4 · 资产图规则（路径均相对项目根目录）

```
my-film/
├── 00-source/            # 原始剧本与参考资料，只读，不修改
├── 01-plan/scene-XX/     # 场次包：brief.md（六部门方案）+ decisions.md（用户裁决）
├── 02-storyboard/        # 全片一份、镜头级更新的"分镜三件套"
│   ├── shotlist.md       # 逐镜：景别/运镜/内容/Exit/Entry/时长
│   ├── subject-registry.md   # 主体登记表：编号固定，全片不复用改号
│   ├── atmosphere-lock.md    # 氛围段落：只写一次，逐字粘贴
│   └── assets/             # 参考图资产区（输入端，与三件套绑定）
│       ├── subjects/portrait1-v1.png   # 角色定妆图：脸+服装+关键道具，绑定 Portrait 编号
│       ├── scenes/scene-01-v1.png      # 定场/氛围参考图，绑定场次编号
│       └── manifest.md                 # 资产台账：编号/职责/版本/喂给哪些镜
├── 03-prompts/shot-XX-vNNN.md   # 提示词只增版本、不覆盖旧版
├── 04-takes/shot-XX/     # 生成产出：Takes 素材 + take-ledger.md（输出端，不放参考图）
└── 05-review/review.md   # 角色×镜头全覆盖审稿表
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

## 5 · 冲突裁决（写死，agent 不得自行裁量）

1. 提示词文法（结构、措辞、负向提示词、模型适配）→ **shortfilm-prompt** 说了算
2. 流程、审稿、台账、连续性、修复纪律 → **leos 六部门** 说了算
3. 资产目录、命名、版本、门禁、阶段路由 → **本 skill** 说了算
4. 时长/画幅/帧率/分辨率 → **只认用户明示**；未指定时询问，模板里的参考值仅供建议，不得自动填入
5. 相机/镜头型号：先有摄影叙事动机（leos 摄影指导的设计结论），再按 shortfilm-prompt 把具体型号作为氛围段执行锚点写入；不得反向"先抄型号再补理由"

## 6 · 会话与自动调用纪律

- 本流程由用户显式触发（"跑流程/继续/做这个剧本"）；子 skill 只在流程内被显式 `skill` 调用，避免 description 撞车抢跑
- 每完成一个阶段输出小结（该阶段产出 + 门禁状态 + 下一段预告），再进下一阶段
- 会话将中断时，先写好「阶段移交」行再收工
