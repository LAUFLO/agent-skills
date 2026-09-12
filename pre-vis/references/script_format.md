# 剧本 JSON 格式规范（script.json）

## 目录

| 章节 | 内容 |
|------|------|
| 顶层结构 | project / episode / acts / characters / scenes / props / shots / meta |
| 角色 | 三层形象结构（base_ref_image / base_versions / costume_variants）|
| 幕（acts[]）| 分幕 + emotional_arc + shot_ids |
| 场景 | time / location / atmosphere / lighting / ref_image |
| 道具 | description / appears_in_shots / ref_image |
| 镜头（shots[]）| 12 字段（含 prev_shot_ref / shot_purpose / screen_direction / review_state）|
| 跨单元一致性 | base_ref_image 永远有效 / base_version 回落规则 / 参考图生成时机 |
| 校验规则 | 16 项 agent 自检清单 |

---

## 顶层结构

```json
{
  "project": "项目名称",
  "episode": "01",
  "title": "雨夜怀表",
  "logline": "少年在雨夜捡到一只会说话的猫，怀表倒转，时间开始失控",
  "style": "日系动画 / 2D赛璐珞 / 柔和光影 / 电影感",
  "style_keywords": ["日系动画", "2D赛璐珞", "柔和光影", "电影感"],
  "acts": [ ... ],
  "characters": [ ... ],
  "scenes": [ ... ],
  "props": [ ... ],
  "shots": [ ... ],
  "meta": {
    "total_shots": 12,
    "total_duration_seconds": 84,
    "created_at": "2026-09-10T00:00:00Z",
    "prev_episode_refs": []
  }
}
```

**`project`**：项目名称，同项目多单元共用同一值，用于跨单元一致性识别。

**`prev_episode_refs`**：引用前一单元的角色/场景/道具 id 列表（如 `["c01", "s01", "p01"]`），不重复定义，只声明引用，避免跨单元时角色形象漂移。

---

## 角色（characters[]）

**设计原则**：角色形象分三层——`base_ref_image`（默认面部/发型/体型指纹，不可变锚点）+ `base_versions`（阶段性形象变化，如换发型/体型变化）+ `costume_variants`（服饰状态，随剧情切换）。

```json
{
  "id": "c01",
  "name": "林晨",
  "age": 17,
  "species": "human",
  "appearance": "黑色短发，左耳上方一枚银色发夹，偏瘦体型，皮肤偏白，左眼角有泪痣",
  "feature_anchors": ["黑色短发", "银色发夹", "左眼角泪痣", "偏瘦体型"],
  "temperament": "敏感、倔强、安静",
  "catchphrase": "……没事。",
  "weakness": "不轻易信任他人，害怕失去",
  "personality": "内向，观察力强，说话简短",
  "color_palette": ["#6D6B69", "#BDAE9A", "#BD7A66"],
  "base_ref_image": "c01_base.png",
  "ref_image_set": {
    "base": "c01_base.png",
    "expressions": "c01_expressions.png",
    "outfit_detail": "c01_outfit_detail.png",
    "closeup_detail": "c01_detail.png"
  },
  "first_appeared_in": "episode_01",
  "base_versions": [
    {
      "version_id": "c01_bv2",
      "label": "长发版",
      "appearance_desc": "黑色长发至肩，右侧扎小马尾",
      "ref_image": "c01_base_longhair.png",
      "active_episodes": ["episode_02"]
    }
  ],
  "costume_variants": [
    {
      "variant_id": "c01_v1",
      "label": "校服",
      "costume_desc": "黑色校服外套、白色卫衣、深蓝色运动裤、黑色帆布鞋",
      "ref_image": "c01_v1.png",
      "active_episodes": ["episode_01", "episode_02", "episode_03"]
    },
    {
      "variant_id": "c01_v2",
      "label": "西装",
      "costume_desc": "深灰色西装、白衬衫、黑色皮鞋",
      "ref_image": "c01_v2.png",
      "active_episodes": ["episode_03"]
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `feature_anchors` | 面部/发型/体型锚点（**不含服饰**），每次出现在提示词中必须全量写入；建议 2~4 个，必须是视觉上可识别的特征 |
| `personality` | 角色当前性格状态。**单片/单集项目**：静态描述（如"内向，观察力强，说话简短"）；**多单元项目**：写该单元所在 stage 的 `state` 值（来源：`series.json → character_arcs[].personality_progression[]`）；写镜头提示词时与 `temperament` + `weakness` 组合使用，作为表情决策 Step 2 的依据（见 `video_prompt_guide.md` §2.3）|
| `base_ref_image` | 默认基础定妆照（素衣状态），**不可变锚点**，第一集生成后永远有效；角色回到原始形象时直接引用此文件，无需重新生成 |
| `base_versions` | 阶段性形象变化列表（换发型/体型变化/特殊化妆）；每个 version 只在 `active_episodes` 范围内生效，超出范围自动回落到 `base_ref_image` |
| `base_versions[].ref_image` | 该 version 参考图，生成时 @1 = `base_ref_image`（面部约束）；**只在首次出现的集生成一次**，后续集直接引用 |
| `costume_variants` | 服饰变体列表；每个 variant 在 `active_episodes` **首次出现的集**生成参考图，后续集直接引用文件 |
| `costume_variants[].ref_image` | 该 variant 参考图，生成时 @1 = 该单元**当前生效的 base**（有 `base_version` 时用其 ref_image，否则用 `base_ref_image`），画面画新服饰 |
| `first_appeared_in` | 首次出现的单元编号，用于跨单元判断是否需要重新定义 |

---

## 幕（acts[]）

**说明**：一集内的分幕结构，每幕有独立的情感弧线，幕间有明显情绪转折点。单集短剧（≤20个镜头）可省略此字段。

```json
{
  "acts": [
    {
      "act_id": "act_1",
      "label": "雨夜相遇",
      "summary": "林晨回家路上在走廊捡到旧怀表",
      "emotional_arc": "平静 → 好奇 → 紧张",
      "shot_ids": ["shot_001", "shot_002", "shot_025"]
    },
    {
      "act_id": "act_2",
      "label": "怀表异响",
      "summary": "林晨发现怀表指针倒转",
      "emotional_arc": "困惑 → 震惊 → 恐惧",
      "shot_ids": ["shot_026", "shot_050"]
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `act_id` | 全集唯一，格式 `act_N` |
| `emotional_arc` | 该幕情感走向，用"状态A → 状态B → 状态C"格式 |
| `shot_ids` | 该幕包含的镜头 id 列表，`shots[]` 中对应镜头的 `act_id` 必须与此一致 |

---

## 场景（scenes[]）

```json
{
  "id": "s01",
  "name": "学校走廊（雨夜）",
  "time": "night",
  "location": "学校教学楼走廊",
  "atmosphere": "昏暗，雨水从窗户渗入，地面有反光",
  "lighting": "冷蓝色走廊灯，远处有暖黄光斑",
  "ref_image": "s01_scene.png",
  "value": "trust: wary → open（林晨对老师从戒备到说出实情）",
  "line": "A"
}
```

**`time` 取值**：`dawn / morning / noon / afternoon / dusk / night`

**`value` 字段**（决策依据 `story_expansion_guide.md` §5）：`价值词: 入口极性 → 出口极性`，一场景一条价值线，**出口极性必须 ≠ 入口极性**（不翻转的戏不留）；翻转机制限定两种：行动（结果 gap）/ 揭示（新信息推翻判断）。

**`line` 字段**：剧情线归属，取值 `A`（主线）/ `B`（主题线）/ `sub`（支线）。`B`/`sub` 场景可带 `payoff_ref`（指向 `payoff_registry[].id`）。决策用途：B 故事场景 `color_script` 用统一色偏（视觉区分支线）；台词/表情决策查 `relationships[]`（见 `series_format.md`）

---

## 道具（props[]）

```json
{
  "id": "p01",
  "name": "旧怀表",
  "description": "铜质外壳，表面氧化发绿，表盘玻璃有裂纹，指针停在23:15",
  "role": "结构核心（时间倒转 payoff 的载体，高潮亲登场）",
  "color_palette": ["#4A7A6B", "#8B6B4A"],
  "appears_in_shots": ["shot_002", "shot_005"],
  "ref_image_set": {
    "main": "p01_prop.png",
    "detail": "p01_prop_detail.png",
    "angles": "p01_prop_angles.png"
  }
}
```

**`appears_in_shots`**：列出该道具出现的所有镜头 id，方便 plan.md 中标注参考图依赖。

**`role` 字段**（写 `props[]` 时必选其一）：道具承担的戏剧作用，六选一——

| 作用 | 说明 | 示例 |
|------|------|------|
| 结构核心 | 全片主道具，payoff 都挂在它身上，高潮必须亲登场 | 怀表、借据 |
| 矛盾助推器 | 每传递一次矛盾前进一步 | 手帕接力、驴皮胶 |
| 刻画人物 | 物件外化角色特征 | 周朴园用怀表校钟 |
| 象征 | 心灵/命运的象征物 | 魔椅、摇篮 |
| 主题窗口 | 物件打开主题讨论 | 定心丸、门板标语 |
| 载体 | 承载歌舞/动作序列的物件 | 石磨、锅 |

> 主角的武器（身份象征：光剑/神剑/车/计算机）按麦基规则**让它在高潮扮演角色**；`role=结构核心` 的道具校验其 `appears_in_shots` 覆盖到 payoff 所在单元的镜头。

---

## 镜头（shots[]）

```json
{
  "id": "shot_001",
  "act_id": "act_1",
  "scene_id": "s01",
  "character_refs": [
    { "character_id": "c01", "variant_id": "c01_v1" }
  ],
  "prop_ids": [],
  "duration_seconds": 8,
  "shot_purpose": "reveal",
  "camera": "平视，中景，固定",
  "screen_direction": "static",
  "stage": "林晨中景居中偏左，低头朝怀表",
  "emotional_register": "压抑的孤独",
  "color_script": "冷蓝 8000K，暗:亮比 70:30",
  "action_summary": "林晨低头看怀表，雨水滴落在走廊地面",
  "dialogue": "",
  "narration": "那天晚上，我第一次看见它的指针在倒转。",
  "first_frame_desc": "中景，林晨站立于走廊中央，低头，右手持旧怀表垂于身侧，冷蓝调，地面雨水反光",
  "video_action_desc": "林晨缓慢抬起怀表至面部高度，镜头从中景推至面部特写，节奏放缓，情绪从平静转紧张，雨滴声渐强",
  "negative_prompt": "无侧面机位，无夸张表演，无AI塑料感",
  "review_state": "draft"
}
```

**有 `prev_shot_ref` 的镜头示例**（同场景+同角色+连续动作，agent 自动判断写入）：
```json
{
  "id": "shot_002",
  "act_id": "act_1",
  "prev_shot_ref": {
    "shot_id": "shot_001",
    "frame": "last",
    "reason": "同场景同角色，林晨低头→抬头，连续动作"
  },
  "scene_id": "s01",
  "character_refs": [
    { "character_id": "c01", "variant_id": "c01_v1" }
  ],
  "duration_seconds": 6,
  "camera": "平视，中景，缓推",
  "first_frame_desc": "林晨抬头，眼神移向镜头方向，中景",
  "video_action_desc": "林晨抬头，嘴角微动，镜头缓推至面部特写，节奏渐强，情绪从紧张转坚定"
}
```

**episode_02（长发 + 校服）镜头示例**：
```json
{
  "character_refs": [
    { "character_id": "c01", "base_version_id": "c01_bv2", "variant_id": "c01_v1" }
  ]
}
```

`character_refs` 说明：
- `character_id`：引用 `characters[].id`
- `base_version_id`：引用 `base_versions[].version_id`；**字段省略** = 用默认 `base_ref_image`（角色原始形象）；有值时写明
- `variant_id`：引用 `costume_variants[].variant_id`；角色无服饰变体时可省略
- 多角色镜头按出场顺序排列

**每个角色的 @N 参考图选择规则**：

| 条件 | @1 | @2（可选）|
|------|----|-----------|
| `base_version_id` 有值 + `variant_id` 有值 | `base_versions[base_version_id].ref_image`（面部/发型最准确）| `costume_variants[variant_id].ref_image`（服饰参考，接受发型不精确）|
| 仅 `variant_id` 有值 | `costume_variants[variant_id].ref_image` | — |
| 仅 `base_version_id` 有值 | `base_versions[base_version_id].ref_image` | — |
| 两者都省略 | `base_ref_image` | — |

> 当 base_version + variant 同时存在且工具 @N 上限不足时：@1 传 base_version 图（面部优先），variant 服饰描述写进提示词文字，**不传 variant 参考图**。

| 字段 | 说明 |
|------|------|
| `act_id` | 引用 `acts[].act_id`；单集短剧（无 `acts[]`）时省略 |
| `prev_shot_ref` | 可选。引用前一镜头的尾帧作为动态连续性参考图（@3，槽位顺序见 `skill.md` "@N 槽位优先级"）；agent 自动判断 |
| `shot_purpose` | 镜头目的，9 型：`establish`（建立场景）/ `reveal`（揭示信息）/ `action`（展示动作）/ `reaction`（捕捉反应）/ `transition`（转场）/ `pov`（主观代入）/ `insert`（道具/物件插入特写）/ `twoshot`（双人同框建立关系）/ `empty_shot`（空镜呼吸/时间过渡）；每个镜头有且只有一个明确目的；推荐镜语套餐见 `video_prompt_guide.md` §1.2 |
| `camera` | 镜头规格（角度/景别/运镜 + 可选焦距 + 可选景深），如"平视，中景，固定"；焦距/景深按 `video_prompt_guide.md` "镜头语言速查"与 §1.1 决策表选定，默认省略（= 50mm 中性 / 不写景深）|
| `screen_direction` | 角色移动方向：`left_to_right` / `right_to_left` / `static`；同场景相邻镜头必须一致，否则标注警告 |
| `stage` | 站位/占位描述：每个出镜角色 前/中/后景 + 画面左/中/右 + 角色间距离/朝向（单角色镜可简写，如"林晨中景居中偏左，低头朝怀表"）；多人镜按 `video_prompt_guide.md` §2.8 关系基线推导并注明基线依据；供分镜批图版（image_prompt_guide §5）与 animatic 视觉复核（production_guide §4.3）使用 |
| `emotional_register` | 该镜头的情绪基调（独立于对白），如"压抑的孤独"、"克制的愤怒"；**推导方法**见 `video_prompt_guide.md` §1.3（承接 + 事件 + 性格过滤三步，不得拍脑袋）|
| `color_script` | 该镜头/场景的色温+明暗比，如"冷蓝 8000K，暗:亮比 70:30"；**决策方法**见 `video_prompt_guide.md` §1.4（物理约束 + 情绪匹配 + 一致性 + 弧线外化四步）|
| `character_refs` | 角色引用列表 |
| `negative_prompt` | 该镜头的负向约束（独立于通用负向约束），写具体禁止项 |
| `review_state` | 审阅状态：`draft` / `needs_revision` / `approved` / `generating` / `final` |
| `dialogue` | 对白，多人时用 `"角色名：台词"` 格式，多个对白用换行分隔 |
| `narration` | 旁白（旁白人物不入 `character_refs`）|
| `first_frame_desc` | 首帧静态画面描述（写进图片提示词）|
| `video_action_desc` | 视频动作描述（写进视频提示词），**不重复**首帧内容 |

---
## 跨单元一致性规则

- 所有 `ref_image` 文件名**全项目唯一**，多单元共用
- `base_ref_image`（默认基础定妆照）：第一单元生成一次，**永远有效**；角色回到原始形象时直接引用，无需重新生成
- `base_versions[].ref_image`（阶段性形象）：该 version **首次出现单元**生成一次；超出 `active_episodes` 范围后自动回落到 `base_ref_image`
- `costume_variants[].ref_image`（服饰变体）：variant **首次使用单元**生成一次，后续单元直接引用文件
- 场景/道具参考图：在**首次出现单元**生成一次，跨单元直接引用
- `project` 字段同值 = 同项目，多单元时自动继承 `prev_episode_refs` 中声明的 id
- 新增角色/场景/道具在**首次出现**的那一单元定义，后续单元只引用 id

### 何时需要新增 base_version

在 `base_versions[]` 中新增一项（**不修改** `base_ref_image`），满足任一条件：
- 发型大幅变化（短发→长发、换色）
- 角色年龄/体型有明确变化
- 面部有永久性伤痕或特殊化妆状态

新增 `base_version` 的参考图生成规则：
- @1 = `base_ref_image`（面部/体型约束，确保同一角色）
- 画面描述 = 新的发型/体型/化妆状态 + `feature_anchors` 中不变的部分
- 超出 `active_episodes` 后，该单元自动回落到 `base_ref_image`（原始形象）

---

## 校验规则（agent 生成后自检）

生成 `script.json` 后，agent 必须验证以下规则，不通过则补全后重新校验，不得跳过：

- [ ] 所有 `shots[].scene_id` 在 `scenes[]` 中存在
- [ ] 所有 `shots[].character_refs[].character_id` 在 `characters[]` 中存在
- [ ] 所有 `shots[].character_refs[].base_version_id`（如有值）在对应角色的 `base_versions[]` 中存在
- [ ] 所有 `shots[].character_refs[].variant_id`（如有值）在对应角色的 `costume_variants[]` 中存在
- [ ] 所有 `shots[].prop_ids` 中的每个 id 在 `props[]` 中存在
- [ ] 有 `acts[]` 时：所有 `shots[].act_id` 在 `acts[]` 中存在；所有 `acts[].shot_ids` 在 `shots[]` 中存在
- [ ] 所有 `shots[].prev_shot_ref.shot_id`（如有值）必须是 `shots[]` 中**紧邻前一个**镜头的 id
- [ ] 所有 `shots[].prev_shot_ref`（如有值）的两个镜头必须满足：同 `scene_id` + `character_refs` 有交集
- [ ] 所有 `shots[].shot_purpose` 取值为 9 型之一（establish/reveal/action/reaction/transition/pov/insert/twoshot/empty_shot）
- [ ] 同场景相邻镜头的 `screen_direction` 一致；不一致时标注警告（可能违反 180度轴线）
- [ ] 所有 `shots[].stage` 非空；多人镜头的站位已注明推导依据（§2.8 关系基线）；同场景相邻镜头角色左右位置无互换
- [ ] 同场景相邻镜头满足 30°/景别差 + 景别序列 + 动作剪辑规则（`video_prompt_guide.md` §2.11）；对话戏镜序 twoshot→OTS→reaction，违反标注警告
- [ ] 故意越轴/反转的镜头使用中性插入（特写/远景/空镜）缓冲，且占独立镜头（§2.11）
- [ ] 每个镜头 `duration_seconds` 在 4~15 范围内
- [ ] 有 `narration`/`dialogue` 时：字数 ÷ 2.5 ≤ `duration_seconds`（台词计时，超出则拆镜头）
- [ ] `meta.total_shots` = `len(shots)`
- [ ] `meta.total_duration_seconds` = `sum(shots[].duration_seconds)`
- [ ] 无字段为空占位符（`"XXX"`、`"TBD"`、`""` 在必填字段中）
- [ ] 所有 `characters[].feature_anchors` 至少 2 个
- [ ] 所有 `base_versions[].ref_image` 和 `costume_variants[].ref_image` 文件名全项目唯一
- [ ] 所有 `shots[].first_frame_desc` 和 `video_action_desc` 非空
- [ ] 所有 `shots[].review_state` 初始值为 `draft`
- [ ] 所有 `scenes[].value` 非空，且入口极性 ≠ 出口极性（`story_expansion_guide.md` §5.1 价值翻转测试）
- [ ] 主要角色（出对白）的 `want` / `need` / `ghost` 非空，且 `want` 与 `need` 存在冲突（§3.1 判据）
- [ ] 所有 `scenes[].line` 取值为 `A`/`B`/`sub` 之一（`B`/`sub` 场景建议带 `payoff_ref`）
- [ ] `scenes[].value` 与 `script_outlines.md` 对应场景卡一致；确需修改先回 0d 改卡
- [ ] 所有 `props[].role` 非空且为六种作用之一（结构核心/矛盾助推器/刻画/象征/主题窗口/载体）；`role=结构核心` 的道具 `appears_in_shots` 覆盖 payoff 所在单元（高潮亲登场）
