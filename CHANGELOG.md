# 变更记录（qixia-skills）

本文件记录**每一层产出**的来源、解决了什么缺口、以及交付层为「自洽」做的修正。
版本号唯一来源是 `VERSION`；`INDEX.json`、`PACKAGE.json`、`methodology/patterns.index.json` 必须与之一致
（`python3 scripts/check_package.py` 会断言，不一致即 FAIL）。

---

## 1.0.0 — 首个完整交付（2026-11-11）

### L1 方法论层（P1–P5）

- `methodology/00-methodology-overview.md`：三差模型（信息差 / 规则差 / 承诺差）、五层拆解（L1 认知→L2 规则→L3 承诺→L4 心理→L5 元层）、谋略八问、情境→模式路由表、三条铁律。
- `methodology/01…05-*.md`：5 个模式，每个含触发条件 / 执行步骤（带产物与判据）/ 失败条件 / 反制手段 / 案例锚点 / checklist；共 **235 个结构化元素**（`patterns.index.json`）。
- `methodology/casebook.yaml`：**23 条深度案例**（规则要点 + 原文行号 + 模式映射）+ **37 条章节级线索**（`evidence: chapter_title`，严格区分「标题线索」与「剧情事实」）。
- `methodology/examples/ex01-jile-qianzhuang-walkthrough.md`：P1→P3→P4→P5 串成一条决策链，含定量推导（彩券样本空间 3¹²=531441、命中率≈1.88e-6、需奖池 > 53 万道才转正 EV → 彩券是负 EV 的沉没成本陷阱）。
- 工具：`methodology/scripts/pattern_cli.py`（list/show/match/check/premortem/counter/eight/route）、`validate.py`（五要素 + 交叉链接 + 案例锚点校验）。

### L2 模型层（G1–G12）

- `scripts/gt/qixia_gt.py`：单文件、纯标准库；12 个模型注册表 + 14 个求解器子命令（pd/bayes/mixed/signaling/screening/mechanism/backward/sunk/bluff/prob/common/meta/metaq/poker）+ audit / gate / selftest；统一 9 字段输出，`gaps[]` 专门输出「规则未定义处」即破局点候选；数值用 `fractions.Fraction` 精确计算。
- `skills/game-theory/`：`SKILL.md`（总入口 + S0–S6 决策流水线）、`AGENT_PLAYBOOK.md`、`SCHEMAS.md`、`CASES.md`、`checklists.md`、`models/G1–G12.md`（由 `scripts/gt/build_docs.py` 从代码注册表生成，重跑逐字节不变）。
- **39 项硬断言自检**（δ*=(T−R)/(T−P)=0.5、猜拳混合均衡 1/3、次价拍卖 DSIC、Mussa-Rosen 信息租金、黑白棋 74/99、两军问题 0.99 不可达、朔望月的点数上限 16 等），`selftest` 全部通过。
- **20 个参数化案例**（16 单模型 + 2 综合审计 + 2 下注闸门）→ `reports/gt/*.md` 20 份报告，`sh scripts/gt/run_cases.sh` 可复跑。

### L0 入口层（agent 契约）

- `SKILL.md` / `QUICKSTART.md` / `ROUTING.md` / `INDEX.json` / `prompts/`：加载方式、场景→模式/模型路由、可直接粘贴的 prompt 模板。
- `qixia.py`：统一前台 CLI（status / where / ask / route / pattern / run / doctor / pack），不复制下层逻辑，只做发现、路由、透传、体检、打包。

### L3 证据与案例扩展

- `knowledge/sources/shiri_baike.txt`：百度百科词条纯文本快照（md5 `f3e1fe1af1ecbf09…` 全值见 `README.md` §4），casebook 行号指向该快照。
- `knowledge/cases/`：**69 条记录**的结构化棋局库——`zodiac_mechanisms.yaml`（12 生肖家族 × 37 局 + 2 特殊局 + 9 仅存名目的废弃/佚名局）、`qixia_battles.yaml`（21 个齐夏战例）、`dedupe_map.yaml`（22 条与 casebook 的去重/增量登记 + 37 条章节线索状态）、`cases.index.json`（机器可读索引，含源指纹）、`coverage.md`（自动生成的覆盖矩阵）、`evidence_policy.md`（E1–E4 四类证据规范）。
- 工具：`scripts/cases/audit_cases.py`（行号回溯 + E1 原文重合度反幻觉 + 去重完整性，实测错误 0）、`build_case_index.py`（索引与覆盖矩阵再生成，逐字节可复现）、`case_cli.py`（检索/筛选）。

### 交付层（本版本新增）

- `README.md`（包级门面）、`VERSION`（唯一版本源）、`CHANGELOG.md`（本文件）、`PACKAGE.json`（机器可读清单：能力 + 逐文件 sha256 + 验收结果）。
- `LICENSE`：MIT 开源许可，开发者 guaidao2；`README.md` 新增开发者署名、包结构与「§8 开发者与开源许可」章节。
- `scripts/check_package.py`：全包集成验收——结构完整性、模式索引↔正文↔gt_refs 一致性、casebook 行号与模式引用真实性、案例↔manifest↔报告三向对齐、Markdown 交叉链接与锚点、文档计数与实际产物的偏差、版本一致性、可复现性（validate / selftest / 20 案例 / 模型文档再生成）、清单 sha256 校验。
- `build_package.sh`：预检 → 写清单 → 确定性打包（固定 mtime / 归零属主 / 名字排序，同内容同 sha256）→ 解包自检 → 产出 `dist/` 下的压缩包、sha256、`RELEASE-*.md` 与完整日志。

### 交付层修正（为消除「看着有、其实不通」）

1. **`qixia_gt.py gate` 忽略 `--out`**：`gate` 分支自打印、不落盘，导致 `run_cases.sh` 报 OK 但 `reports/gt/gate_*.md` 根本不存在。改为与其它 solver 一致地走 `_emit()`，两个闸门案例的报告现已真实生成。
2. **`run_cases.sh` 无落盘断言**：只要退出码为 0 就打印 OK。现改为「每个 case 必须产出非空报告」，否则写 `<case>.err` 并以非 0 退出；同时清理历史失败残留的 `.err`。
3. **文档计数漂移**：`skills/game-theory/SKILL.md` 与 `CASES.md` 仍写着旧计数（18→20 个案例、37→39 项自检，后者以实测为准）；已按实测改正，并补上 `CASES.md` 的 gate 案例小节（B2）。
4. **清理构建垃圾**：删除 `__pycache__` 与历史空 `.err`，压缩包内不再携带字节码。

### 交付层修正（第二轮：让「可复现打包」真正成立）

5. **`build_package.sh` 在 `sh`（dash）下会中断**：脚本用了 bash 专有的 `pushd/popd` 与 `${BASH_SOURCE[0]}`，而文档写的入口是 `sh build_package.sh`；在 `/bin/sh -> dash` 的机器上，解包自检段在 `pushd` 处终止（且退出码被外层管道掩盖，看起来像成功，`RELEASE-*.md` 根本没生成）。已改为 `SELF=$0` / `ORIG_PWD=$(pwd)` + `cd` / `printf '%b'`，dash 与 bash 均可跑完整个流程。
6. **`PACKAGE.json` 受目录读取顺序影响**：`check_package.py` 的 Markdown / 链接扫描未排序，导致同一内容在不同目录（例如解包副本）下生成的清单里 WARN 明细顺序不同 ⇒ 包 sha256 不可复现。已对 md 文件列表与 token 集合排序。
7. **zip 依赖 `zip -r` 的目录遍历顺序**：tar 有 `--sort=name`，zip 没有，因此「从解包副本重新打包」会得到不同字节序与不同 sha256。已改为「排序后的条目清单 + `zip -@`」，并显式排除 `__pycache__` / `*.pyc`。

修复后：同一包在**同目录复跑、换输出目录、从 tar.gz 解包后重建、从 zip 解包后重建（sh 与 bash 皆可）**四种情形下，tar.gz 与 zip 的 sha256 完全一致，即交付物可自举重建；证据见 `dist/determinism-*.log` 与 `dist/RELEASE-*.md`。

### 已知限制

- 建模数值多为假设（原文只给规则文本）；`signaling` 只枚举纯策略 PBE；`mechanism` 限两人单物品两值报告；`mixed` 支撑枚举上限 4×4。
- 百度的词条快照是二手整理材料，不是小说原文；原文级证据需另取，本包不夸大。
- 合规：仅用于对抗性博弈、谈判、红队演练与规则审计；不用于对真实个人实施欺诈、胁迫或诱导自伤。
