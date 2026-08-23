# GPT-image-2 提示词模板库

所有模板都经过实测验证。按场景选模板，填空即可用。

## 目录
- [通用三原则](#通用三原则)
- [模板 1：grid_icons（4×4 icon 集）](#模板-1grid_icons4x4-icon-集)
- [模板 2：grid_characters（3×3 角色集）](#模板-2grid_characters3x3-角色集)
- [模板 3：grid_tcg_cards（4×4 或 5×5 卡牌）](#模板-3grid_tcg_cards4x4-或-5x5-卡牌)
- [模板 4：grid_chinese_cards（4×4 中文知识卡）](#模板-4grid_chinese_cards4x4-中文知识卡)
- [模板 5：chinese_scroll（1:3 竖幅书法）](#模板-5chinese_scroll13-竖幅书法)
- [模板 6：chinese_couplets（3:1 横幅对联）](#模板-6chinese_couplets31-横幅对联)
- [模板 7：single_illustration（单张插画）](#模板-7single_illustration单张插画)
- [模板填空指南](#模板填空指南)

## 通用三原则

所有模板都遵循：

1. **禁画辅助元素**：`no grid lines, no borders, no registration marks, no text labels`
2. **虚拟网格描述**：`Imagine the canvas divided into N×M cells`
3. **风格一致性**：`pick ONE coherent visual style and apply it uniformly`

## 模板 1：grid_icons（4×4 icon 集）

**适用**：批量生成游戏道具、UI 图标、贴纸、表情、纹章等简单图形。

```
Generate a 4×4 grid of {ICON_THEME} icons on a 1024×1024 canvas. 
Imagine the canvas divided into 16 equal 256×256 cells arranged in 
4 rows and 4 columns. Place one icon centered in each cell, filling 
~70% of cell area. Icons must not cross cell boundaries.

Style: {STYLE_DESCRIPTION}. Pure black silhouettes with clean edges, 
or saturated flat colors with bold outlines. No drop shadows, no 
gradients, no 3D effects.

Icons in reading order (left-to-right, top-to-bottom):
1. {ICON_1}
2. {ICON_2}
...
16. {ICON_16}

Pure white background everywhere. No text, no numbers, no labels, 
no grid lines, no borders.
```

**填空示例**：
- `ICON_THEME` = "fantasy RPG inventory"
- `STYLE_DESCRIPTION` = "bold black silhouettes, clean vector style"
- 16 个 icon 依次列出

## 模板 2：grid_characters（3×3 角色集）

**适用**：游戏角色集、IP 角色、人物立绘。

```
Generate a 3×3 grid of {CHARACTER_SET} on a 1536×1536 canvas. 
Imagine the canvas divided into 9 equal 512×512 cells in 3 rows × 
3 columns. Place one character centered in each cell, full body, 
filling ~70% of cell height. Characters must not cross cell 
boundaries.

{OPEN_OR_SPECIFIC}

Pure white background everywhere. No text, no logos, no ground 
shadows, no signatures, no grid lines, no borders.
```

**两种填法**：

**A. 具体指定版**（用于已知 IP）：
```
CHARACTER_SET = "Street Fighter characters"
OPEN_OR_SPECIFIC = "Characters in reading order:
1. Ryu
2. Ken Masters
3. Chun-Li
4. Guile
5. Zangief
6. Dhalsim
7. E. Honda
8. Blanka
9. M. Bison (Dictator)

Art style: Capcom's official arcade illustrations, bold flat-shading, 
thick black outlines, saturated colors."
```

**B. 开放式版**（让 AI 自由发挥，出图常常更好）：
```
CHARACTER_SET = "Street Fighter characters"
OPEN_OR_SPECIFIC = "Your call on who to include and what art style 
to use — but pick ONE coherent visual style and apply it 
consistently to all 9 characters. Surprise me."
```

**关键**：对熟知 IP，开放式版经常出图更准，因为 AI 调用视觉记忆比强约束更精准。

## 模板 3：grid_tcg_cards（4×4 或 5×5 卡牌）

**适用**：TCG 卡牌、图鉴、收藏集。

### ⚠️ 关键教训

TCG 卡是 **2:3 纵向**。早期用 1536×1536 方形画布生成 5×5 卡牌会导致末行压缩 18%（数学上不可能：25 张纵向卡不能舒适放进方形画布）。**解决方案：画布匹配卡牌比例 + 人格化指令**。

### 推荐模板（人格化 + 自适应画布）

```
You are a card game production manager overseeing the printing of a 
{TOTAL}-card collection. Your professional standard is absolute: every 
physical card must have identical dimensions — you would reject any 
production batch with varying card heights. Show {TOTAL} finished 
cards laid out in a {ROWS}-row × {COLS}-column grid, as if 
photographed for a product catalog.

Cards are standard TCG proportions (2:3 portrait). Choose a canvas 
aspect ratio that displays all cards at their natural proportions 
without compression — suggested: {CANVAS_HINT} or similar 2:3 ratio.

Theme: {CARD_THEME}. Art style: {STYLE_REF}. Pick ONE coherent 
visual direction across all {TOTAL} cards.

Each card has its own frame and border as part of the artwork. 
Cards are physical objects on a clean white surface — nothing else 
exists in the frame.

Leave name/stat areas blank or with decorative shapes. No text, no 
numbers, no logos.
```

**填空建议**：

| 网格 | TOTAL | CANVAS_HINT |
|------|-------|-------------|
| 4×4 | 16 | 1536×1536（方）或 1280×1920（2:3）|
| 5×5 | 25 | 1600×2400（2:3 竖幅）或 **2000×1600**（5:4 横幅也可）|

- `CARD_THEME` = "fantasy" / "sci-fi" / "monster taming"
- `STYLE_REF` = "Hearthstone / Magic: The Gathering / Yu-Gi-Oh inspired"

### 为什么这个模板好

**人格化（"production manager"）**：AI 的角色信念里包含"拒绝不一致产出"，压缩末行违背了它扮演的角色。
**自适应画布**：把"选尺寸"的权力交给 AI，让它为内容匹配画布，而非反过来。
**物理类比**：卡牌是实体物品，物理上不可变形——消解了"构图压缩"的选项。

## 模板 4：grid_chinese_cards（4×4 中文知识卡）

**适用**：成语卡、古诗卡、历史典故卡、品牌小词典。

```
Generate a 4×4 grid of {CHINESE_THEME} cards on a 1536×1536 canvas. 
Imagine the canvas divided into 16 equal 384×384 cells in 4 rows × 
4 columns. One card per cell, centered, fills ~90% of cell.

Each card contains:
- {MAIN_TEXT} in large bold Chinese characters (arranged {LAYOUT})
- {VISUAL_ELEMENT} depicting the meaning
- Traditional cream/beige rice paper background with subtle texture
- A small red seal stamp in one corner

{ITEM_LIST}

Visual style: traditional Chinese ink painting fused with modern flat 
design. Consistent black ink calligraphy, red seal accents, cream 
paper. All 16 cards share the same layout template.

Pure white background between cards. No English, no pinyin, no modern 
sans-serif fonts, no grid lines, no borders. Ensure every Chinese 
character is rendered accurately and legibly.
```

**填空示例（成语卡）**：
- `CHINESE_THEME` = "Chinese idiom (成语)"
- `MAIN_TEXT` = "The idiom"
- `LAYOUT` = "horizontally or in a 2×2 square"
- `VISUAL_ELEMENT` = "a small hand-drawn ink illustration"
- `ITEM_LIST` = "Pick 16 idioms with strong visual meanings: 画龙点睛、守株待兔、塞翁失马、..."

## 模板 5：chinese_scroll（1:3 竖幅书法）

**适用**：古诗竖幅、书法条屏、禅语卷轴、对联单联。

```
Generate a vertical Chinese calligraphy scroll on a {WIDTH}×{HEIGHT} 
canvas (aspect ratio 1:3). The scroll displays {POEM_OR_TEXT}.

Layout from top to bottom:
- Top: a horizontal plaque (横批) with 2-4 character title
- Middle: the full text written in vertical columns, right to left, 
  in {CALLIGRAPHY_STYLE}
- Below: the author's name in smaller characters
- Bottom right: a red square seal stamp
- Bottom left: a second smaller red oval seal stamp

Cream-colored aged rice paper background with subtle fiber texture. 
Black ink brush strokes with natural variations in thickness and 
saturation. No modern design elements. No pinyin, no English 
translation.

Ensure every Chinese character is rendered accurately and matches 
the actual text.
```

**填空示例**：
- `WIDTH×HEIGHT` = `512×1536`
- `POEM_OR_TEXT` = `"famous classical Chinese poem 登鹳雀楼 by 王之涣 (20 characters): 白日依山尽，黄河入海流。欲穷千里目，更上一层楼"`
- `CALLIGRAPHY_STYLE` = `"traditional regular-script (楷书)"` 或 `"semi-cursive (行书)"`

## 模板 6：chinese_couplets（3:1 横幅对联）

**适用**：春联、对联横轴、店招、励志语录横幅。

```
Generate a horizontal Chinese calligraphy banner on a {WIDTH}×{HEIGHT} 
canvas (aspect ratio 3:1). Display {N} {CONTENT_TYPE} arranged side 
by side, evenly spaced.

Each unit shows:
{UNIT_STRUCTURE}

Cream rice paper background. Black brush ink calligraphy. Small red 
seal stamps at natural positions. No modern fonts, no English, no 
pinyin.

Ensure every Chinese character is rendered accurately.
```

**填空示例（多联对联）**：
- `WIDTH×HEIGHT` = `1536×512`
- `N` = `3`
- `CONTENT_TYPE` = `"classical couplets (对联)"`
- `UNIT_STRUCTURE` = `"- Two vertical lines of 7-character couplet
- A central horizontal plaque (横批) of 4 characters above"`

## 模板 7：single_illustration（单张插画）

**适用**：海报、封面、单张插图、文艺图。

```
Generate a single high-quality illustration on a {WIDTH}×{HEIGHT} 
canvas. Subject: {SUBJECT}. Style: {STYLE}.

Composition: {COMPOSITION_NOTES}.

{TEXT_OR_NO_TEXT}

Rendering notes: {QUALITY_NOTES}.
```

**填空示例**：
- `SUBJECT` = `"a traditional Chinese teahouse at dusk, lantern-lit, single figure pouring tea"`
- `STYLE` = `"Studio Ghibli watercolor meets ukiyo-e woodblock"`
- `COMPOSITION_NOTES` = `"wide horizontal composition, rule of thirds, warm color palette, soft atmospheric perspective"`
- `TEXT_OR_NO_TEXT` = `"No text, no captions, no watermarks."`
  或 `"Include a vertical seal stamp with 茶禅一味 on the right side."`
- `QUALITY_NOTES` = `"detailed brush work, subtle gradients, no harsh outlines"`

## 模板 8：grid_sprite_sheet（逐帧动画 sprite sheet）

**适用**：2D 逐帧动画素材、角色动作分解、Cuphead 式手绘动画、游戏 sprite。

### ⚠️ 这是 sprite sheet 制作的全新用例

过去做 sprite sheet 需要动画师一帧帧画。现在一张网格图 + 抠图脚本 = 完整 sprite sheet。经今天实测，**90 字中文 prompt 就能拿到角色一致性极高的 12 帧**。

### 实战 prompt（实测 3 轮迭代收敛，90 字）

```
4×3 网格共 12 帧 sprite sheet。同一{角色}{动作}分解动作：
{关键姿势 1}→{关键姿势 2}→{关键姿势 3}→{关键姿势 4}→{关键姿势 5}。
镜头从{视角方向}拍摄，每帧{角色}站在单元格底部居中。
单元格之间纯白色留白。{风格锚定}，{配色签名}。
```

### 填空示例（骑士挥剑）

```
4×3 网格共 12 帧 sprite sheet。同一骑士挥剑分解动作：
站立→举剑过顶→下劈→击中→收招。镜头从正左侧拍摄，
每帧骑士站在单元格底部居中。单元格之间纯白色留白。
Cuphead 1930 式，黑色粗描边+红披风。
```

### 关键设计（每个字都经过实测验证）

| 元素 | 作用 | 为什么必须是这个措辞 |
|------|------|---------------------|
| `4×3 网格共 12 帧` | 锁定帧数 | 硬数字必须**开头出现**；英文长 prompt 里会被忽略成 5×3=15 |
| `同一{角色}` | 角色一致性锁 | 4 个中文字 > 英文一大段。中文信息密度碾压 |
| `{关键姿势 1→2→3→4→5}` | 动作弧线 | 不给 12 帧逐帧描述，给 5 个关键帧，AI 自动脑补中间帧 |
| `镜头从正左侧拍摄` | 视角约束 | **摄影语言** > 几何语言。「strict side view」AI 不一定听 |
| `每帧{角色}站在单元格底部居中` | 位置锁 | **容器语言**，不要用「同一水平线」（会被画成黑线） |
| `单元格之间纯白色留白` | 抠图必需的 gutter | 顺便强化白底，对抗风格锚定的深色惯性 |
| `Cuphead 1930 式` | 风格锚定 | 4 个字 > 英文 50 字的风格描述 |
| `黑色粗描边+红披风` | 配色签名 | 2 个元素的颜色标签胜过色值描述 |

### 迭代路径（骑士挥剑实测）

| 版本 | 帧数结果 | 背景 | 角色一致 | 核心问题 |
|------|---------|------|---------|---------|
| v1：英文 600 字全堆砌 | ❌ 15 帧 | ❌ 深色渐变 | ✅ | 长 prompt 让硬约束被稀释 |
| v2：中文 92 字，含「水平线」 | ✅ 12 帧 | ✅ 纯白 | ✅ | 「同一水平线」被画成黑线 |
| v3：换成「单元格底部居中」 | ✅ 12 帧 | ✅ 纯白 | ✅ | 仅视角锁定失败（被 Cuphead Q 版视觉惯性覆盖）|

### 视角锁定的最后一招

如果用 Cuphead 风格但想要严格侧视，**风格锚定换功能类别**：

```
把「Cuphead 1930 式」→ 换成「2D 横版动作游戏 sprite sheet」
```

原因：Cuphead 是**美学风格**，AI 调 BOSS 战正面视角；「2D 横版游戏 sprite」是**功能类别**，AI 直接调 profile 侧视训练数据。

### 其他场景改造

- **跑步循环**（8 帧循环）：`3×3 网格共 8 帧...{角色}跑步循环`（第 9 格可空，或做 idle 帧）
- **攻击组合**（16 帧完整连招）：`4×4 网格共 16 帧...{角色}三段斩组合`
- **表情变化**（9 帧情绪序列）：`3×3 网格共 9 帧...{角色}从平静到愤怒的 9 个表情`

## 模板填空指南

### 风格锚定短语库（实测有效）

| 想要的感觉 | 锚定短语 |
|----------|---------|
| 街霸/格斗游戏 | `Capcom's official arcade illustrations` |
| 炉石/厚涂卡牌 | `Hearthstone style` |
| MTG/奇幻厚涂 | `Magic: The Gathering card art` |
| 宫崎骏水彩 | `Studio Ghibli style` |
| 粗描边日漫 | `Guilty Gear Strive portraits` |
| 水墨画 | `traditional Chinese ink painting` |
| 扁平矢量 | `minimalist flat design with bold black outlines` |
| 像素风 | `1990s arcade pixel art` |
| 浮世绘 | `ukiyo-e woodblock print` |
| 苹果插画 | `Apple Human Interface illustration style` |

### 禁画清单（粘贴到任何模板）

```
No text, no logos, no watermarks, no signatures, no ground shadows, 
no grid lines, no borders, no registration marks, no pinyin, no 
English captions, no modern sans-serif fonts crossing traditional 
elements.
```

### 质量强调短语（加在结尾）

- **中文准确**：`Ensure every Chinese character is rendered accurately and legibly.`
- **风格一致**：`Apply the chosen style uniformly to all elements.`
- **无污染**：`The background between elements should be completely clean and white.`
- **物理类比**（治 5×5 末行压缩）：`Think of this as a photograph of identical manufactured items, not a hand-drawn layout.`

### 常见错误纠正

- ❌ `"Make sure cards are same size"` → ✅ `"EVERY card has IDENTICAL dimensions. Think of physical manufactured cards."`
- ❌ `"Don't draw grid"` → ✅ `"Do NOT draw any grid lines, borders, or registration marks"`
- ❌ `"Asian style"` → ✅ `"traditional Chinese ink painting"`（具体到技法）
- ❌ `"Hearthstone-like"` → ✅ `"Hearthstone style"`（简洁直接）

### 如果出图不理想的调整顺序

1. **先降密度**（5×5 → 4×4 → 3×3）看是否变稳
2. **再换风格锚定**（可能锚定到了 AI 不熟的风格）
3. **最后加约束**（禁画清单 + 质量强调）

## 词汇选择心法（2026-04-22 sprite sheet 实测沉淀）

这四对是 prompt 工程最高杠杆的认知，每一对都是一次真实的失败换来的。

### 1. 容器语言 > 几何语言

**关于位置/对齐的约束**，用物理容器的语言，不用抽象几何的语言。

| ❌ 几何语言 | AI 的误解 | ✅ 容器语言 |
|-----------|----------|-----------|
| `脚底对齐同一水平线` | 真的画一条黑线 | `每帧角色站在单元格底部居中` |
| `aligned along a grid` | 画出网格线 | `arranged in cells` |
| `same baseline` | 画出基线 | `positioned at the bottom of each cell` |
| `centered on a vertical axis` | 画出轴线 | `centered within each cell` |

**为什么**：AI 对「line / axis / baseline」这类几何名词有字面理解的倾向——它们是视觉元素可以被画出来。而「cell / frame / container」是空间容器概念，AI 理解成位置关系但不会画出来。

### 2. 功能类别 > 美学风格（当想要特定视角时）

**风格锚定词会调用整套视觉惯性，包括视角**。想要打破这个惯性，用功能类别词。

| 想要 | ❌ 美学风格（调惯性）| ✅ 功能类别（调训练数据）|
|------|-------------------|----------------------|
| 严格侧视 sprite | `Cuphead 风格` | `2D 横版动作游戏 sprite sheet` |
| 正面肖像 | `magazine style` | `passport photo / headshot` |
| 45 度俯视 | `isometric art` | `tactical RPG game tile` |
| 鱼眼视角 | `surreal style` | `action camera / security camera footage` |

**为什么**：美学风格 = AI 记忆里的「这个美学的代表作长啥样」，包含视角惯性。功能类别 = AI 记忆里的「这类用途的图片长啥样」，视角由功能决定。

### 3. 中文 > 英文（信息密度 2 倍杠杆）

实测对比：同一个 sprite sheet 需求，英文 600 字失败，中文 92 字成功。

| 英文长 prompt | 中文短 prompt |
|-------------|-------------|
| 600+ tokens | 90+ 字符 |
| 硬约束被稀释（15 帧而非 12） | 硬约束精准命中（12 帧） |
| AI 抓主视觉忽略细节 | 每一条都成为硬指令 |
| 风格描述冗长 | 「Cuphead 1930 式」4 字搞定 |

**为什么**：中文单字信息密度约 2× 英文。gpt-image-2 的中文理解能力被严重低估——它不只能生成中文，也能理解中文 prompt（且理解得更精准，因为 token 更集中）。

**落地规则**：对于硬约束多、字数敏感的场景（网格数量、帧数、位置对齐），**优先用中文写 prompt**。

### 4. 硬数字前置 + 符号强化

硬数字（帧数、网格、尺寸）要**开头出现**，且用**符号包裹**让 AI 识别为「关键约束」而非描述文本。

| ❌ 弱 | ✅ 强 |
|------|------|
| `...arranged in 12 cells in a grid of 4 by 3...` | `4×3 共 12 帧...`（开头 + 数学符号）|
| `around 16 characters` | `16 角色` 或 `【16】`（括号强化）|
| `using 3 to 5 columns` | `3 列` 或 `5 列`（消除范围歧义）|

**为什么**：AI 在长文本里容易「概括」而不是「精确执行」。数字开头 + 符号包裹，让它感知到这是 spec 而非描述。

## 今天漏掉的其他认知（防踩重复）

- **「no X」禁止清单经常失效**：AI 在 Cuphead 语境里主动加了 ★ 和烟雾——我们写了「无文字」但它判定这是 sprite sheet 的合理冲击特效，于是保留。**结果是对的**。规则：AI 对 sprite sheet 的「该加什么特效」有自己的常识，不要过度禁止
- **风格锚定的反作用力**：「Cuphead 1930 式」成功锁住视觉，但把「严格侧视」覆盖了。强风格锚定 = 牺牲了一部分几何约束的执行力。权衡时记着
- **动作弧线用 5 关键帧描述胜过 12 逐帧描述**：AI 会脑补中间帧，给 5 个转折点（如「站立→举剑→下劈→击中→收招」）比写 12 条每一帧的动作更有效
4. **多跑几次**（GPT-image-2 有随机性，跑 3 次挑最好）
