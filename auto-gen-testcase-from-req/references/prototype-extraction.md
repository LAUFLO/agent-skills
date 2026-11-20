# 原型文件解析

用于从 HTML 原型中提取真实控件、表头、弹窗字段和默认值，作为用例步骤与断言依据。

## 1. 判断文件类型

| 特征 | 类型 | 处理 |
|---|---|---|
| 含 `__bundler/template`、`__bundler/manifest`、`__resources` | 打包 HTML | 按第 2 节解包 |
| 普通静态 HTML，可直接看到业务 DOM | 静态 HTML | 按第 3 节提取 |
| 需要登录才能访问的在线原型 | 在线页面 | 让用户提供截图或导出 HTML，不反复尝试登录 |

打包 HTML 的页面通常显示「Unpacking...」或「This page requires JavaScript to display」，直接读源码只能看到加载壳。

## 2. 解包打包 HTML

模板内容在 `<script type="__bundler/template">` 中，是一段 JSON 字符串；页面资源在 `__resources` 中。

Python 解包脚本：

```python
# -*- coding: utf-8 -*-
import json
import re

path = r"原型文件路径.html"
raw = open(path, "rb").read()

text = None
for enc in ("utf-8", "gbk", "gb18030"):
    try:
        text = raw.decode(enc)
        break
    except UnicodeDecodeError:
        continue

# 提取 template 脚本内容
m = re.search(
    r'<script[^>]*type="__bundler/template"[^>]*>([\s\S]*?)</script>',
    text,
)
if not m:
    raise SystemExit("未找到 __bundler/template，可能不是打包 HTML")

html = json.loads(m.group(1).strip())
open("template.html", "w", encoding="utf-8").write(html)

# 生成纯文本版，便于快速查看页面结构
plain = re.sub(r"<style[\s\S]*?</style>", " ", html)
plain = re.sub(r"<(script|helmet)[\s\S]*?</\1>", " ", plain)
plain = re.sub(r"<[^>]+>", "|\n", plain)
plain = re.sub(r"\|{2,}", "|", plain)
plain = re.sub(r"[ \t]+", " ", plain)
open("template.txt", "w", encoding="utf-8").write(plain)
```

解包后优先查看 `template.txt` 的控件顺序，再看 `template.html` 确认属性与默认值。

## 3. 提取清单

按以下顺序记录，每项写入控件清单并映射到用例：

1. 页面标题与导航路径。
2. 筛选控件：名称、类型（输入/下拉/日期）、默认值、选项。
3. 操作按钮：查询、重置、导出、刷新、列设置。
4. 指标卡：名称、单位、副标题。
5. 汇总卡：名称、展示字段。
6. 表头分组与字段顺序。
7. 表格行内可点击元素。
8. 弹窗标题、字段、空态文案、关闭方式。
9. 分页器与排序标识。
10. 页面空态文案。

## 4. 动态内容处理

- 模板中的 `{{ 变量 }}`、`sc-for`、`sc-if` 是渲染占位，记录其语义名称，不把占位符写进用例。
- 内联脚本中的 `ROWS`、`kpis`、`stats` 等数组可确认字段名与计算规则，但不得把原型示例数据当作真实测试数据。
- 原型中的示例人名、供应商名、金额只用于理解结构，不写入用例。

## 5. 与 PRD 差异

- 逐项对比筛选控件、表头字段、弹窗字段、计算规则。
- 差异写入待确认清单，由用户确认以 PRD 还是原型为准。
- 确认前不生成受影响断言；确认后按结论编写，并在「需求确认结果」表中记录。
- 不得以「原型就是这样」为由跳过 PRD 的明确要求。

## 6. 编码与乱码

- 文件头 `meta charset` 可能与实际编码不一致。
- 按 UTF-8、GBK、GB18030 依次尝试解码。
- PowerShell 管道输出中文可能乱码，优先用 Python 写文件后再读取。
- 终端显示乱码不代表文件内容错误，以写入后的 UTF-8 文件为准。
