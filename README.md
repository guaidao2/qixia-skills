# 齐夏 skills · 一个能「布局、破局、算账」的 agent 技能包

**版本 1.0.0** ｜ 纯 Python 标准库 ｜ 零第三方依赖 ｜ 完全离线 ｜ 全部结论可复跑

**开发者** guaidao2 ｜ **开源许可** MIT（全文见 [`LICENSE`](LICENSE)）

> 取自《十日终焉》主角齐夏的谋略路径：**先弄清这张桌子上有几套规则，再设计一个「对方赢了也没用、输了就致命」的局**。
> 本包把这条路径拆成两层工程物：**可路由的方法论模式（P1–P5）** 与 **可计算的博弈论模型（G1–G12）**，
> 并用一份固化的原文快照 + 20 个可复跑案例把每个结论钉回证据。

---

## 0. 三分钟验收（推荐先跑这个）

```bash
cd qixia-skills
python3 scripts/check_package.py --repro     # 全包验收：结构/索引/交叉链接/计数/可复现性（应全 PASS）
python3 qixia.py doctor                      # agent 入口体检：文件 + 双引擎自检 + 命令冒烟
sh build_package.sh                          # 重新打包：dist/qixia-skills-1.0.0.tar.gz + .zip + sha256 + 解包自检
```

三条命令分别回答：**包是否自洽**、**agent 能否开箱调用**、**交付物能否一键重建并验证**。

---

## 1. 包结构（一棵自洽的树，只有一个方向）

```
qixia-skills/
├── README.md                ← 本文件：包级门面（定位 / 结构 / 能力清单 / 验收 / 打包 / 许可）
├── LICENSE                  ← MIT 开源许可（开发者：guaidao2）
├── VERSION                  ← 单一版本号来源（INDEX.json / PACKAGE.json 必须与之一致）
├── CHANGELOG.md             ← 每层产出的来源与变更记录
├── PACKAGE.json             ← 机器可读清单：版本 + 能力清单 + 逐文件 sha256 + 验收结果（打包时生成）
├── build_package.sh         ← 打包与解包自检（唯一打包入口，可重复运行）
├── SKILL.md / QUICKSTART.md / ROUTING.md / INDEX.json / qixia.py / prompts/
│                            ← L0 入口层：agent 契约、场景路由、prompt 模板、统一 CLI
├── methodology/             ← L1 方法论层：P1–P5 模式正文 + patterns.index.json + casebook.yaml
├── skills/game-theory/      ← L2 模型层：G1–G12 形式化文档 + 操作手册 + JSON schema + 判定清单
├── scripts/gt/              ← L2 引擎：qixia_gt.py（14 个求解器）+ build_docs.py + run_cases.sh
├── cases/gt/                ← L3 案例层：20 个参数化局面 + manifest.json
├── reports/gt/              ← L3 报告层：20 份可复跑报告（生成物）
└── knowledge/sources/       ← L3 证据层：百度百科词条纯文本快照（md5 f3e1fe1a…，66490 字符 / 3532 行）
```

**唯一的读向**：L0 拿路由 → L1 定打法 → L2 算约束与数字 → L3 核对原文。
反向（先读案例、再倒套模式）会把启发式当成结论，是本包明确反对的用法。

---

## 2. 能力清单（全部为包内已存在、已被断言验证的产物）

| 能力 | 产物 | 数量 | 验证方式 |
|---|---|---|---|
| 谋略模式 | `methodology/01…05-*.md` + `patterns.index.json` | **5 个模式**（P1 规则侦察 / P2 规则欺骗与反欺骗 / P3 连环计与局中局 / P4 对赌与承诺 / P5 心理战与攻心） | `python3 methodology/scripts/validate.py` → 错误=0 |
| 模式结构化元素 | `patterns.index.json` | 235 个（触发/步骤/失败/反制/案例/checklist） | `check_package.py` 校验五要素与子元素引用 |
| 博弈论模型 | `skills/game-theory/models/G1–G12.md` + `scripts/gt/qixia_gt.py` | **12 个模型 / 14 个求解器** | `python3 scripts/gt/qixia_gt.py selftest` → **39 passed, 0 failed** |
| 参数化局面 | `cases/gt/*.json` + `manifest.json` | **20 个**（16 单模型 + 2 综合审计 + 2 下注闸门） | `sh scripts/gt/run_cases.sh` → 20 cases, 0 failed |
| 可复跑报告 | `reports/gt/*.md` | **20 份**，重跑逐字节不变 | `check_package.py --repro` 比对哈希 |
| 深度案例库 | `methodology/casebook.yaml` | **23 条深度案例**（规则要点 + 行号 + 模式映射）+ **37 条章节级线索**（标 `evidence: chapter_title`） | `check_package.py` 校验行号落在证据快照内、模式引用真实存在 |
| 结构化检索库 | `knowledge/cases/`（`zodiac_mechanisms.yaml` / `qixia_battles.yaml` / `dedupe_map.yaml` / `coverage.md` / `cases.index.json`） | **69 条记录**：37 生肖局 + 2 特殊局 + 21 战例 + 9 仅存名目，覆盖 12/12 生肖家族 | `python3 scripts/cases/audit_cases.py` → 错误 0；`check_package.py` 校验索引↔YAML↔行号↔证据标签 |
| 成品决策链范例 | `methodology/examples/ex01-jile-qianzhuang-walkthrough.md` | 1 篇（P1→P3→P4→P5 串成一条链，含彩券样本空间 3¹² 与 EV 推导） | 人工可读，引用均指向包内文件 |
| agent 统一入口 | `qixia.py`（status / where / ask / route / pattern / run / doctor / pack） | 8 个子命令 | `python3 qixia.py doctor` 全 PASS |
| 结构化检索 CLI | `scripts/cases/case_cli.py`（检索/筛选/去重查询） | 1 个零依赖 CLI | `python3 scripts/cases/case_cli.py --help` |
| 打包与验收 | `build_package.sh` + `scripts/check_package.py` | 2 个脚本，均可 `--json` | 打包后解包自检（见 §5） |

> 完整机器可读清单见 `PACKAGE.json`（`capabilities` + `files[]` 逐文件 sha256 + `checks[]` 逐项结果）。

---

## 3. 该怎么用：一条最短路径

```bash
python3 qixia.py ask "只有口头规则，还有个裁判有最终解释权"     # 1. 一句话路由：给模式 + 给模型
python3 qixia.py pattern show P1                               # 2. 读打法：触发 / 步骤 / 失败条件 / 反制
python3 qixia.py run audit --file cases/gt/situation_interview_room.json   # 3. 跑局面：结构化结论 + gaps[]
python3 qixia.py pattern premortem P3                          # 4. 事前验尸：先排失败条件，再谈执行
```

四条命令覆盖 90% 的调用；细节见 `SKILL.md`（契约）、`QUICKSTART.md`（教程）、`ROUTING.md`（场景→模式/模型路由表）、`prompts/`（可直接粘贴的 prompt 模板）。

**三条铁律**（任何行动前必读）：先算「不做」的收益；任何计划必须有第二计；只用于对抗性博弈、谈判、红队演练与规则审计。

---

## 4. 证据链与诚实边界

- **证据快照**：`knowledge/sources/shiri_baike.txt`，md5 `f3e1fe1af1ecbf0965167fa718f2a3b8`，66490 字符 / 3532 行；casebook 的行号即指向该快照，解包后无需任何外部文件即可核对。
- **可区分的事实层级**：规则原文（可从快照逐字核对）＞ 剧情事实（章节点）＞ 抽象模式（我方提炼）＞ 建模数值（我方假设）。文档里每类都标注了所属层级，章节级线索统一标 `evidence: chapter_title`。
- **案例库的四类证据标签**（`knowledge/cases/evidence_policy.md`）：`E1` 规则原文 / `E2` 剧情陈述 / `E3` 我方推断（只能当可执行假设）/ `E4` 章节标题线索（不得当事实）。任何把 E4 升格为 E2 的条目必须显式登记 `upgraded_by`，这一条由 `scripts/cases/audit_cases.py` 机器强制。
- **已知限制（不掩饰）**：收益矩阵与概率多为建模假设，原文只给规则文本、不给数字；`signaling` 只枚举纯策略 PBE；`mechanism` 限两人单物品两值报告；`mixed` 支撑枚举上限 4×4。结论的「结构」可信，「绝对数值」不可当成原文事实。
- **合规边界**：本包用于**对抗性博弈、谈判、红队演练与规则审计**。禁止用于对真实个人实施欺诈、胁迫或诱导自伤——P2/P5 的「欺骗」「攻心」章节均带反制与防火墙视角，用途是识别与防御。

---

## 5. 打包与复现（交付物的硬证据）

`build_package.sh` 是唯一打包入口，它做四件事：

1. **预检**：`scripts/check_package.py --repro` 全绿才继续（结构、索引、交叉链接、计数、可复现性）。
2. **写清单**：生成/刷新 `PACKAGE.json`（版本、能力清单、逐文件 sha256、验收结果）。
3. **打包**：以固定 mtime / 归零属主 / 名字排序生成 `qixia-skills-1.0.0.tar.gz` 与 `.zip`，因此**同一份内容重复打包得到同一 sha256**。
4. **解包自检**：把 tar 包解到临时目录，在其中重跑 `check_package.py --verify-manifest`（逐文件 sha256 核对）、双引擎自检与 20 案例复跑，结果写入 `dist/RELEASE-1.0.0.md` 与 `dist/verify-1.0.0.log`；哈希写入 `dist/qixia-skills-1.0.0.sha256`。

```bash
sh build_package.sh                      # 默认输出到 ../dist/
OUT=/tmp/rel sh build_package.sh         # 指定输出目录
sh build_package.sh --skip-repro         # 跳过耗时的可复现性比对（不建议用于正式交付）
```

产物（`dist/`，位于包外，避免自包含）：

| 文件 | 内容 |
|---|---|
| `qixia-skills-1.0.0.tar.gz` | 完整包（不含 `__pycache__` / `*.pyc`） |
| `qixia-skills-1.0.0.zip` | 同一内容的 zip（`-X`，无额外属性） |
| `qixia-skills-1.0.0.sha256` | 两个压缩包的 sha256（`sha256sum -c` 可直接校验） |
| `RELEASE-1.0.0.md` | 版本、大小、哈希、文件数、解包自检逐项结果 |
| `verify-1.0.0.log` | 解包后的完整命令输出（审计用） |

解包者只需三条命令即可复核：

```bash
sha256sum -c qixia-skills-1.0.0.sha256
tar xzf qixia-skills-1.0.0.tar.gz && cd qixia-skills
python3 scripts/check_package.py --repro --verify-manifest PACKAGE.json
```

---

## 6. 版本与变更

`VERSION` 是唯一版本来源；`INDEX.json`、`PACKAGE.json`、`patterns.index.json` 必须与之一致（`check_package.py` 会断言）。
层与层之间的产出顺序、各自解决了什么缺口，见 `CHANGELOG.md`。

| 版本 | 要点 |
|---|---|
| 1.0.0 | 首个完整交付：P1–P5 方法论 + G1–G12 模型 + 20 案例/20 报告 + 23 条深度案例 + 37 条章节线索 + 全包验收与可复现打包 |

---

## 7. 目录速查（谁负责回答什么）

| 你的问题 | 打开 |
|---|---|
| 我该用什么招？ | `methodology/00-methodology-overview.md` → `01…05` 正文 |
| 这招在这个局面成不成立、值不值？ | `skills/game-theory/SKILL.md` → `SCHEMAS.md` 取参数字段 |
| 有没有现成的局面可对照？ | `cases/gt/manifest.json`；结论看 `reports/gt/*.md` |
| 这个结论原文怎么写的？ | `methodology/casebook.yaml`（行号）→ `knowledge/sources/shiri_baike.txt` |
| 我要接进自己的 agent / 写 prompt | `SKILL.md`、`ROUTING.md`、`prompts/` |
| 这个包还完整吗？ | `python3 scripts/check_package.py --repro --verify-manifest` |

---

## 8. 开发者与开源许可

- **开发者**：guaidao2
- **开源许可**：**MIT License**，许可见 [`LICENSE`](LICENSE)。

MIT 允许自由使用、复制、修改、合并、发布、分发、再许可与销售本包及其文档副本，唯一义务是保留版权声明与许可声明；本包按「现状」提供，不附带任何明示或默示担保。
