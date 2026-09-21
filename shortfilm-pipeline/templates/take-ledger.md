# shot-XX Take 台账（P4 模板，每镜一份，放在 04-takes/shot-XX/）

> 镜头：shot-XX ｜ 提示词当前版本：vNNN ｜ 目标模型：Agnes Video 2.5 Flash

| Take | 提示词版本 | video_id | seconds | aspect_ratio | seed | 生成日期 | 结论 |
|---|---|---|---|---|---|---|---|
| T001 | v001 | <video_id> | 10 | 16:9 | - | 2026-xx-xx | 保 / 废（一句原因） / 修（一句原因+改哪个字段） |
| T002 | v002 | … | 10 | 16:9 | … | … | … |

## 段间衔接（>12s 分段生成时）
- 段顺序：seg1(x s) → seg2(y s) → …
- 每段衔接方式：reference（在线URL） / keyframe（first_frame=上段尾帧）
- 拼接：ffmpeg 归一化后合并，成片存 `04-takes/shot-XX/`，命名 `shot-XX-final.mp4`

## 登记规则
- 每个 Take 一行，只增不删；"修"必须写清改动字段与变量（一次只改一个关键变量）
- 重 roll 预算提示：本镜累计 ___ 次（行业预期 5–10 倍终选镜数），超预算先回 P5 方向再重roll
- 存量素材：登记"T000 存量，[来源]，登记日期"

> 阶段移交：[P4/shot-XX] 完成于 [日期] → 下一步 [P5 审稿]，入口条件 [已满足/缺什么]
