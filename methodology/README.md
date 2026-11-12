# 齐夏 skills · 谋略方法论层（methodology）

本目录是 skills 的**核心方法论章节**：把《十日终焉》中已确认的案例抽象成 5 个可复用谋略模式，
每个模式都带 **触发条件 / 执行步骤 / 失败条件 / 反制手段 / 案例锚点 / checklist**，
并提供机器可检索的索引与两个零依赖脚本。

## 目录结构

```
methodology/
├── 00-methodology-overview.md   总纲：三差模型、五层拆解、谋略八问、路由表、三条铁律
├── 01-rule-recon.md             P1 规则侦察与隐藏规则识别（含元层"目标审查"）
├── 02-rule-deception.md         P2 规则欺骗与反欺骗（含 16 条恶意条款语法，仅作审计用）
├── 03-nested-plans.md           P3 连环计与局中局（五层结构 + 切换时点 + 第二计）
├── 04-bets-commitment.md        P4 对赌与承诺设计（七要素 + 不可撤回装置 + 两军问题）
├── 05-psych-warfare.md          P5 心理战与攻心（五杠杆 + 12 句工具箱 + 执念审计）
├── patterns.index.json          机器可读索引（模式/触发/步骤/失败/反制/案例/gt_refs）
├── casebook.yaml                案例库：23 条深度案例 + 37 条章节级谋略索引
└── scripts/
    ├── pattern_cli.py           检索与调用 CLI（标准库，无依赖）
    └── validate.py              完整性/自洽性校验（标准库，无依赖）
```

## 快速开始

```bash
cd qixia-skills/methodology

python3 scripts/pattern_cli.py list                 # 五个模式一览
python3 scripts/pattern_cli.py match "只有口头规则，还有个裁判有最终解释权"
python3 scripts/pattern_cli.py show P1              # 全貌（触发/步骤/失败/反制/案例/checklist）
python3 scripts/pattern_cli.py premortem P3         # 事前验尸：这个模式会怎么死
python3 scripts/pattern_cli.py check P4             # 打印 checklist（可直接当执行清单）
python3 scripts/pattern_cli.py eight                # 谋略八问（未知环境先跑这个）
python3 scripts/pattern_cli.py route                # 情境 → 模式 路由
python3 scripts/pattern_cli.py show P1 --json       # 机器可读输出
python3 scripts/validate.py                         # 校验通过 ✅
```

## 五个模式（速览）

| ID | 名称 | 一句话 | 风险 | 典型场景 |
|---|---|---|---|---|
| **P1** | 规则侦察与隐藏规则识别 | 先弄清"这张桌子上有几套规则" | 低 | 进入新环境、只有口头规则、存在裁判 |
| **P2** | 规则欺骗与反欺骗 | 在对手脑内安装一套错误规则；同时把"相信"降级为可验证 | 高 | 规则对我不利、文本有矛盾/自指条款 |
| **P3** | 连环计与局中局 | 让对手在错误的层级上做最优决策 | 极高 | 对手单维度强于我、必须隐藏意图 |
| **P4** | 对赌与承诺设计 | 把未来不确定性换成现在可判定的结果 | 高 | 需要可信承诺、拖不起、隔空协同 |
| **P5** | 心理战与攻心 | 改变对方计算的**输入**，而非计算本身 | 高 | 理性打平、对手有权重情绪弱点、需稳军心 |

## 与 skills 其他层的接口

| 层 | 位置 | 关系 |
|---|---|---|
| 博弈论模型层 | `../cases/gt/*.json`、`../scripts/gt/qixia_gt.py` | 本层每个模式用 `gt_refs` 指向可计算的模型输入；方法论给"为什么"，模型层给"算多少" |
| 计算结果层 | `../reports/gt/*.md` | 模型层的输出，用于校验方法论中的定量断言 |
| 证据基线 | `../knowledge/sources/shiri_baike.txt` | 全部案例的原文来源（md5 `f3e1fe1a…`，66490 字符 / 3533 行） |

## 使用纪律（写在最前面）

1. **先算"不做"的收益**：是否存在"什么都不动就能赢"的解（跷跷板、免佣门槛、滚池）。
2. **任何计划必须有第二计**：主计 / 备用计 / 脱身计，只有一计叫"赌"。
3. **合规边界**：本方法论面向对抗性博弈、谈判、红队演练与规则审计；
   其中"合同陷阱语法"仅作**防御性审计清单**使用，不得用于对真实个人实施欺诈、胁迫或诱导自伤。

## 维护

- 增补模式：在 `patterns.index.json` 加对象（必填字段见 `required_fields`），在 `casebook.yaml` 登记案例，
  然后 `python3 scripts/validate.py` 必须为 0 错误 0 警告。
- 增补案例：`cases`（深度，带原文要点）与 `chapter_cases`（标题级索引，`evidence: chapter_title`）分开登记，
  **标题级证据不得写成剧情事实**。
