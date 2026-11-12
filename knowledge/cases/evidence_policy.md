# 证据分级规范（evidence_policy）

本案例库只允许四类证据标签。**任何一条记录都必须带 `evidence` 字段**，任何一条「破局点」
都必须标为 E3。目的：让 agent 在使用时能区分「书上写着的」「词条陈述的」「我们推出来的」
与「只是一个章节名」。

## 四类证据

| 标签 | 名称 | 定义 | 可当事实用？ | 允许出现在哪些字段 |
|---|---|---|---|---|
| `E1` | `rule_text` 规则原文 | 词条中逐字给出的规则、合同、守则、赌命条款、胜负判定。可被 `line` 精确回溯。 | 可以 | `rules` / `hidden_rules` / `ticket` / `players` |
| `E2` | `plot_fact` 剧情陈述 | 词条「人物经历 / 时间线 / 角色介绍 / 名词解释」中直接写出的客观事件（谁做了什么、谁死了、结果如何）。 | 可以（但只到词条陈述的程度） | 战例的 `what_happened` |
| `E3` | `inference` 我方推断 | 由 E1/E2 推出的破局点、隐藏攻击面、因果链、教训、定量估计。**未在任何原文出现**。 | 不可以当事实，只能当「可执行假设」 | `breakpoint` / `gaps` / `counter` / `lesson` |
| `E4` | `chapter_title` 标题线索 | 仅凭章节标题推测的谋略结构。标题可能只是修辞、可能是烟雾弹、可能与内容无关。 | **不可以** | 只出现在 `dedupe_map.yaml` 的 `chapter_clue_status` |

### 硬性规则

1. **不得把 E4 升格为 E2。** 例如「第 654 章 识破即被骗」不能推出「齐夏在该章用了一个双层骗局」，
   只能推出「作者在第 654 章使用过这个词，可能指向某类结构」。若某条 E4 已被 E1/E2 支撑，必须在
   `dedupe_map.yaml` 里显式写 `status: upgraded_to_fact` 并给出 `upgraded_by`（指向 E1/E2 的 line）。
2. **不得把 E3 写成剧情。** 所有 `breakpoint` / `lesson` 用「可执行推演」口径：写「若…则…」，
   不写「齐夏这样做了」。
3. **每一处外部引用都要带 line。** `line` 指向
   `knowledge/sources/shiri_baike.txt`（3532 行快照；工作区 `research/` 下另有一份同 md5 的同源副本，打包时不随包分发）。
   多个区间用 `a-b,c` 形式。
4. **规则原文只摘要点、不整段复制。** 每条 `rules` 条目应是「判定要素」，而不是原文段落；
   需要原文时用 `line` 回查。
5. **一个字段一个主张。** 不要把「规则」和「我们的发挥」塞进同一条。

## 与 casebook（C01–C23）的关系

- `methodology/casebook.yaml` 的 23 条是**深度案例**（每条含 `confirmed_points / extracted / lesson`），
  偏「机制 + 提炼」。
- 本目录的 `Z*`（十二生肖逐局）与 `Q*`（齐夏战例）是**结构化检索库**，偏「覆盖全 + 可筛选 + 可去重」。
- **不重复叙述已在 casebook 中确认过的内容。** 与既有案例重叠者，一律在 `dedupe_map.yaml` 中登记
  `relation: extends`（只补新事实）或 `duplicate_of`（完全不再重复），并用 `what_is_new` 写明增量。
- 校验脚本 `scripts/cases/audit_cases.py` 会强制检查：新增记录的 `name` 不得与既有 C 案例同名同义、
  每条 `extends` 必须给出 `what_is_new`、每条 `line` 必须落在基线文件行数范围内。

## 一条记录的最小形状

```yaml
- id: ZG-00
  name: 局名
  tier: 地级            # 人级 / 地级 / 天级 / 终极 / 特殊
  host: 地羊            # 原文主办生肖
  lines: "1681-1698"    # 基线文件行号
  players: "51+1"
  ticket: 五个「道」
  rules: []             # E1 要点
  hidden_rules: []      # E1，仅收录原文明确写「隐藏规则」的
  gaps: []              # E3 未定义/可争议处
  breakpoint: []        # E3 可执行破局动作
  counter: []           # E3 反制（作为对手/作为主办方两个方向）
  patterns: [P1.S5]     # 只允许 P1–P5 及其子项
  lesson: ""            # E3 一句教训
  dedupe: {relation: distinct}
  evidence: E1
```
