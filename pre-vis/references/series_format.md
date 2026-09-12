# 系列大纲格式规范（series.json）

## 目录

| 章节 | 内容 |
|------|------|
| 适用场景 | 项目模式目录结构 |
| 故事体量→单元数建议 | 4维判断 + 推荐单元数/时长/幕数 |
| 完整结构 | series.json JSON 示例 |
| 字段说明 | 各字段含义 |
| 分幕规则 | 行业标准（60min/30min/电影）+ 每幕叙事功能 |
| 叙事结构模板 | 三幕 / Save the Cat / 8-Sequence / Hero's Journey |
| Beat Sheet 格式 | beat 数按数字一致性链反推 + 展开规则 |
| 剧本层格式（script_outlines.md）| 场景卡 6 字段 + 3 规则 |
| 校验规则 | 15 项自检 |

---

## 适用场景

**所有项目**（单片/多集）都在项目根目录生成 `series.json`，作为全局单一真相源：
- 多单元项目（多集）：单元数 = 集数
- 单片/单集项目：单元数 = 1，`episode_01` = 整部电影，内部分幕（三幕见下文电影表）
各单元 `script.json` 通过 `project` 字段引用，不反向修改 `series.json`。

**目录结构**：
```
./（cwd）
  series.json          ← 全局，与 episode 目录同级，单一真相源
  episode_01/
    script.json
    assets_prompt.md
    video_prompts.md
    plan.md
  episode_02/
    script.json
    ...
```

---

## 故事体量 → 单元数/时长建议（agent 自动推荐，用户确认）

agent 根据以下维度判断故事体量，**先推荐**单元数和时长，用户可调整：

| 判断维度 | 短篇 | 中篇 | 长篇 | 史诗 |
|---------|------|------|------|------|
| 核心冲突数 | 1~2 | 3~5 | 5~8 | 8+ |
| 主要角色数 | ≤3 | 3~5 | 5~10 | 10+ |
| 时间跨度 | 单场景/单事件 | 数天~数周 | 数月~数年 | 数年/跨代 |
| 场景数 | ≤5 | 5~15 | 15~40 | 40+ |

| 故事体量 | 推荐单元数 | 每单元时长 | 每单元幕数 | 总镜头估算 |
|---------|---------|---------|---------|----------|
| 短篇 | 1~2 单元 | 10~15 min | 2~3 幕 | 75~150 |
| 中篇 | 3~6 单元 | 15~20 min | 3~4 幕 | 225~600 |
| 多单元短剧（AI 剧/高密度短剧）| 8~15 单元 | 10~15 min | 2~3 幕 | 600~1500 |
| 长篇 | 8~12 单元 | 30~45 min | 4~5 幕 | 900~2250 |
| 史诗 | 12~24 单元 | 45~60 min | 5 幕+Teaser | 1350~5400 |

> 用户指定单元数时以用户为准；未指定时 agent 按上表推荐并在 `series.json` 中注明推荐依据。

---

## 完整结构

```json
{
  "project": "雨夜怀表",
  "total_episodes": 10,
  "episode_duration_seconds": 600,
  "style": "日系动画 / 2D赛璐珞 / 柔和光影",
  "style_keywords": ["日系动画", "2D赛璐珞", "柔和光影"],
  "series_logline": "少年捡到怀表后时间开始失控，最终面对命运的选择",
  "expansion_level": "L0",
  "gate": {
    "empathy_entry": "共情入口：观众在乎什么（基本驱动）",
    "conflict_uniqueness": "冲突独特性压力测试结论",
    "stakes_visible": "赌注可感知性结论"
  },
  "theme_statement": "求助胜过孤军奋战，因为……（道德论证 + 价值极性对）",
  "characters": [
    {
      "character_id": "c01",
      "ghost": "未正视的旧伤（错误世界观来源）",
      "want": "表层欲望（具体目标）",
      "need": "内在需要（必须与 want 冲突）",
      "flaw": ["拒绝求助", "推开靠近的人"],
      "arc_type": "正向成长 | 平坦 | 负向堕落"
    }
  ],
  "b_story_character": "c02（B 故事/主题载体）",
  "relationships": [
    {
      "a": "c01",
      "b": "c02",
      "type": "盟友 | 敌对 | 师徒 | 爱情 | 镜像 | ...",
      "state": "当前关系状态一句话（如：师徒，信任正在被考验）",
      "evolution": [
        { "episodes": ["01", "03"], "state": "师徒，绝对信任", "trigger": null },
        { "episodes": ["04"], "state": "老师身份暴露，信任破裂", "trigger": "b7 揭示真相" }
      ]
    }
  ],
  "payoff_registry": [
    { "id": "p1", "payoff": "揭示：老师是另一时间线的他", "setup_beats": ["b4", "b7"], "act": "act_3" }
  ],
  "beat_sheet": [
    { "id": "b1", "text": "少年的日常：用查证据逃避母亲失踪的悲伤", "episode": "01", "setup_for": null },
    { "id": "b4", "text": "老钟验表点题：时间是被借走的", "episode": "02", "setup_for": "p1" }
  ],

  "character_arcs": [
    {
      "character_id": "c01",
      "name": "林晨",
      "arc_summary": "从内向退缩到勇敢面对时间真相",
      "personality_progression": [
        { "episodes": ["01","02","03"], "state": "内向，退缩，不轻易信任他人", "trigger": null },
        { "episodes": ["04","05"], "state": "开始好奇，仍害怕但主动行动", "trigger": "朋友被卷入时间异常，被迫参与" },
        { "episodes": ["06","07"], "state": "接受现实，勇敢但孤独", "trigger": "发现怀表真相后短暂崩溃" },
        { "episodes": ["08","09","10"], "state": "坚定，愿意承担代价", "trigger": "失去最重要的人，做出最终决定" }
      ],
      "key_moments": [
        { "episode": "01", "moment": "捡到怀表" },
        { "episode": "05", "moment": "发现时间倒流的真相" },
        { "episode": "10", "moment": "做出最终选择" }
      ]
    }
  ],

  "scene_distribution": [
    { "scene_id": "s01", "name": "学校走廊", "episodes": ["01", "02", "03"] },
    { "scene_id": "s02", "name": "实验室", "episodes": ["04", "05", "06", "07"] }
  ],

  "voice_profiles": [
    {
      "character_id": "c01",
      "name": "林晨",
      "voice": "男声，17岁，略哑偏低，音高偏低，语速慢",
      "first_set_in": "episode_01"
    }
  ],

  "episode_plan": [
    {
      "episode": "01",
      "title": "雨夜怀表",
      "logline": "少年在雨夜捡到会说话的猫，怀表开始倒转",
      "acts": [
        { "act_id": "act_1", "label": "雨夜相遇", "shot_count_estimate": 25, "set_piece": "雨夜天台：主角追逐怀表阴影，时间在空中冻结" },
        { "act_id": "act_2", "label": "怀表异响", "shot_count_estimate": 25 },
        { "act_id": "act_3", "label": "时间失控", "shot_count_estimate": 25 }
      ]
    }
  ],

  "library_routing": ["喜剧规则/情景喜剧-SKILL.md"],

  "meta": {
    "total_shots_estimate": 750,
    "created_at": "2026-09-10T00:00:00Z",
    "current_stage": "0d 批 2 已确认，待 episode_01 阶段①",
    "next_step": "执行 episode_01 阶段①拆解（第 3 幕起）",
    "decision_log": [
      { "date": "2026-09-12", "change": "s02 出口钩由"悬念"改为"反转"", "reason": "payoff p1 需要该单元出口推翻既有判断" }
    ]
  }
}
```

---
## 字段说明

| 字段 | 说明 |
|------|------|
| `project` | 项目名称，同项目所有 `script.json` 的 `project` 字段必须与此一致 |
| `total_episodes` | 总单元数（单片项目 = 1，`episode_01` = 整部电影） |
| `episode_duration_seconds` | 每单元目标时长（秒）；用于估算镜头数：`镜头数 ≈ 时长 / 8`（默认 8s/镜头）|
| `series_logline` | 系列总主题（一句话，logline 公式见 Beat Sheet 规则）|
| `expansion_level` | 扩展等级 L0~L3（`story_expansion_guide.md` §1 判定结果）|
| `gate` | 高概念门三测试结论（§2）；三项全过才进 0a-2 |
| `theme_statement` | 主题论证："X 胜过 Y，因为……" + 价值极性对（§4）|
| `characters[]` | 角色设计页：`ghost` / `want` / `need`（必须与 want 冲突）/ `flaw[]` / `arc_type`（§3.1）；与 `character_arcs` 分工：本字段管"设计"，`character_arcs` 管"轨迹" |
| `b_story_character` | B 故事（主题线）载体角色 id（§4）；高潮 Synthesis 时给出 A 故事解法 |
| `relationships[]` | 角色关系矩阵：`a`/`b` 成对 + `type` + `state` + `evolution`（成对关系时间线，结构同 `personality_progression`：`episodes` 区间 + `state` + `trigger`）；**镜头层决策（台词关系约束/表情/色温/空间布局）查当前单元所在 stage 的 `state`，不现场猜**（`story_expansion_guide.md` §3.3） |
| `payoff_registry[]` | payoff 登记表：`id` / `payoff` / `setup_beats[]` / `act`（§6.4）；高潮每个揭示必须在此登记 |
| `beat_sheet[]` | 故事骨架 beat 列表：`id` / `text`（一句话事件）/ `episode`（归属单元）/ `setup_for`（可选，`payoff_registry[].id`）；**beat 的主落点**（`beat_sheet.md` 仅作可读视图，可选生成，不默认写）|
| `character_arcs` | 角色弧线列表，跨单元一致性参考 |
| `character_arcs[].key_moments` | 角色关键节点；`episode` 必须在 `total_episodes` 范围内 |
| `character_arcs[].personality_progression` | 角色性格轨迹；每个 stage 写 `episodes`（单元区间）、`state`（该阶段性格状态）、`trigger`（触发事件，初始 stage 为 `null`）；**每个单元 `script.json` 角色 `personality` 字段 = 该单元所在 stage 的 `state` 值**，镜头提示词的表情决策依据此字段 |
| `scene_distribution` | 场景分布，规划参考图生成时机 |
| `scene_distribution[].episodes` | 该场景出现的集数；参考图只在**首次出现的集**生成 |
| `voice_profiles` | 角色音色档案：每个主要角色一条，`voice` 为音色规格（写进每句台词 prompt）；首单元定死后跨单元引用，**不逐单元重新决定**；推导依据 = 年龄 + personality + 初始 personality stage。**小角色例外**：出对白但非主要（对白 ≤2 句）的角色不进档案——① 现场一次性定 8 字内音色行直接写进台词行，同一角色跨镜头复用第一次定下的行 |
| `episode_plan` | 每单元的分幕规划，长度必须 = `total_episodes` |
| `episode_plan[].acts` | 该单元分幕列表；`shot_count_estimate` 建议 10~30；`set_piece` 为该幕招牌场面（一句话，§6.1，最黑暗幕可空） |
| `meta.total_shots_estimate` | 全项目预估总镜头数（≈ `total_episodes × 每单元平均镜头数`）|
| `engine_check` | 系列引擎测试（`story_expansion_guide.md` §7.4/§7.5）：`pass/fail` + 事件种子表 + franchise 四要素（concept/conflict/theme/`story_pattern`——每单元重复的形状，一句话）+ `theme_proposition`（可辩的对立命题，禁单词主题）+ `pressure_drop`（闭合长篇：物质引擎失压的单元 = 结尾位置）；fail → 回 0a-2 |
| `library_routing` | 0a-1 类型锁定 → 素材库文件路由（类型 → `素材库/` 子目录/文件列表，无命中 = 空数组）；素材库的**主动打开**只凭此字段 |
| `image_system` | 形象系统（可选，麦基）：一类形象全片连贯反复出现且每次有微变（如"水/盲视/腐坏"）；写了则场景卡/道具/色板决策都向它靠 |
| `meta.current_stage` + `meta.next_step` | 会话协议（SKILL.md"会话协议"节）：项目进度指针；每个阶段确认点过后更新；一次性交付项目可省略 |
| `meta.decision_log[]` | 决策日志：改已定事项（换前提/换结尾/删角色/改卡/改 0d 卡）时追加一行 `date / change / reason`；跨会话恢复时只读最近 3 条

---

## 分幕规则（行业标准）

### 幕数与时长

| 每单元时长 | 幕结构 | 说明 |
|---------|-------|------|
| 10~15 min（短剧）| 2~3 幕 | 每幕 15~25 镜头 |
| 15~20 min | 3~4 幕 | 每幕 15~25 镜头 |
| 30~45 min | 4~5 幕 + Teaser | 每幕 20~30 镜头 |
| 45~60 min（标准电视剧）| Teaser + 4~5 幕 | 每幕 25~35 镜头 |

### 每幕叙事功能（必须写明）

**60 分钟剧（Teaser + 5 幕）**：

| 幕 | 时长占比 | 叙事功能 | 结束时必须有 |
|----|---------|---------|-----------|
| Teaser | 2~3 min | 冷开场，建立冲突/悬念/异常 | 一个问题或异常事件 |
| Act 1 | 15~20% | 引入角色 + **催化剂事件**（打破日常）| 主角做出第一个决定 |
| Act 2 | 20~25% | 升级冲突，引入盟友/对手/新信息 | 局势恶化或新发现 |
| Act 3 | 15~20% | **最黑暗时刻**（一切看起来无望）| 主角处于最低点 |
| Act 4 | 20~25% | 开始解决，希望出现，关键转折 | 做出关键牺牲/决定 |
| Act 5 | 15~20% | 高潮 + 收束 | 核心冲突解决（或新悬念）|

**30 分钟剧（Teaser + 2~3 幕）**：

| 幕 | 叙事功能 |
|----|---------|
| Teaser | 冷开场（1~2 min）|
| Act 1 | 引入 + 催化剂 + 升级（合并）|
| Act 2 | 最黑暗 + 转折 + 高潮（合并）|
| Act 3（可选）| 收束/开放结局 |

**电影（90~120 min，三幕）**：

| 幕 | 占比 | 叙事功能 | 关键节点 |
|----|------|---------|---------|
| 第一幕 | 25% | 建置 + 催化剂 | 主角跨入门槛（~25%处）|
| 第二幕 | 50% | 对抗 + **中点转折** + 最黑暗时刻 | 中点（~50%）有新信息/新盟友 |
| 第三幕 | 25% | 高潮 + 结局 | 高潮在 ~75% 处 |

> 每幕的 `narrative_function` 字段必须写明（如"催化剂"、"最黑暗时刻"），不能只写"幕1""幕2"。
> 同样，每幕的 `set_piece` 字段必须写明（该幕 1 个招牌场面，一句话可复述，`story_expansion_guide.md` §6.1）；"最黑暗时刻"幕可为空（relief 段）。

### 幕断点决策判据（"为什么在这里分幕"）

幕断点必须落在**"态势转变"点**（满足其一），不许只因"时间/镜头数过半"：

| 态势转变类型 | 判断问题 |
|------------|---------|
| 目标改变 | 主角从"想要 X"变成"必须做 Y"？|
| 局势不可逆 | 发生了出不了收回来的事？|
| 判断被推翻 | 新信息让此前所有判断失效？|

**校验两条**：
1. 幕断后，主角的下一步行动方向 ≠ 上一幕
2. 每幕 `emotional_arc` 起终点必须**极性反转**（平静↔紧张、希望↔绝望）；"平静 → 有点紧张"不算反转，重做

---

## 单元结构层与季形登记（多单元项目，0b 确认）

- **幕尾类型（act out）**：反转 / 新威胁 / 情感反转 / 情势变化；每单元逐幕写明，类型**不连续重复**；幕断仍走"幕断点决策判据"（态势转变 + 情感极性反转）
- **隐形幕**（流媒体 / 无广告位）：单元分 2~4 个**剧情日**，每剧情日 1 次**信息或权力转移**（标志：换日 / 换地点与交通工具 / 核心问题转向）；不写幕标记，但每次转移必须可指认
- **A/B/C 线**：A = 单元主线（payoff 落点）/ B = 关系主题线 / C = 副线喜剧；C 线 ≤ 25% 镜头，三线场景 5:3:2
- **季形**（`season_shape[]`，≥2 种，方法见 `story_expansion_guide.md` §7.5）：容器集 / 瓶子集 / tentpole / 双集 / 季终减场加长 / 季级对称
- 登记字段（JSON 顶层，多单元必填；单片项目省略）：

```json
"season_shape": [
  { "type": "容器集", "unit": 6, "occasion": "颁奖礼" },
  { "type": "tentpole", "unit": 4 },
  { "type": "季终减场加长", "unit": 10 }
]
```

---

## 叙事结构模板（可选骨架，agent 根据故事类型推荐一个）

| 模板 | 适用 | 核心节点 | 说明 |
|------|------|---------|------|
| 三幕结构 | 电影/单集 | 催化剂 → 中点 → 最黑暗 → 高潮 | 最通用 |
| Save the Cat（15 beat）| 单集/电影 | 开场板→主题→设定→催化剂→辩论→B故事→...→终场板 | 节奏精确 |
| 8-Sequence | 季播/多集 | 每季 8 集 × 每集 8 个 sequence = 64 节点 | 季级规划 |
| Hero's Journey（12步）| 角色弧光强的故事 | 日常→召唤→拒绝→导师→跨越→考验→奖励→回归 | 冒险/成长类 |

**使用方式**：agent 在阶段 0 推荐一个模板，将其关键节点映射到 `series.json` 的 `episode_plan` 中，作为 beat sheet 的骨架。

---
## Beat Sheet 格式（故事扩展中间产物）

**用途**：在拆镜头之前，先把故事压缩为关键节点（beat 数按"数字一致性链"由单元时长反推，见下文规则），确认故事骨架后再展开。

**格式**（主落点：`series.json` 的 `beat_sheet[]`；`beat_sheet.md` 仅作可读视图，可选生成）：

```markdown
# Beat Sheet — [项目名]

1. [主角在日常世界中的状态/不满]
2. [触发事件：打破日常的催化剂]
3. [拒绝/犹豫：主角最初不接受改变]
4. [跨入门槛：主角做出第一个不可逆决定]
5. [第一次考验：新世界的规则/危险]
6. [盟友/导师出现]
7. [接近目标（中点）：看似胜利或重大发现]
8. [背叛/失去：最黑暗时刻]
9. [顿悟：找到真正的方法/理解]
10. [高潮：最终对决/选择]
11. [结局：新的日常/开放式]

[如有多集，标注每个 beat 对应的集数]
```

**规则**：
- 每个 beat 一句话，描述"必须发生的事"（不写细节，细节在场景层展开）
- **节点质量判据（不可逆测试）**：事件之后，角色的处境/信息/关系是否与之前**根本不同、回不去**？不满足 → 并入上一节点，不独立成 beat
- **因果链**：每个 beat 必须是前一个的"必然结果"而非拼贴；不满足因果 → 改写为因果或删掉
- **数字一致性链（0b 校验时执行）**：`每单元镜头数 = 单元时长(秒) ÷ 8（±15%）` → `场景数 = 镜头数 ÷ 4`（区间 ÷3~÷5）→ `beat 数 = 场景数 ÷ 2`（区间 ÷1~÷3，即"每个 beat 展开为 1~3 个场景"）；用 beat 数反推时长，偏差 >±20% 时先调 beat/场景数再继续
- **每单元必须有一个情绪高点**（不一定是大高潮，可以是小揭秘/小挫败）
- **logline 公式**（`series_logline` 和每单元 `logline` 都用）：主角 + 主动目标 + 核心障碍 + 赌注（失败会失去什么）；自检"读完这句会不会想看下一步"
- 每个 beat 展开为 1~3 个场景
- **场景 → 镜头拆分依据**：镜头数 = 该场景"信息输出"条数——观众必须看到什么（establish）/ 揭示什么新信息（reveal）/ 发生什么动作（action）/ 谁的 reactions（reaction），一个目的一个镜头（`video_prompt_guide.md` §1.2）；纯动作场景 ≈ 3 个，信息密集 ≈ 5 个
- beat 数量：按"数字一致性链"由单元时长反推（不拍脑袋）；单片项目通常落在 8~12
- 可选 `setup_for`：标注该 beat 为哪个 payoff 埋的 setup（`payoff_registry[].id`）；无 setup 的 payoff 和无 payoff 的 setup 均为违规（`story_expansion_guide.md` §6.4）

---

## 剧本层格式（script_outlines.md，全剧场景卡）

**用途**：阶段 0d 一次性输出**所有单元**的场景卡（Sorkin 索引卡法：一卡 = 一场景，卡片层看全剧；故事级问题全在此修完），逐单元执行 ① 时按本单元卡片拆镜头，**① 不发明剧情**。

**位置**：`./script_outlines.md`（单文件，每单元一节；单元 >5 时按 3~4 集一批输出）

**每卡 8 项**（前 7 项挂已有判据；后 2 项为过渡/信息标注，首卡可省）：

```markdown
### [第 01 集]

【场景卡 s02 · 天台追影子】INT.→EXT. 天台 / 雨夜
· 谁要什么：林晨要追上怀表影子（得不到→时间线继续乱）；秤要护住怀表
  （Mamet 三问逐条答：要什么 / 得不到会怎样 / 为什么是现在；场景内每个角色都要写）
· 价值翻转：control: in-control → out-of-control（行动型：追到了但更失控）
· 动作（3~5 行，现在时，**只写镜头拍得到的**——可见/可听，不写心理）
· 关键台词："它不走。"（林晨，低声；潜台词：我不敢再看第二次）
· 出口钩：指针停在 23:15 —— 留"母亲在哪"的疑问进下场
· 造型状态：林晨 = 校服 + 湿发（v1 + bv1）；秤 = 默认形象（无变体）
· 过渡要素：与前卡 s01 的第三要素 = 动作延续（林晨冲上天台的脚步声接开场）；与后卡 s03 = 物件（怀表）
· 信息位置：受限（观众与林晨同步不知指针含义，惊奇压在 s04 揭示）
```

**3 条规则**：
1. 场景卡数 = 价值翻转条数（`story_expansion_guide.md` §5.1），不翻转的场不进清单；每单元场景数 ≈ 该单元 beat 数 × 1~3（与 Beat Sheet 规则"每个 beat 展开为 1~3 个场景"一致）
2. 卡 ↔ beat/payoff 一一对应：本单元卡片必须覆盖本单元全部 beat；带 `setup_for` 的 beat 必须出现在对应卡片的"动作"或"关键台词"里
3. 出口钩 4 型（悬念/反转/情感/信息）不连续重复（§7.2）；最后一单元末卡出口为收束
4. 造型状态只引用该角色**已存在的** variant / base_version；造型变化必须对应一个 beat（造型是叙事的不是审美的）；`base_versions[].active_episodes` 切换点在 0c 定（绑 `key_moments`），① 只引用不创建
5. 段落思想（sequence）：同单元每 3~5 张卡归一个"段落"，段落给一句话思想（标题）；同单元段落思想不得重复；段落之间靠卡片的"过渡要素"（第三要素：人物特征/动作余势/物件/一句话/光质/声音/想法）衔接，不硬跳

---

## 校验规则

- [ ] `episode_plan` 长度 = `total_episodes`
- [ ] 所有 `character_arcs[].key_moments[].episode` 在 `total_episodes` 范围内（01~NN）
- [ ] 所有 `scene_distribution[].episodes` 中的单元编号在 `total_episodes` 范围内
- [ ] 所有 `episode_plan[].acts[].shot_count_estimate` 在 10~30 范围内
- [ ] `meta.total_shots_estimate` ≈ 所有 `episode_plan[].acts[].shot_count_estimate` 之和
- [ ] `voice_profiles[].character_id` 覆盖所有出对白的主要角色，且单元编号在 `total_episodes` 范围内
- [ ] `gate` 含三测试结论，且 `expansion_level` 已填写（`story_expansion_guide.md` §1/§2）
- [ ] `theme_statement` 非空（含价值极性对，§4）
- [ ] `payoff_registry` 每条：`setup_beats[]` ≥ 1，且 setup beat 位置**先于 payoff 所在幕（单元）至少 1 幕**（§6.3/§6.4）
- [ ] `relationships[]` 每对的 `a`/`b` 都在 `characters[]` 中存在；`evolution` 各 stage 的 `episodes` 在 `total_episodes` 范围内
- [ ] 出对白的小角色（对白 ≤2 句且非主要）：台词行内有一致音色行，未写入 `voice_profiles`（小角色例外规则）
- [ ] `script_outlines.md` 存在且覆盖全部单元；每卡 7 项齐全，翻转入口 ≠ 出口，本单元卡覆盖本单元全部 beat
- [ ] `beat_sheet[]` 的 `episode` 在 `total_episodes` 范围内，且 `setup_for`（如有）取自 `payoff_registry[].id`
- [ ] `scene_distribution[]` 的首现单元与 `script_outlines.md` 卡片首现单元一致（如场景分布写第 3 单元、卡片首现在第 5 单元 → 修其一）
- [ ] 数字一致性链：每单元镜头数 ≈ 时长÷8（±15%）、场景数 = 镜头数÷4（区间 ÷3~÷5）、beat 数 = 场景数÷2（区间 ÷1~÷3）；反推偏差 >±20% 先调 beat/场景数
- [ ] `engine_check` 已填（pass/fail + 事件种子表，§7.4）；fail 时项目停在 0b，不进 0c
- [ ] 多单元：`season_shape` ≥ 2 种登记（容器/瓶子/tentpole/双集/季终减场/季级对称，§7.5）；每单元幕尾类型不连续重复；流媒体项目的隐形幕"剧情日 + 每幕 1 次信息/权力转移"可指认
- [ ] `library_routing` 与 0a-1 锁定类型一致（多单元必填；单片项目可空数组）
- [ ] L2/L3 素材"不翻转"而保留的场景，卡上均有豁免理由（"段落思想"行，`story_expansion_guide.md` §5.1）；无理由保留 = 违规
- [ ] `meta.current_stage` / `meta.next_step` 与最新确认点对齐；`decision_log` 每行含 change + reason（一次性交付项目可省，见 SKILL.md 会话协议）
