# 棋局案例库（knowledge/cases）

把「全」补成**可检索的结构化棋局库**：十二生肖 37 局 + 2 个特殊局 + 9 条「仅存名目」+ 齐夏本人 21 条战例
（共 69 条记录），
每条都给出「规则原文要点（可回溯行号）→ 隐藏规则 → 未定义处 → 破局点 → 反制 → 教训 → 模式编号」，
并与 `methodology/casebook.yaml` 的 23 条深度案例（C01–C23）、37 条章节线索（X 系列）**去重并划清证据边界**。

## 一分钟上手

```bash
cd qixia-skills

# 1) 生成索引 + 去重台账 + 覆盖矩阵（改了 YAML 就重跑）
python3 scripts/cases/build_case_index.py

# 2) 硬校验（结构 / 行号 / 反幻觉 / 去重 / 覆盖 / 线索隔离）
python3 scripts/cases/audit_cases.py

# 3) 检索
python3 scripts/cases/case_cli.py stats                 # 库统计
python3 scripts/cases/case_cli.py zodiac                # 十二生肖总表
python3 scripts/cases/case_cli.py family 羊              # 某族：家族攻击面 + 全部各局
python3 scripts/cases/case_cli.py show Q05               # 单条全貌（合同工程战例）
python3 scripts/cases/case_cli.py search 沉没成本 彩券    # 关键词
python3 scripts/cases/case_cli.py route 隐藏规则 判定 人数 # 情境 → 候选局（打分）
python3 scripts/cases/case_cli.py gaps                   # 所有未定义/可争议处（红队探针清单）
python3 scripts/cases/case_cli.py hidden                 # 所有 E1 级隐藏规则
python3 scripts/cases/case_cli.py list --dedupe extends  # 与 casebook 有增量的条目
python3 scripts/cases/case_cli.py --json list --family 龙  # 机器可读
```

零第三方依赖的只有 `case_cli.py`（读 `cases.index.json`）；生成器与审计器需要 PyYAML。

## 文件

| 文件 | 作用 |
|---|---|
| `evidence_policy.md` | **证据分级规范**：E1 规则原文 / E2 剧情陈述 / E3 我方推断 / E4 标题线索，以及硬性标注规则 |
| `zodiac_mechanisms.yaml` | 十二生肖 12 族、37 局 + 特殊局 2 条（刑官「拔河」、神兽「第三类」），含家族级攻击面 |
| `qixia_battles.yaml` | 齐夏 21 条战例（Q01–Q21） |
| `cases.index.json` | 机器索引（69 条扁平记录 + 12 族元数据 + 分类学），CLI 的唯一输入 |
| `dedupe_map.yaml` | **去重台账**（自动生成）：extends / upgrades_clue 逐条写明增量；omitted 说明哪些 C 案例不再重复；chapter_clue_status 给 37 条标题线索定性 |
| `coverage.md` | 覆盖矩阵（自动生成）：生肖 × 机制 × 局、战例表、证据分级统计、E1 隐藏规则清单、模式覆盖 |

## 覆盖情况

- 十二生肖 **12/12**，局 **37** 条：鼠4 牛2 虎1 兔2 龙7 蛇4 马2 羊5 猴4 鸡2 狗3 猪1。
- 特殊局 **2** 条：玉城刑官「拔河」（原文无规则条文）、神兽「第三类」（不算正规游戏）。
- **仅存名目 9 条**：天鼠/天牛/天虎/天狗/天猪/天鸡/天猴/天兔「时刻」与人羊「人羊立威」——
  词条只给了名字，本库就只记名字并标注「证据到此为止」，不编造规则。
- 齐夏战例 **21** 条：Q01 频率誓言、Q02 天秤之败、Q03 生肖渗透、Q04 永久回响者、
  Q05 面试房间合同、Q06 问题本验证器、Q07 四轮回、Q08 仓颉棋、Q09 朔望月、Q10 双龙三方对赌、
  Q11 造人计划、Q12 假命令与对位击杀、Q13 门即拓扑、Q14 眼球容器、Q15 爆炸项圈、
  Q16 蝼蚁杠杆、Q17 洗牌谎言、Q18 新世界反杀、Q19 恻隐成本、Q20 执念审计、Q21 七年封存。

## 证据边界（最重要的一条）

- 本库正文**只放 E1/E2**（规则原文要点、词条直接陈述的剧情）；所有 `breakpoint / gaps / counter / lesson`
  都是 **E3 推断**，读作「若…则…」的可执行推演，**不能**读作「齐夏当时这样做了」。
- **章节标题（E4）一律不进入正文**。`dedupe_map.yaml` 的 `chapter_clue_status` 给每条 X 线索定性：
  目前只有 X337「道的骗局」被 Q17 用 E1/E2 事实**升级**，其余 36 条保持 `clue_only`。
- 反过来，凡正文里出现「齐夏在某局的具体打法」，都必须能在 `what_happened`（E2）里找到出处；
  找不到的（例如朔望月 Q09）会显式写明「原文未记载，以下为推演」。

## 记录结构

生肖局（`zodiac_game` / `zodiac_special`）：

```yaml
id / name / tier / host / players / ticket / status / lines
rules          # E1 要点（可空，但空时必须有 note 说明原文缺项）
hidden_rules   # E1，仅收录原文明确写「隐藏规则」的条目
gaps           # E3 未定义/可争议处（红队探针）
breakpoint     # E3 破局点（可执行动作）
counter        # E3 反制（作为对手 / 作为主办两个方向）
lesson         # E3 一句教训
patterns       # 只允许 P1–P5 前缀（子项沿用 casebook 约定，如 P1.S5 / P2.D4 / P4.S1）
dedupe         # distinct | extends | duplicate_of | upgrades_clue（非 distinct 必填 what_is_new）
evidence       # E1 或 E2（本条主证据级别）
clue_refs      # 可选：E4 标题线索，仅用于定位，不计入证据
```

齐夏战例（`qixia_case`）额外含 `what_happened`（E2 事件清单）与 `failure_lesson`（E3，多条）。

## 与其他层的关系

- 上游方法论：`methodology/patterns.index.json`（P1–P5 五模式），本库的 `patterns` 指向它。
- 并行深度案例：`methodology/casebook.yaml`（C01–C23）。本库**不重复**其内容，只登记增量——
  22 条去重记录全部说明「新增了什么」（例如 Q05 新增「3.6 条款 × 第四轮回第十人 × 张强自杀」的因果链）。
- 博弈论层：`cases/gt/*.json` 与 `reports/gt/*.md`。本库提供**局面与判定条件**，gt 层提供**可算模型**；
  两者通过 `uid`（ZG-xx / Qxx）与 `cases/gt` 的 `situation_*.json` 对齐。
- 证据基线：`knowledge/sources/shiri_baike.txt`（3533 行）。所有 `lines` 都指向它，`audit_cases.py`
  会用字符二元组重合度做反幻觉检查（阈值 0.50 提示、0.30 判错），确保没有凭空编造的规则或剧情。
