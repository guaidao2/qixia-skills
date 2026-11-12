# QUICKSTART · 使用指南（5 分钟把齐夏 skills 接到 agent 上）

> 目标：不读原著、不读全部文档，只按本文件走一遍，就能把一个真实局面跑成一份可执行决策报告。
> 本文件只管"**怎么加载、怎么用**"；方法论正文在 `methodology/`，模型正文在 `skills/game-theory/`。

---

## 0. 先确认包是好的（30 秒）

```bash
cd qixia-skills
python3 qixia.py doctor
```

期望最后一行：`体检结果：全部通过 ✅ (N/N)`。

若失败，按 FAIL 行的提示处理：

| FAIL 项 | 含义 | 处理 |
|---|---|---|
| `entrypoint:*` | 包不完整 | 重新解压压缩包；检查是否漏复制子目录 |
| `validate.py` | 方法论层数据不自洽 | 读输出里的"错误/警告"行，通常是手工改过 `patterns.index.json` |
| `qixia_gt:selftest` | 引擎坏了或 Python 版本过低 | 确认 `python3 --version >= 3.8` |
| `no-pyc-in-package` | 包里有 `.pyc` | 只是提示；`pack` 时会自动排除 |

---

## 1. 三种挂载方式（选一种）

### 方式 A：对话内挂载（最快，零配置）

把下面这段作为**第一条消息**发给 agent，或塞进 system prompt：

```text
你现在可以使用 qixia-skills 技能包（路径：/绝对路径/qixia-skills）。
使用规则：
1. 先读 SKILL.md 了解入口；需要路由时执行 `python3 qixia.py ask "<情境>" --json`。
2. 需要"打法"读 methodology/，需要"算数字/硬约束"用 `python3 qixia.py run <solver>`。
3. 任何结论必须带 fail_if（失败条件）与 gaps（规则未定义处）。
4. 不改包内任何文件；所有命令在包根目录执行。
```

### 方式 B：技能目录挂载（Claude Code / 兼容 `skills/` 约定的 agent）

```bash
cp -r qixia-skills ~/.claude/skills/qixia     # 或对应 agent 的 skills 目录
# 之后 agent 依据 SKILL.md 的 frontmatter（name/description）自动加载
```

若该 agent 只认单文件技能，直接放 `SKILL.md` 即可——它不含长内容，只指向包内其余文件（因此**必须同时复制整个目录**）。

### 方式 C：作为工具库调用（有代码执行能力的 agent / 自动化流水线）

```python
import json, subprocess
def qixia(args, root="/abs/path/qixia-skills"):
    r = subprocess.run(["python3", "qixia.py", *args], cwd=root, capture_output=True, text=True)
    return json.loads(r.stdout) if "--json" in args else r.stdout

route = qixia(["route", "对手碾压我，正面必输，但他有个必须救的人", "--json"])
print(route["patterns"][0]["id"], [m["code"] for m in route["models"]], route["next"])
```

三种方式的共同点：**agent 永远只通过 `qixia.py` 与包交互**（或直接透传下层脚本），不直接读写数据文件。

---

## 2. 五分钟主线：从一个局面到一份报告

### 第 1 分钟 · 定位方法

```bash
python3 qixia.py pattern eight          # 谋略八问：先把信息缺口列出来
python3 qixia.py ask "只有口头规则，裁判有最终解释权，输了要赔命"
# → P1 规则侦察（low） + G4 机制审计 / G12 元博弈
```

### 第 2 分钟 · 读方法（只读一个模式）

```bash
python3 qixia.py pattern show P1         # 触发条件 / 执行步骤 / 失败条件 / 反制 / 案例锚点
python3 qixia.py pattern premortem P1     # 先看它会怎么死
```

### 第 3 分钟 · 把局面写成参数

最少可以只写四行（其余引擎会用 `gaps` 提示你补）：

```json
{
  "name": "我的局",
  "summary": "规则原文 + 隐藏规则 + 裁判是谁 + 赌注是什么（自然语言，越长越好）",
  "keywords": ["规则", "裁判", "赌注"],
  "g4": { "略": "见 skills/game-theory/SCHEMAS.md" }
}
```

字段速查：`skills/game-theory/SCHEMAS.md`；范例：`cases/gt/situation_interview_room.json`。

### 第 4 分钟 · 跑

```bash
python3 qixia.py run audit --file my_situation.json --out reports/gt/<局名>.md --json
```

先看 `gaps[]`（破局点 + 待办），再看每个模型的 `verdict` / `action` / `fail_if`。

### 第 5 分钟 · 收口

```bash
python3 qixia.py pattern check P1        # 把 checklist 当执行清单逐项打勾
```

输出给使用者时，只保留四行：

```text
结论：<verdict 一句话>
依据：<关键数字 1–2 个> + <gaps 里最要命的一条>
下一步：<action 中不可逆性最低的那个>
失败条件：<fail_if 里排第一的那条>
```

---

## 3. 四个实战走查（按任务类型）

### 3.1 "我要审计一套规则，找它的漏洞"

```bash
python3 qixia.py pattern show P1
python3 qixia.py run mechanism --file cases/gt/g4_mechanism_feisheng.json     # 参照：DSIC/IR 违反怎么被找出来
python3 qixia.py run audit --file <你的 situation.json> --json                 # gaps[] 就是漏洞清单
```

要点：先冻结规则原文（P1-S1），再找"未定义词 / 判定函数 / 平局 / 时限 / 解释权 / 隐藏权限"六类缺口。**只审计，不下注**——这是本包最基本的安全用法。

### 3.2 "对手比我强，我要布局"

```bash
python3 qixia.py pattern show P3
python3 qixia.py run backward --file cases/gt/g6_tree_changjie.json   # 威胁是否可信
python3 qixia.py run meta --file cases/gt/g12_meta_dao.json           # 赢了之后谁结算
python3 qixia.py pattern premortem P3
```

要点：P3 的层数上限是 3–4 层，必须有第二计；**先用 `backward` 验证对手威胁可信度，再设计诱饵层**，否则整条链建立在假威胁上。

### 3.3 "有人拉我对赌 / 要我签合同"

```bash
python3 qixia.py pattern show P4
python3 qixia.py run screening --theta-h 100 --theta-l 20 --prior 0.5   # 菜单能不能筛出类型
python3 qixia.py run signaling --file cases/gt/g3b_signaling_contract_fixed.json  # 押注标的怎么改才有分离均衡
```

要点：七要素（标的/对手/判定函数/筹码/时间/制裁/裁决者）缺一不可；**"参与者不能拒绝赌命"**，所以目标是让赌局不成立或抢占裁决结构，而不是"礼貌拒绝"。

### 3.4 "一局结束了，我要复盘"

```bash
python3 qixia.py pattern show P5                         # 对内军心 / 对外攻心
python3 qixia.py run sunk --file cases/gt/g7_sunk_250.json   # 复盘"该不该继续"的判据
```

要点：复盘只更新三样东西——对手的实际频率、你自己的先验、以及那个"下次一定改"的失败条件。**别把一次样本当成对手的偏差**。

---

## 4. 把"故事"翻译成参数的五个动作

模型跑不起来，99% 是参数没落地。按顺序做（详见 `skills/game-theory/SKILL.md` §3）：

1. **列决策者**：我 / 对手 / 裁判 / 结算者。裁判与结算者也是玩家，漏掉他们是最常见的错。
2. **列动作与顺序**：同时动 → 收益矩阵；有先后 → 博弈树；由规则分配 → 机制表。
3. **列收益来源**：钱 / 道 / 命 / 记忆 / 队友 / 时间。不能货币化的要显式折算（如"被处决 = −100"），并在 `note` 里写明"这是建模假设"。
4. **填数字**：概率、底池、下注、贴现因子、类型先验。原文没给就自己设并标注。
5. **跑三遍**：基准 / 悲观 / 乐观。三个都一致才可下结论。

---

## 5. 常见卡点

| 现象 | 原因 | 处理 |
|---|---|---|
| `ask` 返回空 `patterns` | 情境描述太抽象（如"怎么办"） | 换成现象描述："规则是口头传达的""裁判能改结果""他让我先下注" |
| `ask` 的 `models` 是关键词兜底 | 关键词没命中 | 直接跑 `run audit --file <situation.json>`，引擎会按 `keywords` 字段识别 |
| `run <solver>` 报参数缺失 | 该模型的 JSON 段没填 | 报告会写"参数缺失：… 下一步：运行 xxx"，按提示补 |
| 结论和直觉冲突 | 可能落在陷阱区间（如 `p* ≤ p < p_lookback`） | 用三值法复跑，检查是不是"情绪 vs 理性"的分界 |
| `--out` 写不进去 | 相对路径被解析到别处 | 先 `python3 qixia.py where` 拿绝对路径，或用绝对路径输出 |
| `gate` / 新 solver 用法不确定 | 引擎在演进 | `python3 qixia.py run --help` 与 `run models` 永远是最新事实来源 |

---

## 6. 交付前自检（3 条命令）

```bash
python3 qixia.py doctor     # 全 PASS（agent 能否加载与调用）
python3 qixia.py status     # missing=0
sh build_package.sh         # 正式交付打包（tar.gz + zip + sha256 + PACKAGE.json + 解包自检）
python3 qixia.py pack       # 轻量版：只要一个 zip + sha256 时用
```

更完整的验收清单见 `SKILL.md` §7。

---

## 7. 纪律（违反这三条，本包会变成自毁说明书）

1. **先算"不做"的收益**——存在"不动即胜"的解时，任何策略都是多余的。
2. **任何计划必须有第二计**——主计 / 备用计 / 脱身计。
3. **只用于对抗性博弈、谈判、红队演练与规则审计**，不用于对真实个人实施欺诈、胁迫或诱导自伤。
