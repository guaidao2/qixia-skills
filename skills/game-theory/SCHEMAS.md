# JSON 入参 / 出参速查（每个求解器一份）

> 约定：所有子命令都是 `python3 scripts/gt/qixia_gt.py <solver> --file <json> [--json] [--out report.md]`。
> 也可以不用文件，直接用 CLI 参数（`--pot/--bet/--theta-h/...`）。
> 出参固定 9 个字段：`model, solver, title, verdict, evidence[], numbers{}, action, counter, fail_if[], gaps[]`。

---

## G1 `pd` — 囚徒困境 / 重复博弈

```json
{
  "name": "局面名",
  "anchor": "原书锚点",
  "row": {"name": "我方", "actions": ["C 合作", "D 背叛"]},
  "col": {"name": "对手", "actions": ["C 合作", "D 背叛"]},
  "payoffs": [[[3, 3], [0, 5]],
              [[5, 0], [1, 1]]],
  "repeated": {"mode": "infinite", "delta": 0.9}
}
```

- `payoffs[i][j] = [行玩家收益, 列玩家收益]`，与 `actions` 顺序一一对应。
- `repeated.mode`：`"infinite"`（配 `delta`）或 `"finite"`（配 `periods`）；省略 = 不结算重复性。
- 出参 `numbers`：`game_class`、`pure_nash`、`dominant`、`T/R/P/S`、`is_prisoners_dilemma`、`delta_star`、`row_maximin`。

## G2 `bayes` — 贝叶斯更新 / 信息价值

```json
{
  "types": ["状态0", "状态1"],
  "prior": 0.5,
  "observations": [{"name": "观测名", "likelihood": [0.9, 0.2]}],
  "actions": [{"name": "动作A", "payoff": [10, -10]},
              {"name": "动作B", "payoff": [0, 0]}]
}
```

- `likelihood = [P(观测|状态0), P(观测|状态1)]`；可给多条 `observations`（等价于多都做贝叶斯更新）。
- `actions[].payoff = [在状态0下的收益, 在状态1下的收益]`。
- 出参 `numbers`：`bayes.posterior`、`action_ev`、`best_action`、`EVPI`。

## G5 `mixed` — 混合策略纳什均衡

```json
{
  "row": {"name": "我", "actions": ["R", "P", "S"]},
  "col": {"name": "他", "actions": ["R", "P", "S"]},
  "payoffs": [[[0,0],[-1,1],[1,-1]],
              [[1,-1],[0,0],[-1,1]],
              [[-1,1],[1,-1],[0,0]]]
}
```

- 2×2 用解析解；n×m（≤4×4）用支撑枚举，有理数精确。
- 出参 `numbers`：`game_class`（pd/stag_hunt/chicken/coordination/matching_pennies/zero_sum/asymmetric）、`equilibria[]`（`type/row/col/payoff/deviation_gain`）、`row_maximin`。

## G3 `signaling` — 信号博弈

```json
{
  "types": ["强", "弱"],
  "prior": 0.5,
  "signals": ["昂贵信号", "便宜信号"],
  "actions": ["接受", "拒绝"],
  "sender_payoff": {"强": {"昂贵信号": {"接受": 10, "拒绝": 0},
                            "便宜信号": {"接受": 6, "拒绝": 0}},
                     "弱": {"昂贵信号": {"接受": -3, "拒绝": 0},
                            "便宜信号": {"接受": 6, "拒绝": 0}}},
  "receiver_payoff": {"昂贵信号": {"接受": {"强": 8, "弱": -2}, "拒绝": {"强": 0, "弱": 0}},
                       "便宜信号": {"接受": {"强": 4, "弱": 2},  "拒绝": {"强": 0, "弱": 0}}}
}
```

- 严格按 `sender_payoff[类型][信号][动作]`、`receiver_payoff[信号][动作][类型]` 索引。
- 出参 `numbers`：`single_crossing`、`gain_by_type`、`equilibria[]`（`type: separating|pooling`、`offpath_robust`）、`n_equilibria`。
- 判定逻辑：分离均衡存在 → 信号有信息量；只有混同 → 信号是噪音（需要用 G11 改成本结构）。

## G11 `screening` — 甄别菜单 / 信息租金

```json
{"theta_high": 10, "theta_low": 6, "prior_high": 0.5}
```

- 或用 CLI：`--theta-h 10 --theta-l 6 --prior 0.5`。
- 出参 `numbers`：`q_high`、`q_low`、`t_high`、`t_low`、`info_rent`、`profit`、`first_best_profit`、`shutdown`、`ic_binding`、`strict_separating`、`self_selection{H_high,H_low,L_high,L_low}`。

## G4 `mechanism` — 机制 / 规则审计

```json
{
  "player_types": {"A": [10, 4], "B": [10, 4]},
  "prior": {"A": [0.5, 0.5], "B": [0.5, 0.5]},
  "reports": [0, 1],
  "rule": [
    {"report": [0, 0], "alloc": [1, 0], "pay": [3, 0]},
    {"report": [0, 1], "alloc": [1, 0], "pay": [3, 0]},
    {"report": [1, 0], "alloc": [0, 1], "pay": [0, 3]},
    {"report": [1, 1], "alloc": [0, 0], "pay": [0, 0]}
  ]
}
```

- `player_types[玩家] = [高类型估值, 低类型估值]`；`reports` 的取值是**类型索引**（0=高，1=低）。
- `rule[]` 覆盖所有报告组合；`alloc` 是分配概率（单物品应满足 `x_A+x_B ≤ 1`），`pay` 是支付（负数=给玩家钱）。
- 效用定义：`u = 类型估值 × alloc − pay`。
- 检查项：DSIC、BIC、IR、预算平衡、可行性（印资源）、资金泵（0 分配却收钱）、效率。
- 出参 `numbers`：`expected_welfare`、`first_best_welfare`、`efficiency_ratio`；`violations{dsic,ir,bb,money_pump}`；违规事实同时进 `gaps[]`。

## G6 `backward` — 逆向归纳

```json
{
  "players": ["我", "对手"],
  "tree": {"player": 0, "actions": {
      "进": {"player": 1, "claimed_best": "战", "actions": {
              "战": {"payoffs": [-1, -5]},
              "退": {"payoffs": [2, 0]}}},
      "退": {"payoffs": [0, 1]}}},
  "simultaneous": {"row": {"actions": ["进", "退"]},
                   "col": {"actions": ["进", "退"]},
                   "payoffs": [[[-1,-1],[2,0]],[[0,2],[0,0]]]}
}
```

- 节点：`{"player": 索引, "actions": {动作名: 子节点}}`；叶子：`{"payoffs": [u0, u1]}`。
- `claimed_best`（可选）：对方**宣称**会选的动作。工具会检查它是否真的是最优——不是就判为**不可信威胁**。
- `simultaneous`（可选）：同时行动版本，用于算先手价值。
- 出参 `numbers`：`spne_value`、`strategy`、`spne_path`、`first_mover_advantage`、`non_credible_nodes`。

## G7 `sunk` — 沉没成本 / 承诺升级

```json
{"sunk_cost": 7, "continue_cost": 10, "win_prob": 0.3, "prize": 100, "quit_value": 5,
 "war_of_attrition": {"prize": 100, "cost_per_period": 10}}
```

- 出参 `numbers`：`ev_continue`、`p_star`、`p_lookback_threshold`、`war_of_attrition_expected_duration`。
- 判读：`p < p*` → 立刻止损；`p* ≤ p < p_lookback` → **陷阱区间**（理性应继续，情绪会让你放弃）；`p ≥ p_lookback` → 继续且把 S 转成承诺资产。

## G8 `bluff` — 诈唬频率 / 底池赔率

```json
{"pot": 2, "bet": 1, "opponent_fold_freq": 0.45, "payout_multiplier": 3}
```

- 出参 `numbers`：`MDF`、`alpha`、`bluff_fraction_of_bets`、`value_to_bluff_ratio`、`ev_bluff_given_fold`、`payout_adjusted_MDF`。

## G9 `prob` — 概率分配设计

```json
{"black": 50, "white": 50, "allow_equal_bowls": true}
```

- 暴力搜索所有整数分配（≤51×51），返回精确最优（`fractions.Fraction`）。
- 出参 `numbers`：`best_prob`、`bowl1`、`bowl2`、`equal_split_prob`、`gain_vs_equal`。
- `allow_equal_bowls: true` 时额外提示"每碗 50 颗"解读下的胜率退化（恒 50%）。

## `metaq` — 是与非型元问题

```bash
python3 scripts/gt/qixia_gt.py metaq --prop "碗A摸到的是黑子"
```

- 出参 `numbers.truth_table`（真话者/说谎者 × 命题真假 4 行真值表）、`numbers.normalizes`（是否恒等于命题真值）。

## G10 `common` — 共同知识 / 两军问题

```json
{"reliability": 0.9, "msgs": [1, 2, 3, 5, 12], "target": 0.99}
```

- 出参 `numbers`：`coord_prob{"1": .., "2": ..}`、`max_usable_rounds`（目标可达的最大确认轮数；<1 表示不可达）。

## G12 `meta` — 元博弈 / 目标函数审计

```json
{"goal_source": "other", "settler_trusted": false, "settler_can_alter": true,
 "has_exit_option": false, "has_second_goal": false}
```

- 出参 `numbers.meta_risk_score`（0–9，≥4 表示"赢了也可能归零"）、`risks[]`。

## `poker` — 朔望月点数判定

```json
{"cards": [9, 7], "public": 5, "cap": 16}
```

- 枚举"用不用公共牌 / 用几张手牌"的所有子集，过滤 `> cap`（爆牌），取最接近 cap 的合法组合。
- 出参 `numbers`：`best_score`、`best_combo`、`legal_scores`。

## `audit` — 局面审计（总入口）

```json
{
  "name": "局面名",
  "summary": "自然语言描述（规则文本/局面，可长）",
  "keywords": ["规则", "下注", "隐藏"],
  "g4": { ...mechanism 入参... },
  "g1": { ...pd 入参... },
  "g2": { ...bayes 入参... },
  "g6": { ...backward 入参... },
  "g8": { ...bluff 入参... },
  "g9": { ...prob 入参... },
  "g12": { ...meta 入参... }
}
```

- 用关键词命中 + 显式 `gN` 段两条路径选择模型；`summary` 命中的模型若没有对应参数段，会输出"参数缺失 + 下一步命令"，不会崩。
- 输出：Markdown 报告（`verdict / action / counter / evidence / numbers / gaps` + 汇总的规则未定义处 + 强制决策顺序）。
- 建议：**先写 summary（自然语言），跑一次 audit 看它选了哪些模型**，再逐个补参数段，反复跑到"所有识别到的模型都有结果"。
