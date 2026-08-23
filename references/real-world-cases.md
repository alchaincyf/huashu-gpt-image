# GPT-image-2 实战案例 · 写 prompt 的避坑经验

> 沉淀自 2026-04 「聊聊 skill」 deck 项目，两次成功的 4×2 grid 生成案例。
> 每条经验都来自踩过的坑，可直接复用到类似场景。

---

## 0 · 核心使用场景

**最有价值的场景**：cinematic 动画 / 3D gallery 需要「一组主题相关的真实物件」做素材。

例如：
- 给「费曼蒸馏」demo 做「1960s Caltech 物理档案」8 件物品
- 给「skill 优化」demo 做「Skill 工程师 lab bench」8 件工具
- 给「张小龙产品哲学」demo 做「微信发展史 archival」8 件物品

**反模式**：
- 让 AI 一张张生成（每张 30 秒，8 张要 4 分钟，且风格不一致）
- 用 emoji / SVG 手画代替（丑且无品牌）

**正确做法**：用一张 `4×2 grid · 8 cells` 大图（30 秒生成），脚本抠成 8 张独立 PNG（10 秒），风格完全统一。

---

## 1 · 五条避坑经验

### 1.1 · 白底优先，灰底慎用

**坑**：早期为了氛围用 `mid-grey #2A2A2A` 背景，结果 `extract_grid.py --bg 240` 阈值识别不出灰背景，抠出的 PNG 边缘有灰渣。

**经验**：
- **第一选**：`Pure white background (#FFFFFF)` —— 干净，extract_grid 默认阈值 240 完美工作
- **第二选**：`Off-white #FAFAF7` —— 略带温度但仍易抠
- **避免**：mid-grey / 任何渐变背景 / 任何带纹理的背景

**例外场景**：如果素材最终就是放在浅色 panel 上展示（不需要透明 PNG），灰底反而更有 archival 氛围。

**判断标准**：素材是否需要后续合成到不同背景上漂浮？需要 → 白底。直接用整张 → 灰底可。

---

### 1.2 · 4×2 不要 5×5

**坑**：早期试过 5×5 卡牌生成，末行被 AI 自发压缩 18%，因为画布尺寸（1:1）和内容比例（2:3 卡牌）数学上不可能同时满足。

**经验**：
- **首选 4×2 = 8 张**：1920×1080 画布完美，每格 480×540，刚好放一个物件
- **次选 3×3 = 9 张**：方形画布 1536×1536
- **慎用 5×5**：必须用 `--mode density` 抠图，且画布必须匹配内容比例

**为什么 4×2 是黄金**：
- 8 件物品的 narrative 容量足够（够讲一个故事）
- 比 3×3 少 1 件，去掉「凑数那张」的诱惑
- 16:9 画布天然适配演示页面 / cinematic 横屏

---

### 1.3 · IP 锚定 + Hearthstone-style consistent treatment

**坑**：早期 prompt 写「Feynman-related artifacts, vintage style」，AI 自由发挥，8 件物品风格各异（一张油画质感、一张卡通、一张写实）。

**经验**：在 prompt 里加两个魔法句子：

1. **IP 锚定**（视觉记忆唤起）：
   ```
   1960s-70s Caltech archive aesthetic, vintage academic feel
   ```
   而不是 "vintage style" 这种泛泛描述。具体的时代+机构会唤起 AI 的视觉记忆。

2. **Hearthstone-style consistent treatment**（一致性强约束）：
   ```
   "Hearthstone-style consistent treatment" — these 8 items are 
   a curated set, not random objects. Equal visual weight, 
   no item dominates.
   ```
   这个短语来自 huashu-gpt-image 的「IP 记忆唤起胜过细节堆砌」原则——AI 见过太多 Hearthstone 卡牌，知道「同一套卡牌的统一视觉处理」是什么意思。

---

### 1.4 · Persona Finishing（人格化收尾）

**坑**：纯描述性 prompt 容易让 AI 产出 stock-photo 质感（千篇一律）。

**经验**：在 prompt 末尾加一个 persona 句子，让 AI 进入特定职业角色：

```
Persona: you are a curator preparing a Wired magazine feature on
the engineering of self-improving systems.
```

或：

```
Persona: you are an editorial photographer for Wired magazine — 
make it documentary, not stock-photo.
```

这一句话能把质感从「AI 生成图」拉到「编辑级摄影」。原因：训练语料里 Wired / 博物馆 curator 这类 persona 的图片样本质量都很高。

---

### 1.5 · 60px breathing space + 不画辅助元素

**坑**：AI 自发画分隔线 / 边框 / 标签来「帮助」结构化，结果都是 extract_grid 抠图时的污染源。

**经验**：每个 prompt 必须有这两句：

```
Imagine the canvas divided into a 4×2 grid of 8 cells (480×540 each).
Do NOT draw grid lines, borders, registration marks, or text labels between cells.
60px breathing space within each cell. No item overlaps adjacent cells.
```

- 「Imagine ... grid」让 AI 把网格作为内部空间规划，而不是真的画出来
- 「60px breathing space」给抠图脚本留 padding
- 「No item overlaps」防止物品跨格

---

## 2 · 完整 prompt 模板（经过验证）

### 模板 · 4×2 主题档案 grid

```text
Title: {THEME} Archive · 4×2 grid · 8 thematic items
Canvas: 1920 × 1080 (16:9), high quality

Imagine the canvas divided into a 4×2 grid of 8 cells (480×540 each).
Do NOT draw grid lines, borders, registration marks, or text labels between cells.
Each cell contains ONE distinct artifact related to {THEME}.

UNIFIED STYLE across all 8 items:
- Pure white background (#FFFFFF) — clean studio backdrop, easy to extract
- Each item floats with subtle natural shadow at 30°
- Color palette: {3-4 specific colors}
- Soft directional studio lighting from upper-left
- Still-life product photography, single hero subject per cell
- 60px breathing space within each cell
- {ERA-and-INSTITUTION-anchor, e.g., "1960s Caltech archive aesthetic"}

The 8 items (left→right, top row first):
1. {item 1 with specific details}
2. {item 2 with specific details}
3. ...
8. {item 8 with specific details}

Critical: All 8 items must feel curated for a documentary photo shoot
about "{NARRATIVE-KEY-PHRASE}".
"Hearthstone-style consistent treatment" — equal visual weight, 
no item dominates.

Persona: you are a curator preparing a {AUTHORITATIVE-CONTEXT, 
e.g., "Wired magazine feature on the engineering of self-improving systems"}.
```

**填空建议**：
- `{THEME}`：1-3 个词，IP 锚定（如 "Feynman Knowledge"、"Skill Engineer Lab Bench"）
- `{3-4 specific colors}`：cream paper #F5EFE6 / charcoal ink / occasional rust accent / etc
- `{ERA-and-INSTITUTION-anchor}`：时代 + 机构（"1960s Caltech archive aesthetic"、"1830s Darwinian naturalist notebook"）
- `{NARRATIVE-KEY-PHRASE}`：1 句话点明这组物品讲什么故事
- `{AUTHORITATIVE-CONTEXT}`：知名编辑/博物馆/curator 角色

### 8 个 item 的描述要点

每个 item 的描述要包含 **3 个具体维度**：

```
A worn first-edition copy of "{exact-name}" book, 
showing {specific texture/wear}, 
{angle: 3/4 view / overhead / side},
{additional detail: paperclip / annotation / etc}
```

太抽象（"a book about Feynman"）→ AI 画错；太冗长（10 个形容词）→ AI 抓不住重点。

---

## 3 · 案例对照

### 案例 A · Feynman Knowledge Archive

**触发场景**：cinematic Scene 2 的 3D 知识 orbit，需要 8 件费曼相关物件漂浮。

**Prompt 关键句**：
- IP 锚定：`1960s-70s Caltech archive aesthetic`
- Persona：`you are a museum curator preparing an exhibition catalog photo`
- 8 件物品都是真实存在的（《Surely You're Joking》book / Caltech QED folder / 黑板手稿 / Vol.I 物理讲义 / 手写笔记 / QED 磁带 / Caltech 1965 奖牌）

**抠图命令**：
```bash
python3 extract_grid.py source.png --grid 2 4 --mode bbox \
  --names "01-book-joking,02-folder-qed,03-blackboard-diagrams,..." \
  --out items/
```

**结果**：8 张独立透明 PNG，每张 350-450px，边缘干净。

### 案例 B · Darwin Skill Lab Bench

**触发场景**：cinematic Scene 2 的 lab bench orbit，主题从「物理学家档案」改成「skill 工程师桌面」。

**Prompt 关键差异**：
- IP 锚定：`half engineering, half Darwinian naturalist tradition`（混搭：现代工程 + 1830s 博物学）
- 8 件物品体现「自我评估实验」narrative：v1 SKILL.md（红笔批注）/ v5 SKILL.md（干净）/ 8 维评分卡 / hill-climb 笔记本 / 黄铜卡尺 / 达尔文 1837「I think」树状图 / 复古 stopwatch / git commit 便签
- Persona：`Wired magazine feature on the engineering of self-improving systems`

**为什么对比成立**：两组物品视觉同样品质（都白底 + 摄影级 + unified style），但**叙事完全不同**——一组是「物理学家的工作」，一组是「skill 工程师的科学方法」。

---

## 4 · 抠图配套技巧

### 4.1 · 命名规则

`extract_grid.py --names` 用逗号分隔的名字按 reading order 标记，建议格式：
```
01-{category}-{specific-name}
02-{category}-{specific-name}
...
```

例如：`01-book-joking,02-folder-qed,03-blackboard-diagrams`

输出文件名：`01_01-book-joking.png`（前缀 `01_` 是脚本加的位置编号）

### 4.2 · 阈值调整

默认 `--bg 240` 适合纯白底。如果素材很浅（米白），用 `--bg 250` 或 `--bg 245`。

### 4.3 · 保留 padding

默认 `--pad 0` tight crop。如果素材有阴影想保留，用 `--pad 10` 或 `--pad 20`。

### 4.4 · 验证抠图

抠完后随机看 2-3 张：
```bash
# 浏览器打开（透明背景，会看到棋盘格）
open items/03_03-blackboard-diagrams.png
```

边缘有灰渣 → 调整 `--bg` 阈值
物体被切掉 → 增加 `--pad`
背景没抠干净 → 重新生成（白底没生成对）

---

## 5 · 速查表

| 场景 | 推荐配置 |
|---|---|
| 给 cinematic 做 orbit / gallery 漂浮素材 | 4×2 白底 + persona finishing |
| 单张大图直接用（不抠图） | 任意背景 + 重质感 |
| 中文知识卡 / 国风内容 | `chinese_*` 模板 + 米色底 |
| 游戏 icon / UI 资源 | 4×4 平涂彩色 + 黑描边 |

| 反 pattern | 正 pattern |
|---|---|
| "vintage style" | "1960s Caltech archive aesthetic" |
| "8 books" | 8 个具体 book 描述（书名 / 颜色 / 角度 / 磨损） |
| 灰底 + 想抠透明 | 白底 + extract_grid bbox |
| 5×5 grid | 4×2 / 3×3 grid |
| 自由发挥风格 | "Hearthstone-style consistent treatment" |
| 描述性 prompt 结尾 | persona finishing（"you are a Wired editor"）|
| 让 AI 画分隔线辅助 | "Imagine the grid, do NOT draw grid lines" |
