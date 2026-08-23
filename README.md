<div align="center">

# huashu-gpt-image

> *「你缺的不是 prompt 技巧，是那个名字。」*
> *GPT-image-2 的 prompt 工程方法论。*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent-Agnostic](https://img.shields.io/badge/Agent-Agnostic-blueviolet)](https://skills.sh)
[![Skills](https://img.shields.io/badge/skills.sh-Compatible-green)](https://skills.sh)

<br>

**封面 · 海报 · 信息图 · UI mockup · 产品包装 · 批量 icon/角色/卡牌 · 中文书法**

<br>

大多数人写 AI 生图 prompt 的方式是堆形容词：「高级感、现代、简约、有质感、
专业的、精致的」。堆得越多，出来的图越像所有 AI 图。

而这条 prompt 只有 16 个字：

```
Dieter Rams 风格的大疆 pocket3 说明书
```

拿到的是一份完整 A4 说明书，含真实参数，视觉精度到官方手册级别。

差别不在技巧，在**你知不知道 Dieter Rams 是谁**——他的东西长什么样、
为什么他配这个产品。**模型的视觉记忆里有他，前提是你去调他。**

```
npx skills add alchaincyf/huashu-gpt-image
```

跨 agent 通用——Claude Code、Cursor、Codex、OpenClaw、Hermes 都能装。

[核心方法](#核心方法概念压缩比) · [四条红线](#四条红线) · [装上就能用](#装上就能用) · [批量生成](#批量生成) · [出图之后](#出图之后)

</div>

---

## 核心方法：概念压缩比

**prompt 的有效信息 ≠ prompt 的字数。决定输出质量的是单字承载的设计决策密度。**

写 prompt 之前先问一句：**主体 / 风格 / 媒介**三个槽位，能不能各填一个模型
熟知的高频名字？

| | 堆形容词 | 填名字 |
|---|---|---|
| 主体 | 「一个便携相机」 | 大疆 pocket3 |
| 风格 | 「简约、高级、德国工业感」 | Dieter Rams |
| 媒介 | 「产品介绍页面」 | 说明书 |

三个槽都填上了 → 短 prompt 就够。有空槽 → 那个槽位才需要结构化描述补足。

所以这个 skill 真正在训练的不是 prompt 写法，是**你脑子里的概念库**：
设计师、品牌、媒介范式，每多认识一个精准的名字，你的上限就抬高一点。

---

## 四条红线

违反任何一条都是 AI slop。完整规则见 [`SKILL.md`](SKILL.md)。

**一、prompt 默认写中文。**
模型对中英文理解能力完全对等，但中文更精炼（一个汉字 ≈ 2-3 个英文 token）。
英文段落式 prompt 是模型训练数据的默认输出，也是 AI 味的来源。
`Subject:` / `Style:` / `Constraints:` 这种伪结构化 header 同样禁止。

**二、图里的文字也默认中文。**
读者是中文用户，图上出现「Perception Gap」「Mainstream path」是隔阂不是高级感。
GPT-image-2 的中文准确率支持 20+ 字符，出中文不是问题。

**三、用真实参考名替代形容词。**
Dieter Rams / Penguin Books / MUJI / Anthropic / 瑞士国际主义 ——
一个名字调动的视觉记忆，比十个形容词精确得多。

**四、Placeholder > 烂实现。**
没有真实数据就留白，不要编造看起来像数据的假数据。

---

## 装上就能用

```bash
npx skills add alchaincyf/huashu-gpt-image
```

装完直接说人话：

```
"给这篇文章做个封面"        → 走配图 SOP，定家族 → 挑 ref → 生成
"做一套 12 个 icon"        → 批量生成，网格切图
"这张图重新出，字太小"      → 按失败模式树对症改
"做个产品对比信息图"        → 单图 playbook
```

**生成执行层**支持两条路径：

| 路径 | 什么时候用 |
|---|---|
| `scripts/gen_via_codex.py` | Codex 环境，走内置 image_gen |
| `chatgpt-web-bridge/` | 通过 Chrome 扩展 + 本地桥调 ChatGPT 网页版 |

本地桥只监听 `127.0.0.1:8765`，不对外暴露。

---

## 批量生成

icon 集 / 角色集 / 卡牌集 / sprite sheet / 中文长文本，走网格法：
一次生成一张大图（如 4×3 网格），再用 `scripts/extract_grid.py` 切成单张。

比逐张生成快一个数量级，而且**同一张图里的元素风格天然一致**——
这是逐张生成很难做到的。

但有个坑，是实测踩出来的：**别硬性锁死画布尺寸，让比例匹配内容**。
早期用 1:1 画布生成 5×5 的 2:3 纵向卡，末行被压缩了 18%——
模型在约束冲突时会自发牺牲末行来「保住构图完整」，而且不会告诉你。

配套脚本：

| 脚本 | 干什么 |
|---|---|
| `extract_grid.py` | 网格大图切成单张 |
| `contact_sheet.py` | 多张图拼成审阅用的联系表 |
| `chroma_key.py` | 抠掉纯色背景转透明 |

---

## 出图之后

生成不是终点。skill 内置一棵**失败模式树**——出图后对症查：

- 文字糊了 / 缺笔画 → 字号与字数上限
- 出现外文水印 / nameplate → prompt 里的负向约束写法
- 风格漂移 → ref 垫图的用法
- 人物崩坏 / 手部异常 → 构图与视角调整

每一条都对应具体改法，不是「再试一次」。

---

## 方法论出处

| 来源 | 用在哪 |
|---|---|
| Dieter Rams《设计十诫》 | 工业设计类 prompt 的风格锚点 |
| Penguin Books / MUJI / Anthropic 品牌视觉 | 出版与品牌类的媒介范式 |
| 瑞士国际主义平面设计 | 版式与网格系统 |
| GPT-image-2 官方能力文档 | 尺寸、字符数、批量的硬约束 |

skill 里所有风格锚点都是**真实存在、模型确实认识**的名字，
不是编出来的「某某风」。

---

## License

MIT
