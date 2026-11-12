# T2 · 复杂局面全审计（P + G 全链条）

**用途**：局面复杂、涉及多方、有规则+有赌注+有时限，需要一份可直接执行的决策报告。
**代价**：token 较多；简单局面请用 T6。

**变量**
- `{{局面描述}}`：现象，不要评价（"裁判可以改判"而不是"这不公平"）
- `{{已知}}` / `{{未知}}`：分两栏列
- `{{时间压力}}`：多久必须决定

---

```text
在 {{PACK_ROOT}} 下工作。把下面这个局面跑成一份可执行决策报告。

局面：
"""
{{局面描述}}
"""
我已确认的信息：{{已知}}
我尚不知道的：{{未知}}
时间压力：{{时间压力}}

执行步骤（不许跳步）：
1. `python3 qixia.py route "<局面一句话>" --json`
   → 记录 patterns[].id 与 hits（选这个模式的理由）、models[].solver（必算模型）。
2. 对主模式：`python3 qixia.py pattern show <P?>` 与 `pattern premortem <P?>`。
3. 把局面写成 situation.json（最少填 name/summary/keywords，其余按
   {{PACK_ROOT}}/skills/game-theory/SCHEMAS.md 补），然后：
   `python3 qixia.py run audit --file situation.json --json`
4. 对 audit 识别出的每个模型，读它返回的 verdict / numbers / action / counter / fail_if / gaps。
5. 若结论依赖某个参数，用基准/悲观/乐观三值重跑该 solver，并说明结论是否稳定。
6. 下注/承诺前追加 `python3 qixia.py run gate --file <gate.json>`（七道闸）。

输出格式：
① 路由结论：主模式 + 必算模型 + 为什么（引用 hits，不要编）
② 关键数字：≤3 个，每个都要说明它代表什么
③ gaps：规则未定义 / 激励不相容 / 参数缺失，各列 ≤3 条，标出"最要命的一条"
④ 动作时间线：按"不可逆性从低到高"排序，每条注明对应模型与预期反制
⑤ 失败条件：每个动作一条 fail_if
⑥ 一个"不做"的选项：如果什么都不做会怎样，为什么（不）可选
⑦ 待补信息：按成本从低到高排序，说明补上后哪条结论会改变

禁止：把假设写成事实；给出没有 fail_if 的建议；忽略 gaps。
```

**期望输出**：①–⑦ 七段，②不超过 3 个数字，④可被逐条执行。
**失败信号**：动作时间线里出现"同时做"——不可逆动作和试探动作不能并列。
