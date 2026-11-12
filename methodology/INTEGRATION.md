# 集成说明：把"谋略方法论"嵌入 SKILL.md

本文件给出可直接粘贴到包根 `SKILL.md` 的片段，以及打包、校验命令。
（最终压缩包由打包步骤生成；此处只描述契约，避免与其它层重复产出。）

> **落地状态（L0 入口层已交付）**：`SKILL.md` 已按本文件的 §1/§2 骨架落地在包根目录，
> 并新增了 `QUICKSTART.md` / `ROUTING.md` / `INDEX.json` / `qixia.py` / `prompts/`。
> 因此日常校验与打包请直接用统一入口：
> `python3 qixia.py doctor`（体检）与 `python3 qixia.py pack`（打包 + sha256）；
> §4 的原始命令保留作为底层对照。

---

## 1. SKILL.md frontmatter 建议

```yaml
---
name: qixia
description: 以《十日终焉》主角齐夏的谋略与博弈方法为核心的 agent 技能：规则侦察与隐藏规则识别、规则欺骗与反欺骗、连环计与局中局、对赌与承诺设计、心理战与攻心；配套可计算的博弈论模型与可检索的模式库。
version: 0.1.0
tags: [strategy, game-theory, negotiation, red-team, rules-audit, deception-defense]
entrypoints:
  methodology: methodology/README.md
  pattern_index: methodology/patterns.index.json
  casebook: methodology/casebook.yaml
  cli: methodology/scripts/pattern_cli.py
  validate: methodology/scripts/validate.py
  gt_engine: scripts/gt/qixia_gt.py
---
```

## 2. SKILL.md 正文建议骨架（可整段复制）

```markdown
# 齐夏 skills

## 这个技能解决什么问题
在**规则不完全公开、对手拥有信息或权限优势、且失败代价不可逆**的博弈中，
先弄清"这张桌子上有几套规则"，再设计让对方"赢了也没用、输了就致命"的局。

## 三条铁律（任何行动前必读）
1. 先算"不做"的收益（是否存在不动即胜的解）。
2. 任何计划必须有第二计（主计 / 备用计 / 脱身计）。
3. 只用于对抗性博弈、谈判、红队演练与规则审计；不用于对真实个人实施欺诈、胁迫或诱导自伤。

## 工作流（默认路径）
1. `python3 methodology/scripts/pattern_cli.py eight` —— 跑一遍谋略八问，确认信息缺口。
2. `python3 methodology/scripts/pattern_cli.py match "<你的情境>"` —— 定位主模式。
3. `python3 methodology/scripts/pattern_cli.py show <P?>` —— 读触发条件与执行步骤。
4. `python3 methodology/scripts/pattern_cli.py premortem <P?>` —— 事前验尸，先排失败条件。
5. 需要定量结论时，调用 `scripts/gt/qixia_gt.py`（见 `reports/gt/*.md` 的既有结果）。
6. 落地前跑 `python3 methodology/scripts/validate.py` 确认引用的模式与案例都真实存在。

## 核心方法论（章节目录）
- 总纲：`methodology/00-methodology-overview.md`（三差模型 / 五层拆解 / 八问 / 路由表）
- P1 规则侦察与隐藏规则识别：`methodology/01-rule-recon.md`
- P2 规则欺骗与反欺骗：`methodology/02-rule-deception.md`
- P3 连环计与局中局：`methodology/03-nested-plans.md`
- P4 对赌与承诺设计：`methodology/04-bets-commitment.md`
- P5 心理战与攻心：`methodology/05-psych-warfare.md`

## 案例与证据
- 深度案例 23 条 + 章节级谋略索引 37 条：`methodology/casebook.yaml`
- 原文基线：`knowledge/sources/shiri_baike.txt`（百度百科词条纯文本，md5 f3e1fe1a…）
- 博弈论模型：`cases/gt/*.json` → `scripts/gt/qixia_gt.py` → `reports/gt/*.md`
```

## 3. 层间映射约定（供后续自动化使用）

| 方法论产物 | 机器可读位置 | 被谁消费 |
|---|---|---|
| 模式（触发/步骤/失败/反制/checklist） | `methodology/patterns.index.json` → `patterns[]` | `pattern_cli.py`、agent 规划器 |
| 模式 ↔ 博弈论模型 | `patterns[].gt_refs` | `validate.py` 校验存在性；agent 按需调用模型 |
| 案例（深度） | `methodology/casebook.yaml` → `cases[]` | 讲解、溯源、测试用例生成 |
| 案例（标题级线索） | `methodology/casebook.yaml` → `chapter_cases[]`，`evidence: chapter_title` | 只可作为**线索**，不可当剧情事实引用 |

## 4. 打包与校验（供最终交付步骤执行）

```bash
cd <workspace>
python3 qixia-skills/methodology/scripts/validate.py     # 必须 0 错误 0 警告
python3 qixia-skills/methodology/scripts/pattern_cli.py list >/dev/null   # CLI 冒烟测试
zip -r -X qixia-skills.zip qixia-skills -x '*.pyc' -x '*/__pycache__/*'
sha256sum qixia-skills.zip
```

## 5. 验收清单

- [ ] `validate.py` 输出"校验通过 ✅"（模式 5、深度案例 23、章节索引 37）
- [ ] `pattern_cli.py` 的 `list / show / match / check / premortem / eight / route` 全部可运行且无第三方依赖
- [ ] 每个模式在 `patterns.index.json` 中五要素齐全，且在对应 `.md` 中有同名章节
- [ ] 每个模式的 `gt_refs` 指向的 `cases/gt/*.json` 真实存在
- [ ] 案例中"标题级证据"与"剧情事实"严格区分（`evidence: chapter_title`）
- [ ] SKILL.md 已包含 §2 的铁律与工作流，且指向本目录的六个文件
