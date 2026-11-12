---
name: qixia
description: 以《十日终焉》主角齐夏的谋略与博弈方法为核心的 agent 技能包：规则侦察与隐藏规则识别、规则欺骗与反欺骗、连环计与局中局、对赌与承诺设计、心理战与攻心；每个模式都可路由到可计算的博弈论模型（G1–G12）与可检索的案例库。适用于对抗性博弈、谈判、红队演练与规则审计。
version: 1.0.0
entrypoint: qixia.py
runtime: python3 >= 3.8（纯标准库，零第三方依赖，离线可用）
layers:
  methodology: methodology/00-methodology-overview.md
  models: skills/game-theory/SKILL.md
  cases: cases/gt/manifest.json
  evidence: knowledge/sources/shiri_baike.txt
---

# 齐夏 skills · agent 入口

> **这份文件只回答四个问题**：装什么、什么时候用、按什么顺序跑、跑完怎么验收。
> 方法论正文在 `methodology/`，博弈论模型正文在 `skills/game-theory/`——本文件不重复它们。

---

## 0. 30 秒上手（4 条命令）

```bash
cd qixia-skills

python3 qixia.py doctor                      # ① 体检：文件齐备 + 双引擎自检 + 命令冒烟（应全 PASS）
python3 qixia.py ask "只有口头规则，还有个裁判有最终解释权"   # ② 路由：该用哪个模式 + 哪个模型
python3 qixia.py pattern show P1             # ③ 读方法：触发条件/执行步骤/失败条件/反制
python3 qixia.py run audit --file cases/gt/situation_interview_room.json   # ④ 跑局面：自动识别模型并出结论
```

四条命令覆盖 90% 的调用。其余命令见 `python3 qixia.py --help`，完整清单见 `INDEX.json`。

**路径约定**：全部命令都在包根目录（`qixia.py` 所在目录）执行；不确定路径先跑 `python3 qixia.py where`。

---

## 1. 包的四层结构与读取顺序

| 层 | 位置 | 回答的问题 | 什么时候读 |
|---|---|---|---|
| **L0 入口层** | `SKILL.md` / `QUICKSTART.md` / `ROUTING.md` / `INDEX.json` / `qixia.py` / `prompts/` | 怎么加载、怎么路由、怎么调用、怎么验收 | 第一次加载时（一次性） |
| **L1 方法论层（P1–P5）** | `methodology/` | **用什么招**：规则侦察、规则欺骗、连环计、对赌承诺、心理战 | 需要"打法"时 |
| **L2 模型层（G1–G12）** | `skills/game-theory/` | **为什么成立、数值上值不值**：机制设计、贝叶斯、信号、PD、混合、逆向归纳、沉没成本、诈唬、概率、共同知识、甄别、元博弈 | 需要"算"或需要"硬约束"时 |
| **L3 案例与证据层** | `cases/gt/` / `reports/gt/` / `knowledge/sources/` | 这个局怎么实例化成参数、原书原文怎么写的 | 需要对照/溯源时 |

**读取顺序不可颠倒**：先 L0 拿到路由结论 → 再 L1 定模式 → 再 L2 算约束 → L3 只用于核对与举例。
反向（先读案例再套模式）是最常见的误用，会把启发式当成结论。

---

## 2. 六条默认工作流（照抄即可）

### W0 冷启动：进入一个完全陌生的场景

```bash
python3 qixia.py pattern eight                 # 谋略八问：规则全文/未定义词/裁判激励/判定函数/代价/无成本动作/半胜/结算者
python3 qixia.py ask "<用一句话描述场景>"
python3 qixia.py pattern show <P?>             # 读主模式全貌
python3 qixia.py pattern premortem <P?>        # 事前验尸：先排失败条件，再谈执行
```
> 八问里第 1、4、8 问答不上来，就不要进入任何下注/承诺动作。

### W1 规则审计：只判断规则，不下注

```bash
python3 qixia.py run audit --file <你的 situation.json> --json      # 只填 g4 段也能跑
python3 qixia.py pattern check P1                                    # 逐项打勾
```
读三个东西：`identified[]`（引擎认为这是哪类局）、`gaps[]`（规则未定义处 / 激励不相容处 / 参数缺失处）、`results[].verdict`。

### W2 定量决策：要一个数

```bash
python3 qixia.py run models                                    # 先看 solver 名与锚点（以引擎输出为准）
python3 qixia.py run <solver> --file cases/gt/<case>.json --json
```
参数要跑三遍：基准值、悲观值、乐观值。**三个值下结论一致才可用**；不一致说明胜负取决于那个参数，回去查它。

### W3 布局：需要多层计划

```bash
python3 qixia.py pattern show P3
python3 qixia.py run backward --file cases/gt/g6_tree_changjie.json    # 先验证"威胁是否可信"
python3 qixia.py run meta     --file cases/gt/g12_meta_dao.json        # 再验证"赢了谁结算"
python3 qixia.py pattern premortem P3                                  # 最后排失败条件
```

### W4 对赌 / 谈判：要把口头约定变成锁

```bash
python3 qixia.py pattern show P4
python3 qixia.py run screening --theta-h <高类型价值> --theta-l <低类型价值> --prior <先验>
python3 qixia.py run bluff --pot <池> --bet <注>
python3 qixia.py pattern counter P4                            # 对手会怎么反制我
```
> 记住原书规则：**参与者不能拒绝赌命**。所以 P4 的目标不是"拒绝"，而是"让赌局不成立/让对手没有赌命资格/抢占裁决结构"。

### W5 交付验收：打包前

```bash
python3 qixia.py doctor      # 必须全 PASS（agent 可调用性）
sh build_package.sh          # 正式交付：确定性打包 + PACKAGE.json + RELEASE + 解包全量自检
python3 qixia.py pack        # 轻量本地打包（只要一个 zip 时）
```

---

## 3. 路由：情境 → 方法（P）+ 模型（G）

一句话路由（推荐 agent 用，可解析 JSON）：

```bash
python3 qixia.py route "对手资源碾压我，正面必输，但他有个必须救的人" --json
```

返回结构（字段稳定）：

```jsonc
{
  "query": "...",
  "patterns": [{"id": "P3", "name": "...", "score": 6.0, "hits": ["T1:打不过"], "risk": "critical",
                "file": "methodology/03-nested-plans.md", "summary": "...", "gt_refs": ["g6_tree_changjie.json"],
                "commands": ["python3 qixia.py pattern show P3", "..."], "source": "pattern"}],
  "models":   [{"code": "G6", "name": "...", "solver": "backward", "score": 0,
                "hits": ["来自 P3 的 gt_refs"], "case": "g6_tree_changjie.json", "why": "...", "source": "pattern"}],
  "next":     ["python3 qixia.py pattern eight", "..."]
}
```

- `patterns` 由 `methodology/scripts/pattern_cli.py match` 计算（与手工调用完全同一套数据）；只在触发词漏召时，才由 `INDEX.json` 的口语别名层补位（`source: "alias"`，`hits` 以 `alias:` 前缀标记，**可区分、低保真**）。
- `models` 先按 `INDEX.json` 的关键词打分（`source: "keyword"`），再追加主模式 `gt_refs` 反查到的模型（`source: "pattern"`）——后者是"该模式背后必查的模型"，即使得分为 0 也要跑。
- **`next` 是可直接执行的下一步命令**，agent 不需要自己拼命令。

完整人工路由表（12 类任务 × 首选模式 × 必跑模型 × 参考案例）：见 **`ROUTING.md`**。

---

## 4. 输出契约：agent 该从结果里抄什么

除 `models` / `flow` / `checklist` / `selftest` 外，所有求解器与 `audit` 都遵循固定字段：

| 字段 | 含义 | agent 怎么用 |
|---|---|---|
| `model` / `solver` / `title` | 模型与局面标识 | 写进报告的"依据"栏 |
| `verdict` | 一句话结论 | 直接作为决策句 |
| `evidence[]` | 推导链（含数字） | 审计留痕，别丢 |
| `numbers{}` | 结构化数值（后验、EV、δ*、MDF、均衡值…） | 二次计算/监控用 |
| `action` | 单步最优动作 | 排进时间线（不可逆性低的先做） |
| `counter` | 对手的反制 | 反过来读，就是我的应手 |
| `fail_if[]` | 失败条件 | **没有 fail_if 的策略一律不许执行** |
| `gaps[]` | 规则未定义 / 激励不相容 / 参数缺失 | 破局点清单 + 待办清单 |

`audit` 额外返回 `identified[]`（命中的模型、命中的关键词、是否已提供参数）与汇总 `gaps[]`。

**执行顺序约定**：`action` 是"单步最优"，落地时按 **不可逆性从低到高** 排序——先试探/取证，再改规则/立约，最后下注/赌命/公开承诺。

---

## 5. Prompt 模板（可直接粘贴）

`prompts/` 下 7 个模板，全部可直接复制到对话里用，`{{变量}}` 处替换即可：

| ID | 文件 | 用途 |
|---|---|---|
| T0 | `prompts/00-system-agent.md` | 把本 skill 挂进 agent 的 system prompt |
| T1 | `prompts/01-rule-audit.md` | 只审计规则：找隐藏规则与漏洞 |
| T2 | `prompts/02-full-audit.md` | 复杂局面一次跑通 P+G 全链条 |
| T3 | `prompts/03-nested-plan.md` | 正面打不过，需要布局/连环计 |
| T4 | `prompts/04-negotiation-bet.md` | 谈判/结盟/对赌/承诺设计 |
| T5 | `prompts/05-debrief.md` | 一局结束后的复盘与参数更新 |
| T6 | `prompts/06-quick-oneshot.md` | 只想要一句话结论（最省 token） |

最小可用范例（T6 的实质内容）：

```text
在 qixia-skills 包里工作。先跑 `python3 qixia.py ask "<情境>"` 拿路由，
按返回的 next 命令执行，最后只输出：结论 / 依据(gaps 与关键数字) / 下一步一个动作 / 该动作的失败条件。
不要复述方法论，不要输出原文剧情。
```

---

## 6. 与 `scripts/` 的整合契约

入口层**不复制任何逻辑**，只做发现、路由、透传、体检、打包：

```
qixia.py  pattern …  →  methodology/scripts/pattern_cli.py     （模式检索：list/show/match/check/premortem/counter/eight/route）
qixia.py  run …      →  scripts/gt/qixia_gt.py                 （博弈论求解：models/flow/checklist/pd/bayes/…/audit/gate/selftest）
qixia.py  doctor     →  methodology/scripts/validate.py + qixia_gt.py selftest + 文档命令冒烟
qixia.py  pack       →  zipfile（排除 __pycache__/*.pyc/*.zip）+ sha256（轻量本地打包）
交付层（直接调用，不复制）：scripts/check_package.py（全包自洽）、build_package.sh（确定性打包 + 解包自检）
```

调用契约（agent 可依赖）：

1. **透传不改语义**：`qixia.py run X args…` 与 `python3 scripts/gt/qixia_gt.py X args…` 等价，退出码原样透传。
2. **`--json` 透传**：下层支持的 `--json`、`--out`、`--file` 全部原样有效；`--out` 的相对路径仍相对包根目录。
3. **零依赖**：只 import 标准库；不需要 `pip install`，不需要联网。
4. **只读**：`qixia.py` 不修改下层任何文件；`pack` 只读打包。
5. **单一事实来源**：模式数据只来自 `methodology/patterns.index.json`，模型清单只来自 `qixia_gt.py models`——文档与本脚本都不另存一份模型定义，避免漂移。
6. **失败要响**：`doctor` 任一检查失败退出码为 1；`status` 有文件缺失退出码为 1。CI/agent 应据此阻断。

下层脚本的详细用法（不属于本层，仅索引）：`skills/game-theory/AGENT_PLAYBOOK.md`（7 步作业流程）、`skills/game-theory/SCHEMAS.md`（每个求解器的 JSON 入参/出参）。

---

## 7. 校验与交付

```bash
python3 qixia.py doctor           # 期望：全部通过 ✅
python3 qixia.py status           # 期望：missing=0
sh build_package.sh               # 正式交付：dist/ 下 tar.gz + zip + sha256 + RELEASE + 解包自检
python3 qixia.py pack             # 轻量本地打包（只要一个 zip 时用；不含 PACKAGE.json/RELEASE）
```

> **两层校验的分工**（别混用结论）：
> - 本层 `python3 qixia.py doctor` 回答"**agent 能不能加载与调用**"（文件齐备 + 双引擎自检 + 文档命令冒烟 + 文档引用路径存在）。
> - 交付层 `python3 scripts/check_package.py` 回答"**包是否自洽**"（索引/交叉链接/计数/可复现性），`sh build_package.sh` 负责确定性打包与解包自检。
> - `doctor` 通过 ≠ 全包自洽；两者都要过才能交付。

`pack` 会打印三条验收命令；标准验收流程：

```bash
unzip -l qixia-skills-1.0.0.zip | tail -1
sha256sum qixia-skills-1.0.0.zip
unzip -q qixia-skills-1.0.0.zip -d /tmp/qv && python3 /tmp/qv/qixia-skills/qixia.py doctor
```

验收清单（打包前逐项确认）：

- [ ] `qixia.py doctor` 全 PASS（含 `validate.py` 的"0 错误 0 警告"与 `qixia_gt selftest` 的"0 failed"）
- [ ] `qixia.py status` 的 `missing=0`
- [ ] `qixia.py ask "<任一情境>"` 能返回非空 `patterns`，且 `next` 命令可直接执行
- [ ] `qixia.py run audit --file cases/gt/situation_interview_room.json --json` 可解析且含 `identified`
- [ ] `unzip` 到干净目录后 `qixia.py doctor` 仍全 PASS（证明无绝对路径/外部依赖）
- [ ] 压缩包内无 `__pycache__` / `*.pyc`
- [ ] 交付层 `python3 scripts/check_package.py` 同样全 PASS（无悬空引用、计数一致）

---

## 8. 使用纪律（三条铁律 + 合规边界）

1. **先算"不做"的收益**：先问"有没有什么都不动就能赢的解"（跷跷板不动即胜、彩券滚池、极乐钱庄只赢一颗不收费）。
2. **任何计划必须有第二计**：主计 / 备用计 / 脱身计，只有一计叫"赌"。
3. **欺骗只在对抗性博弈中使用**：本包面向对抗性博弈、谈判、红队演练与规则审计；**不得**用于对真实个人实施欺诈、胁迫或诱导自伤，也不得伪造证据陷害。

冲突裁决规则：**模式（P）是启发式，模型（G）是硬约束；两者冲突时以 G 的判定为准。**

---

## 9. 已知限制（诚实声明）

- 数值参数多为**建模假设**：原文只给规则文本，不给收益数字。结论的"结构"可信，"绝对数值"不可当原文事实（每个 case 的 `note` 都有此声明）。
- `screening`（G11）目前**没有独立案例文件**，只能走 CLI 参数或自写 JSON。
- 各求解器的适用范围（树大小、类型数、矩阵维度、信号数）见 `skills/game-theory/SKILL.md` §9；超界时先降维或用闭式解。
- 证据基线是百度百科词条全文（`knowledge/sources/shiri_baike.txt`，md5 `f3e1fe1af1ecbf0965167fa718f2a3b8`）：章节名可作线索，**不能**当作剧情事实。
- 本层只保证"可加载、可调用、可验收"；不保证对具体现实决策的正确性——参数与判断仍由使用者负责。

---

## 10. 文件地图

```
qixia-skills/
├── SKILL.md                 ← 本文件：agent 入口契约
├── QUICKSTART.md            ← 5 分钟上手 + 三种挂载方式 + 四个实战走查
├── ROUTING.md               ← 场景 → 方法/模型 完整路由表（12 类任务 + 触发词表 + 组合链）
├── INDEX.json               ← 机器可读清单：入口、命令、路由关键词、模板、验收项
├── qixia.py                 ← 统一前台 CLI（status/where/ask/route/pattern/run/doctor/pack）
├── README.md                ← 人读总览
├── prompts/                 ← T0–T6 可粘贴 prompt 模板
├── methodology/             ← L1 方法论层（P1–P5 + 索引 + 案例库 + 2 个零依赖脚本）
├── skills/game-theory/      ← L2 模型层（G1–G12 文档、playbook、schema、checklist）
├── scripts/gt/              ← 引擎（qixia_gt.py 单文件、run_cases.sh、build_docs.py）
├── cases/gt/                ← 案例参数（20 个 JSON + manifest）
├── reports/gt/              ← 案例运行报告（生成物）
└── knowledge/sources/       ← 原文证据基线
```
