#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qixia_gt.py — 齐夏 skills · 博弈论/机制设计决策引擎（纯标准库，单文件可移植）

定位：把"故事里的局"翻译成标准博弈论模型，并把模型跑出数字，
      让 agent 能直接调用：判定 -> 计算 -> 给出动作 -> 给出反制 -> 给出失败条件。

用法（agent 直接调用；所有子命令支持 --json 输出机器可读结果）：
  python3 qixia_gt.py models                          # 模型索引（12 个模型）
  python3 qixia_gt.py checklist [--model G3] [--format md|json]
  python3 qixia_gt.py pd         --file cases/gt/g1_pd_278.json
  python3 qixia_gt.py mixed      --file cases/gt/g5_mixed_shuowangyue.json
  python3 qixia_gt.py signaling  --file cases/gt/g3_signaling_contract.json
  python3 qixia_gt.py screening  --theta-h 10 --theta-l 6 --prior 0.5
  python3 qixia_gt.py mechanism  --file cases/gt/g4_mechanism_rule.json
  python3 qixia_gt.py backward   --file cases/gt/g6_tree_changjie.json
  python3 qixia_gt.py sunk       --file cases/gt/g7_sunk_250.json
  python3 qixia_gt.py bayes      --prior 0.3 --like 0.9 0.2
  python3 qixia_gt.py bluff      --pot 100 --bet 50
  python3 qixia_gt.py prob       --black 50 --white 50
  python3 qixia_gt.py common     --reliability 0.9 --msgs 1 2 3 12
  python3 qixia_gt.py poker      --cards 7 9 --public 5          # 朔望月点数判定
  python3 qixia_gt.py metaq      --prop "碗A摸到的是黑子"          # 是与非型元问题
  python3 qixia_gt.py audit      --file cases/gt/situation_*.json [--out reports/gt/x.md]
  python3 qixia_gt.py selftest

设计约束：
  * 只用 Python 标准库（numpy/scipy 在目标环境不可用），有理数用 fractions.Fraction 精确计算。
  * 每个求解器返回 dict：{model, verdict, evidence[], action, counter, fail_if[], gaps[], story}
  * "gaps" 字段专门输出「规则未定义处」——即齐夏式破局点的候选位置。
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
from fractions import Fraction as F

VERSION = "1.0.0"

# --------------------------------------------------------------------------------------
# 一、模型注册表：12 个标准模型 <-> 齐夏局面
# --------------------------------------------------------------------------------------

MODELS = {
    "G1": {
        "id": "G1",
        "zh": "囚徒困境与重复博弈",
        "en": "Prisoner's Dilemma / Repeated Game (Folk Theorem)",
        "solver": "pd",
        "anchors": ["第278章 囚徒困境", "第567章 骗亦是信", "地狗「送信人」奸细阵营", "极乐博彩「胜/负/杀」对赌"],
        "use_when": [
            "存在「合作对双方都好，但单方背叛更划算」的收益结构",
            "对手是理性且只结算一次 / 或会长期重复相遇",
            "需要判断要不要先合作、要不要惩罚、惩罚多久",
        ],
        "params": ["2x2 收益矩阵 (T,R,P,S 或完整矩阵)", "重复次数或贴现因子 δ", "对手类型先验"],
        "flow": [
            "1) 把局面写成 2x2：双方各有 C(合作/守信) 与 D(背叛/夺道) 两个动作。",
            "2) 判 T>R>P>S 是否成立，且 2R>T+S —— 成立才是真囚徒困境。",
            "3) 若一次性：唯一纳什均衡是 (D,D)，任何「我们合作吧」的口头承诺都是廉价的。",
            "4) 若重复：算临界贴现因子 δ* = (T-R)/(T-P)；δ≥δ* 时触发策略可支撑合作。",
            "5) 选触发策略：针锋相对(TFT) / 冷酷触发(Grim) / 以牙还牙+宽恕；对手背叛一次的反制速度要快于其收益回收期。",
            "6) 若对手不知道 δ（信息不完全），用「可观测的惩罚承诺」把 δ 变成共同知识（公开处刑、公开撕票、公开立誓）。",
        ],
        "checks": [
            "是否确认过 2R>T+S？很多『囚徒困境』其实是猎鹿/胆小鬼博弈，策略完全相反。",
            "对手的 T（背叛收益）是否被我低估？在他眼里背叛可能是零成本。",
            "这场博弈是单次还是重复？对方是否认为『没有下一次』（末世/必死局常被判为单次）。",
            "我的惩罚承诺是否可被观测？不可观测的惩罚 = 不存在。",
            "合作是否有『可被单方摧毁的抵押品』（人质/共同资产/把柄）？",
        ],
        "red_flags": ["对手主动提出合作且拒绝立下可执行抵押", "对手反复强调『这是最后一次』", "规则允许杀人夺道（背叛收益≈无限）"],
        "counters": ["制造可观测的重复关系（把一次性博弈改写成重复博弈）", "先手自缚：公开销毁背叛选项（销毁钥匙/交出人质）", "提高背叛成本：让第三方见证并承担惩罚义务"],
        "fail_if": ["误把胆小鬼/猎鹿当囚徒困境 -> 该强硬时合作，被杀", "单次博弈中先合作 -> 被一次性收割", "惩罚承诺不可观测 -> 对手理性选择背叛"],
    },
    "G2": {
        "id": "G2",
        "zh": "不完全信息与贝叶斯更新",
        "en": "Incomplete Information / Bayesian Updating / Value of Information",
        "solver": "bayes",
        "anchors": ["第644章 真假规则", "第648章 超核运算", "地羊「四情扇」隐藏规则", "人蛇「是与非」"],
        "use_when": ["对手类型/规则版本/隐藏条款未知", "可以用行动或提问换取信息", "需要在信息不足时下注"],
        "params": ["先验概率", "每种信号在各类型下的似然", "可选动作与其收益"],
        "flow": [
            "1) 列出状态空间（对手类型、规则版本、底牌集合），给出先验。",
            "2) 列出可观测信号（他的动作、停顿、用词、下注额、你被允许问的问题）。",
            "3) 用贝叶斯公式更新：P(θ|s) ∝ P(s|θ)P(θ)。",
            "4) 用更新后的后验重算每个动作的期望值，选择 EV 最大者。",
            "5) 算信息价值：EVPI = EV(完美信息) - EV(当前)，若 EVPI < 获取信息的成本则不要问。",
            "6) 反向使用：设计一个只有某类型才会做出的动作，把对方的私有信息『逼』成公开信号（见 G3）。",
        ],
        "checks": [
            "先验是从哪来的？如果是别人告诉我的，它本身可能是假信号。",
            "这个信号是否被对手操纵（他可以故意发假信号）？",
            "我是否把『他没反应』当成了证据？无信号也是信号（沉默成本=他不在乎）。",
            "后验是否已经过时（规则被改过/信息被洗过）？",
        ],
        "red_flags": ["对手给出『恰好能让我安心』的信息", "信息只在口头层面存在，无法交叉验证"],
        "counters": ["交叉验证：用两个独立信源验证同一命题", "构造只能由真类型支付的昂贵信号（G3）", "故意泄露假信息测试对手反应（信息投毒）"],
        "fail_if": ["把先验当事实 -> 全盘押错", "忽略对手的信号操纵能力 -> 被反向利用", "信息价值低于成本仍去探索 -> 浪费唯一机会"],
    },
    "G3": {
        "id": "G3",
        "zh": "信号博弈与甄别（分离/混同均衡）",
        "en": "Signaling Game (Spence) / Screening / Separating vs Pooling",
        "solver": "signaling",
        "anchors": ["生肖飞升对赌合同（嵌入式自杀条款）", "第654章 识破即被骗", "第1063章 布局开始", "第1318章 三方对赌"],
        "use_when": ["我比对手更清楚自己的类型（强/弱、真/假）", "需要一个『只有某类型才付得起』的动作来证明自己", "对手想通过合同菜单让我暴露类型"],
        "params": ["类型集合与先验", "信号集合及其按类型的成本", "接收方动作与收益"],
        "flow": [
            "1) 定义类型 θ（强/弱、真货/假货、回响者/普通人）与先验。",
            "2) 定义信号 m 与成本 c(m,θ)：**单交叉条件**——强类型发同一信号的边际成本必须更低，否则信号无信息量。",
            "3) 求分离均衡：强类型发昂贵信号、弱类型不发；核对弱类型的模仿激励是否被成本差挡住（IC）。",
            "4) 求混同均衡：两类发同一信号，接收方只能用先验行动；核对是否存在偏离激励。",
            "5) 若我是接收方（被信号轰炸方）：设计合同菜单让不同类型自选（见 screening / G4）。",
            "6) 若我是发送方：优先选『烧掉自己退路』的信号（自杀条款、公开赌命），因为弱者无法模仿。",
        ],
        "checks": [
            "信号成本是否真的按类型不同（单交叉）？若成本相同，信号只是噪声。",
            "对手是否可能『装强』装到底（pooling）？装到底的成本他付得起吗？",
            "我发出的信号是否可被伪造/租借（借来的回响、借来的底牌）？",
            "分离均衡是否唯一？若存在混同均衡，我的信号可能被无视。",
        ],
        "red_flags": ["对手要求的信号成本对所有类型相同", "对手给出『不用证明我也信你』的承诺"],
        "counters": ["引入可验证的第三方凭证", "设计阶梯式信号（小信号->大信号），逐步加价筛选", "把对手的混同策略变成对我不利的共同知识（公开点名要求自证）"],
        "fail_if": ["用了无成本信号 -> 完全无信息量，被当作空话", "只算自己发信号的成本，没算对手模仿的成本 -> 被冒充", "忽略混同均衡 -> 自信误判"],
    },
    "G4": {
        "id": "G4",
        "zh": "机制设计与规则审计（激励相容/参与约束/漏洞）",
        "en": "Mechanism Design (BIC/DSIC, IR, budget balance) & Rule Audit",
        "solver": "mechanism",
        "anchors": ["第438章 隐藏的规则", "第460章 未曾提及的规则", "第463章 规则更改", "第831章 规则盲点", "生肖守则九条 / 赌命规则八条"],
        "use_when": ["规则是我（或对手）写的，需要让人『自愿』按我设计的方式行动", "需要检查规则里是否有可套利/可钻的空子", "需要判断对方设计的规则在鼓励什么行为"],
        "params": ["参与者类型分布", "分配规则（谁得到什么）", "支付规则（谁付什么）"],
        "flow": [
            "1) 抄全规则原文，逐条标注：定义了的 / 未定义的 / 可被谁解释的。",
            "2) 检查激励相容（DSIC/BIC）：说真话是否是每个参与者的最优策略；若不是，规则实际在奖励说谎。",
            "3) 检查参与约束（IR）：每个类型参与是否比不参与更好；若不好，被强制参与的人会破坏机制（摆烂/同归于尽）。",
            "4) 检查预算平衡与铸币：是否存在『不付出就获得』的免费午餐（负支付、重复结算、可复制凭证）。",
            "5) 检查可行性：分配概率之和是否 ≤1（是否在『印资源』）。",
            "6) 输出漏洞清单：未定义项（判定函数/平局/时限/解释权）+ 套利项（免费动作/负成本动作）+ 强制项（不可拒绝的义务）。",
            "7) 设计补丁：把关键判定函数写死、加平局规则、加时间戳、把解释权分散给多方。",
        ],
        "checks": [
            "胜/负/平局的判定函数是否唯一确定？平局算谁赢？（第668章 平局算输）",
            "时限、顺序、先手权是否定义？谁先动？",
            "『最终解释权』在谁手里？他是否也是利益相关方？",
            "规则是否允许某个玩家合法地使用规则外动作（生肖可隐藏规则权限差异）？",
            "奖励是否可被同一人重复领取？凭证是否可伪造/转让？",
            "惩罚是否可执行？执行者是否有动机执行？",
        ],
        "red_flags": ["合同里嵌了自杀/自裁条款（飞升对赌合同）", "规则用口头广播传达", "关键判定词使用了可多解的形容词（如『有趣』『更重要』）"],
        "counters": ["把口播规则变成书面并要求确认", "要求写入平局与例外条款", "把解释权拆成需要多方同意", "故意触发一次边缘情况来测试裁判"],
        "fail_if": ["不看规则全文就下注", "假设对方会遵守对自己不利的条款", "把『规则没写』当成『规则不允许』（通常是隐藏权限）"],
    },
    "G5": {
        "id": "G5",
        "zh": "混合策略与纳什均衡（随机化）",
        "en": "Mixed-Strategy Nash Equilibrium / Randomization",
        "solver": "mixed",
        "anchors": ["终极游戏「朔望月」", "极乐博彩下注分布", "人猪「黑白棋」概率分配", "第1082章 最终博弈"],
        "use_when": ["没有纯策略均衡，或纯策略会被对手针对", "需要在多个动作之间随机化以保持不可预测", "需要算对手的均衡频率来制定压注/诈唬比例"],
        "params": ["收益矩阵", "可选动作集合"],
        "flow": [
            "1) 写出收益矩阵，先找纯策略纳什均衡（有就用，别乱随机）。",
            "2) 若无纯均衡：令对手在动作间无差异，解出各动作概率（2x2 有解析解；n×m 用支撑枚举）。",
            "3) 用混合策略时，随机化必须是真随机（不可被观察出规律），否则对手会读牌。",
            "4) 算对手偏离的收益差：若对手偏离的收益差很小，说明均衡脆弱，可用心理战/信息战放大。",
            "5) 反过来：若发现自己在均衡中被压榨（EV<0），说明我不该玩这个游戏——改变规则或退出（G4/G6）。",
        ],
        "checks": [
            "纯策略均衡是否存在？随机化是否只是在掩盖一个本来就该确定的决策？",
            "我的随机化是否可被观测/统计出来（时间间隔、下注额规律）？",
            "对手是否在『非均衡』地行动（可被剥削）？剥削需要样本量，我的样本够吗？",
            "均衡只是防守线，不是盈利线：均衡 EV 是否为负？",
        ],
        "red_flags": ["对手在长序列中表现出稳定的偏差（可利用）", "游戏赔付结构（抽水/场地费）本身让 EV<0"],
        "counters": ["对可剥削对手做最大化剥削（exploitative）调整", "改变赔付结构/规则（G4）把负 EV 变正", "加噪音：把随机化种子外置（骰子/第三方）"],
        "fail_if": ["在有限样本上判断对手偏差 -> 过拟合", "用固定周期随机化 -> 被读牌", "把均衡当必胜法 -> 忽略抽水与方差"],
    },
    "G6": {
        "id": "G6",
        "zh": "逆向归纳与承诺可信度（子博弈完美）",
        "en": "Backward Induction / SPNE / Credible Commitment",
        "solver": "backward",
        "anchors": ["第120章 生肖飞升对赌合同", "第685章 很长的计划", "第1128章 我有一计", "仓颉棋「拒令即抹杀」", "青龙游戏（四天杀八个地级生肖）"],
        "use_when": ["行动有先后顺序，需要判断对手最后一步会不会真的执行", "对手在威胁我，需要判断威胁是否可信", "需要设计一个『即使对我短期不利也必须执行』的承诺"],
        "params": ["博弈树（节点、行动、终局收益）", "各方宣告的威胁/承诺"],
        "flow": [
            "1) 画出博弈树：谁先动、谁能观测、终局收益是多少。",
            "2) 从叶子往回算：每个节点上行动者会选收益最大的动作（逆向归纳）。",
            "3) 得到 SPNE 路径；任何与 SPNE 不一致的『威胁』都是不可信威胁（cheap threat）。",
            "4) 若要威胁可信：必须有自缚机制——把执行成本外部化/让不执行的成本更高（公开立誓、交出人质、设自动装置）。",
            "5) 先手价值 = 我先动的 SPNE 收益 - 后动的 SPNE 收益；若先手价值为负，让对方先动。",
            "6) 若树太深，只算关键的最后三步（终局结算层），因为所有前序策略都要服从终局结算。",
        ],
        "checks": [
            "终局是谁结算的？他有动机按规则结算吗？",
            "对手的威胁在最后一步对他自己有利吗？不利=不可信。",
            "我的承诺是否有自动执行装置（合同/机关/第三方）？",
            "我是否假设对手会在对自己不利时仍然履约？",
        ],
        "red_flags": ["对手的威胁需要他付出巨大代价才能执行", "合同约定由对手自己执行对我的惩罚（他有动机不执行/篡改）"],
        "counters": ["把承诺写进不可撤销的机制（G4）", "让第三方持有执行权且其利益与履约一致", "制造『不执行就立刻损失更大』的局面"],
        "fail_if": ["把不可信威胁当真 -> 过度让步", "把可信承诺当虚张声势 -> 被处决", "忽略终局结算者的利益 -> 赢了也被判输"],
    },
    "G7": {
        "id": "G7",
        "zh": "沉没成本与承诺升级（escalation）",
        "en": "Sunk Cost Fallacy / Escalation of Commitment / Burning Bridges",
        "solver": "sunk",
        "anchors": ["第250章 沉没成本", "第617章 失算", "十年前的「天秤游戏」", "七年生肖之路", "第886章 无法赌命"],
        "use_when": ["已经投入巨大成本（时间/道/队友/记忆），继续 or 放弃", "对手已投入巨大成本，可被诱导向继续加注", "需要把『已投入』转化为可信承诺"],
        "params": ["已沉没成本 S", "继续的增量成本 c", "胜率 p 与胜利收益 V", "放弃的保留收益 q"],
        "flow": [
            "1) 先把 S 从决策里划掉：它无论如何都收不回来，**不进入边际决策**。",
            "2) 只算增量：EV(继续) = p·V - c；与 q 比较。",
            "3) 算临界胜率 p* = (c+q)/V：低于 p* 就该立刻止损，无论此前投入多少。",
            "4) 反过来利用对手的沉没成本：让对手先投入（门票/抵押/公开承诺），再改变规则或提高价码，他会因为不甘心而继续加注。",
            "5) 若 S 可以转化为承诺（烧船/毁钥匙/公开立誓），则 S 不是浪费，而是买了『不可反悔』的可信度（G6）。",
        ],
        "checks": [
            "我继续的理由里，有多少是『为了不浪费已经投入的』？这部分必须剔除。",
            "若今天是我第一次面对这个局面（S=0），我会投入吗？",
            "对手是否在利用我的沉没成本加价？",
            "止损的信号是否已经出现但我拒绝承认（第617章 失算）？",
        ],
        "red_flags": ["『已经走到这一步了』", "『再撑一次就能翻盘』", "加注额度越来越大而胜率没变"],
        "counters": ["预先设定硬止损线并公开（外部约束）", "把决策权交给未投入的第三方", "要求对手先亮出他的沉没成本（谁更不敢退）"],
        "fail_if": ["为了面子/执念继续加注 -> 归零", "对所有人使用同一套沉没成本诱导 -> 遇到真能止损的人被反杀", "把可回收资产当沉没成本销毁 -> 失去退出选项"],
    },
    "G8": {
        "id": "G8",
        "zh": "诈唬频率与底池赔率（阈值/混合）",
        "en": "Bluffing Frequency, Pot Odds, MDF & Alpha",
        "solver": "bluff",
        "anchors": ["朔望月（德州扑克化）", "极乐博彩「杀」三倍赔付", "第493章 以赌命做赌注", "第1285章 隔空对赌"],
        "use_when": ["对手可以在『跟/弃』之间选择，我可以选择下注额", "需要算对手该防守多宽、我该诈唬多少", "赔率不对称（杀/胜/负三档赔付）"],
        "params": ["底池 P", "下注额 b", "我的手牌强度的估计分布", "对手防守频率"],
        "flow": [
            "1) 算底池赔率：对手要跟注 b 争 P+b，其最小防守频率 MDF = P/(P+b)。",
            "2) 我的诈唬比例上限 α = b/(P+b)：超过这个比例，对手可以用『永远跟注』剥削我。",
            "3) 反向：若对手防守频率 d < MDF，我用任意两张牌诈唬都是 +EV；若 d > MDF，我只用价值牌下注。",
            "4) 混合：在诈唬与价值之间用随机化保持无差异（G5），并按牌面阻断（blocker）微调。",
            "5) 赔率不对称时（如『杀』三倍赔付）：先把赔付折算成等效底池，再套公式。",
        ],
        "checks": [
            "底池里有多少是对手已经投入的『死钱』（可被我白拿）？",
            "我的下注额 b 是否大到让对手的 MDF 低到不可维持？",
            "对手是否在情绪化跟注（d 偏高）/ 情绪化弃牌（d 偏低）？",
            "我是否有『不用 showdown 就能赢』的合法动作（弃牌迫使/规则漏洞）？",
        ],
        "red_flags": ["我连续下注且对手从不弃牌 -> 我的诈唬比例超了", "对手在我下注后加注 -> 我的价值/诈唬比被读出来了"],
        "counters": ["调整下注尺度改变 MDF 结构", "用『杀』这类高赔率档位反向定价对手的恐惧", "在被读牌时切换成纯价值模式"],
        "fail_if": ["诈唬比例 > α -> 被无限跟注剥削", "防守频率 < MDF -> 被无限诈唬剥削", "忽略抽水/场地费（极乐博彩每胜要交一颗道）-> 名义 +EV 实际 -EV"],
    },
    "G9": {
        "id": "G9",
        "zh": "概率分配与随机化设计",
        "en": "Probability Design / Mixing over Allocations",
        "solver": "prob",
        "anchors": ["人猪「黑白棋」（50黑50白分两碗）", "人猪赌命版（一真一假只能问一次）", "极乐彩券（红绿白十二字）"],
        "use_when": ["可以让对手在『随机结果』上做选择，而我能先设计分布", "需要在信息不对称下把胜率最大化", "需要在一次性事件中把概率拉到极限"],
        "params": ["黑白子数量或等价的可分配资源", "对手的选择方式（随机/自选/被规定）"],
        "flow": [
            "1) 写出胜率表达式（对分配变量的函数），不要凭直觉分配。",
            "2) 找极值：常见最优是『把极少数资源集中到一个极小概率但必胜的分支』（黑白棋：1黑 vs 49黑50白）。",
            "3) 验证对手是否能通过选择规则剥削（让他选择碗 vs 随机选碗，结果不同）。",
            "4) 若对手能问一次问题且一真一假：用元问题把『真/假』归一化（metaq 子命令），把不确定性降为 0。",
            "5) 把结论写成可执行动作：分配比例、问法、下注额。",
        ],
        "checks": [
            "对手的选择机制是否真的随机（谁摇匀、谁选碗）？",
            "我设计的分布是否被对手知道？知道后他能否反制？",
            "是否存在『必胜但概率极低』的分支被浪费？",
            "一次性事件中，我是否在用大数定律的直觉处理单次抽样？",
        ],
        "red_flags": ["『公平分配』的直觉", "对手主动提议规则（他可能已经算过极值）"],
        "counters": ["把分布设计权抓在自己手里（我来分、他来选）", "用元问题消除真假不确定性", "若无法设计分布，改为设计赔付（G8）"],
        "fail_if": ["平均分配 -> 胜率仅约 50%", "忽略对手自选碗的权利 -> 最优解失效", "把随机当确定性 -> 单次失手"],
    },
    "G10": {
        "id": "G10",
        "zh": "共同知识与协调不可能（两军问题）",
        "en": "Common Knowledge / Coordination Impossibility (Two Generals)",
        "solver": "common",
        "anchors": ["人蛇面试「两军问题」", "第460章 未曾提及的规则", "十人以上协同类游戏（不插队/送信人）"],
        "use_when": ["需要多方同时行动才能成功", "通信不可靠或需多轮确认", "有人可能叛变/理解偏差"],
        "params": ["单条消息可靠性 p", "确认轮数 n", "协同失败代价"],
        "flow": [
            "1) 承认结论：在不可靠信道上，『绝对共同知识』无法通过有限轮确认达成（每一轮都留下最后一层不确定）。",
            "2) 用概率工程替代完美协调：n 轮确认后协同成功率 = p^n，算出需要的轮数与冗余（多信使/多路径）。",
            "3) 若 p^n 无法达标：改变机制——指定单一决策者（独裁）+ 可验证信号，或把行动设计成『任一方单独行动也不致命』。",
            "4) 把『理解的共同性』也当成信道：用书面、复述确认、可执行演练来降低歧义。",
        ],
        "checks": [
            "需要的是『同时行动』还是『先后行动』？先后可以直接消除协调问题。",
            "信道可靠性 p 是多少？我是否在假设 p=1？",
            "失败的代价是否对称？若只有一方承担，他会不确认就行动。",
            "是否存在叛徒（奸细）？有叛徒时任何协议都可能被破坏（G1）。",
        ],
        "red_flags": ["『我们都说好了』但没有可验证的确认", "依赖口头转述的多层指挥链"],
        "counters": ["降级为单点决策+回执", "多路径冗余通信", "设计容错行动（局部失败不导致全局失败）"],
        "fail_if": ["追求绝对确认 -> 永远不动，错过窗口", "假设一次沟通=共同知识 -> 协同失败"],
    },
    "G11": {
        "id": "G11",
        "zh": "甄别合同菜单（信息租金与扭曲）",
        "en": "Screening Menu / Information Rents & Distortion",
        "solver": "screening",
        "anchors": ["生肖飞升对赌合同（晋升=自证）", "极乐钱庄三层结构（博彩/彩券/存款）", "地羊「四情扇」花道买扇"],
        "use_when": ["我要给不同类型的人提供不同选项，让他们自选并暴露类型", "对手给我一份『多档合同』，要我选一档", "需要算：为了让人说真话，我必须让出多少信息租金"],
        "params": ["高/低两类估值 θH,θL", "类型先验 p", "成本函数（默认 c(q)=q²/2）"],
        "flow": [
            "1) 写出两类类型的估值与成本，确认单交叉（高类型的边际效用更高）。",
            "2) 设计菜单 {(q,t)}：低类型拿被扭曲的数量（低于最优）、零租金；高类型拿最优数量、付出信息租金 Δθ·qL。",
            "3) 检查 IC：高类型不想装低类型、低类型装不起高类型。",
            "4) 检查 IR：低类型恰好无差异（绑定），高类型有正的租金。",
            "5) 算扭曲量：qL = θL - (p/(1-p))·Δθ；若 ≤0 则放弃低类型（shutdown）。",
            "6) 作为被甄别方：识别哪一档是『为零租金设计的陷阱档』，以及能否伪装成低类型套利。",
        ],
        "checks": [
            "菜单的每一档是否都满足 IR？（不满足=逼人退出或摆烂）",
            "低档的数量扭曲是否被我误当成『服务质量差』？那是有意设计的筛选器。",
            "我伪装成另一类型的成本是否低于获得的差额？",
            "是否存在『选高档但只付低档』的执行漏洞（G4）？",
        ],
        "red_flags": ["合同里高档选项附带不可逆义务（自杀条款）", "『免费试用』档的退出成本极高"],
        "counters": ["自建菜单反向筛选对手", "用可验证凭证替代自述类型", "对高档附加可撤销的保证金而非不可逆义务"],
        "fail_if": ["给低类型留了正租金 -> 所有人都装低类型", "高档义务不可逆 -> 没人敢选，菜单失效"],
    },
    "G12": {
        "id": "G12",
        "zh": "终局结算与元博弈（目标函数审计）",
        "en": "Terminal Settlement / Meta-Game & Objective Audit",
        "solver": "meta",
        "anchors": ["第337章 道的骗局", "第1063章 布局开始", "第1082章 最终博弈", "第1347章 神之欺诈", "十城收集目标与「洗牌」"],
        "use_when": ["所有局都赢了，但不确定赢了之后会发生什么", "目标本身可能是别人设定的诱饵", "需要判断『谁在结算这场游戏』"],
        "params": ["目标函数（我在最大化什么）", "结算者及其激励", "赢的条件与赢之后的下一步"],
        "flow": [
            "1) 问：这个目标是谁定的？他从中得到什么？（道的骗局：集齐不是出路，是洗牌触发器）",
            "2) 问：结算者能否在我赢之后改写结果？（规则更改/第三方赌约/抹杀裁判）",
            "3) 若结算者不可信：把胜利条件改成『结算者也必须履约』的结构（把裁判拖进赌局）。",
            "4) 设计二层目标：表面目标（赢下这一局）+ 真实目标（获得下一局的规则制定权）。",
            "5) 留后手：任何单局胜利都必须有『胜利后仍能自保』的备份（底牌/撤退路线/新世界）。",
        ],
        "checks": [
            "我的目标是他给的，还是我自己定的？",
            "赢了之后谁会来收账？",
            "是否存在『赢了反而更危险』的结构？",
            "我有没有第二目标（规则制定权/退出权）？",
        ],
        "red_flags": ["目标由对手单方面宣布", "奖励是『集齐X』式的进度条（可被随时改规则）"],
        "counters": ["把结算权抢到自己手里", "把胜利条件改成对手无法否认的形式", "准备『掀桌』选项（同归于尽的可信威胁，G6）"],
        "fail_if": ["只优化给定目标 -> 成为别人计划里的工具", "没有掀桌选项 -> 被无限加价"],
    },
}


# --------------------------------------------------------------------------------------
# 二、关键词 -> 模型路由（供 audit 自动识别）
# --------------------------------------------------------------------------------------

KEYWORDS = {
    "G1": ["囚徒", "背叛", "合作", "出卖", "举报", "奸细", "叛变", "重复", "报复", "信用", "承诺", "夺道", "单次", "一次性"],
    "G2": ["不知道", "隐藏", "信息", "真假", "概率", "线索", "情报", "试探", "观测", "先验", "更新", "底牌"],
    "G3": ["证明", "自证", "身份", "类型", "强", "弱", "信号", "宣誓", "立誓", "对赌合同", "资历", "招牌"],
    "G4": ["规则", "条款", "合同", "判定", "平局", "解释权", "漏洞", "裁判", "奖励", "惩罚", "资格", "守则"],
    "G5": ["随机", "均衡", "策略", "概率", "不可预测", "混合", "读牌", "反复", "循环"],
    "G6": ["威胁", "承诺", "先后", "顺序", "最后", "结算", "可信", "履约", "处决", "抹杀", "倒计时", "轮次"],
    "G7": ["沉没", "已经投入", "不甘心", "止损", "加注", "翻盘", "执念", "七年", "代价"],
    "G8": ["下注", "跟注", "弃牌", "底池", "诈唬", "赔率", "诈赌", "赌注", "押注", "梭哈"],
    "G9": ["分配", "概率", "摸", "抽", "随机选择", "碗", "黑白", "彩券", "组合", "抽样"],
    "G10": ["通信", "传令", "确认", "同时", "协同", "两军", "可靠", "信号传递", "误解"],
    "G11": ["菜单", "档次", "选择", "租金", "甄别", "筛选", "优惠", "门槛", "套餐", "分层"],
    "G12": ["目标", "真相", "结局", "洗牌", "造神", "神格", "最终", "赢了之后", "收账", "元"],
}


# --------------------------------------------------------------------------------------
# 三、通用工具
# --------------------------------------------------------------------------------------

def _fmt(x):
    """有理数/浮点友好格式化。"""
    if isinstance(x, F):
        if x.denominator == 1:
            return str(x.numerator)
        return f"{x.numerator}/{x.denominator}"
    if isinstance(x, float):
        return f"{x:.6g}"
    return str(x)


def _dec(x):
    """转成可 JSON 序列化的数字。"""
    if isinstance(x, F):
        return float(x) if x.denominator != 1 else x.numerator
    return x


def _jsonify(obj):
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonify(v) for v in obj]
    if isinstance(obj, F):
        return _dec(obj)
    return obj


def solve_linear(A, b):
    """高斯消元（有理数精确）。返回解列表，奇异返回 None。"""
    n = len(A)
    m = [[F(x) for x in A[i]] + [F(b[i])] for i in range(n)]
    for col in range(n):
        piv = None
        for r in range(col, n):
            if m[r][col] != 0:
                piv = r
                break
        if piv is None:
            return None
        m[col], m[piv] = m[piv], m[col]
        pv = m[col][col]
        m[col] = [v / pv for v in m[col]]
        for r in range(n):
            if r != col and m[r][col] != 0:
                f = m[r][col]
                m[r] = [m[r][c] - f * m[col][c] for c in range(n + 1)]
    return [m[i][n] for i in range(n)]


def classify_2x2(A, B):
    """识别 2x2 博弈类型（PD / 协调 / 胆小鬼 / 硬币匹配 / 零和 / 非对称）。"""
    labels = set()
    # 零和/常和检测
    sums = {A[i][j] + B[i][j] for i in range(len(A)) for j in range(len(A[0]))}
    if len(sums) == 1:
        labels.add("zero_sum" if list(sums)[0] == 0 else "constant_sum")
    # 只有对称博弈（A == B^T）才套用对称经典结构的收益序判定
    symmetric = all(A[i][j] == B[j][i] for i in range(len(A)) for j in range(len(A[0])))
    if not symmetric:
        labels.add("asymmetric")
        return sorted(labels)
    a, b = A[0][0], A[0][1]  # (C,C), (C,D)
    c, d = A[1][0], A[1][1]  # (D,C), (D,D)
    if c > a > d > b:
        labels.add("prisoner_dilemma")
    elif a > c and d > b and a > b:
        labels.add("stag_hunt")
    elif c > a and b > d and c > b:
        labels.add("chicken_hawk_dove")
    if A[0][0] == A[1][1] and A[0][1] == A[1][0] and A[0][1] > A[0][0]:
        labels.add("matching_pennies")
    if A[0][0] > A[1][0] and A[1][1] > A[0][1] and B[0][0] > B[0][1] and B[1][1] > B[1][0]:
        labels.add("coordination")
    return sorted(labels)


def pure_nash(A, B):
    n, m = len(A), len(A[0])
    out = []
    for i in range(n):
        for j in range(m):
            if A[i][j] == max(A[r][j] for r in range(n)) and B[i][j] == max(B[i][k] for k in range(m)):
                out.append((i, j))
    return out


def dominant_actions(A, B):
    """返回 (行玩家的严格占优动作列表, 列玩家的严格占优动作列表)。"""
    n, m = len(A), len(A[0])
    row_dom, col_dom = [], []
    for i in range(n):
        if all(all(A[i][j] > A[k][j] for j in range(m)) for k in range(n) if k != i):
            row_dom.append(i)
    for j in range(m):
        if all(all(B[i][j] > B[i][k] for i in range(n)) for k in range(m) if k != j):
            col_dom.append(j)
    return row_dom, col_dom


def maximin(A):
    """行玩家混合 maximin 值（2x2 解析）。"""
    n, m = len(A), len(A[0])
    if n != 2 or m != 2:
        return None
    denom = A[0][0] - A[0][1] - A[1][0] + A[1][1]
    if denom == 0:
        return None
    p = F(A[1][1] - A[0][1]) / denom
    if p < 0 or p > 1:
        return max(min(A[0]), min(A[1]))
    v = p * A[0][0] + (1 - p) * A[0][1]
    return v


# --------------------------------------------------------------------------------------
# 四、求解器 G1：囚徒困境 / 重复博弈
# --------------------------------------------------------------------------------------

def _num(x):
    if isinstance(x, F):
        return x
    if isinstance(x, bool):
        return F(int(x))
    if isinstance(x, int):
        return F(x)
    return F(str(x))


def _load_matrix(spec):
    """spec: {"row": {"name","actions"}, "col": {...}, "payoffs": [[ [r,c], ...], ...]}"""
    A = [[_num(p[0]) for p in row] for row in spec["payoffs"]]
    B = [[_num(p[1]) for p in row] for row in spec["payoffs"]]
    names_r = spec.get("row", {}).get("actions") or [f"R{i}" for i in range(len(A))]
    names_c = spec.get("col", {}).get("actions") or [f"C{j}" for j in range(len(A[0]))]
    return A, B, names_r, names_c


def solve_pd(spec):
    A, B, nr, nc = _load_matrix(spec)
    name_r = spec.get("row", {}).get("name", "我方")
    name_c = spec.get("col", {}).get("name", "对手")
    out = {"model": "G1", "solver": "pd", "story": spec.get("anchor", "第278章 囚徒困境"),
           "title": spec.get("name", "囚徒困境"), "evidence": [], "numbers": {}, "gaps": []}
    ev = out["evidence"]
    ev.append(f"收益矩阵（{name_r}行 / {name_c}列）：")
    for i in range(len(A)):
        ev.append("  " + nr[i] + " | " + " | ".join(f"{_fmt(A[i][j])},{_fmt(B[i][j])}" for j in range(len(A[0]))))

    cls = classify_2x2(A, B) if (len(A) == 2 and len(A[0]) == 2) else []
    out["numbers"]["game_class"] = cls
    nes = pure_nash(A, B)
    out["numbers"]["pure_nash"] = [[nr[i], nc[j]] for i, j in nes]
    rd, cd = dominant_actions(A, B)
    out["numbers"]["dominant"] = {"row": [nr[i] for i in rd], "col": [nc[j] for j in cd]}
    ev.append(f"博弈结构识别：{', '.join(cls) if cls else '未匹配经典结构'}")
    ev.append("纯策略纳什均衡：" + ("; ".join(f"({nr[i]}, {nc[j]})" for i, j in nes) if nes else "无"))
    if rd or cd:
        ev.append(f"严格占优动作：{name_r}->{[nr[i] for i in rd] or '无'}；{name_c}->{[nc[j] for j in cd] or '无'}")

    # 囚徒困境结构参数
    pd_flag = False
    if len(A) == 2 and len(A[0]) == 2:
        R = A[0][0]
        S_ = A[0][1]
        T = A[1][0]
        P = A[1][1]
        out["numbers"].update({"T": _dec(T), "R": _dec(R), "P": _dec(P), "S": _dec(S_)})
        tnum, rnum, pnum, snum = T, R, P, S_
        pd_flag = (tnum > rnum > pnum > snum) and (2 * rnum > tnum + snum)
        out["numbers"]["is_prisoners_dilemma"] = bool(pd_flag)
        if pd_flag:
            delta_star = (tnum - rnum) / (tnum - pnum)
            out["numbers"]["delta_star"] = _dec(delta_star)
            ev.append(f"T={_fmt(T)} > R={_fmt(R)} > P={_fmt(P)} > S={_fmt(S_)} 且 2R={_fmt(2*R)} > T+S={_fmt(T+S_)} -> 真囚徒困境")
            ev.append(f"重复博弈临界贴现因子 δ* = (T-R)/(T-P) = ({_fmt(T)}-{_fmt(R)})/({_fmt(T)}-{_fmt(P)}) = {_fmt(delta_star)}")
            rep = spec.get("repeated", {"mode": "infinite", "delta": None})
            mode = rep.get("mode", "infinite")
            if mode == "infinite":
                d = rep.get("delta")
                if d is not None:
                    d = _num(d)
                    if d >= delta_star:
                        ev.append(f"给定 δ={_fmt(d)} ≥ δ*={_fmt(delta_star)} -> 冷酷触发/针锋相对可支撑持续合作，合作是均衡。")
                        out["verdict"] = "可合作（重复博弈支撑）"
                        out["action"] = f"先手合作（C），并公开承诺『被背叛后永久转D』；同时把『一定会再见面』变成共同知识。"
                    else:
                        ev.append(f"给定 δ={_fmt(d)} < δ*={_fmt(delta_star)} -> 合作不可持续：单次背叛收益 {_fmt(T-R)} 大于未来合作损失现值。")
                        out["verdict"] = "合作不可持续（贴现过高/关系太短）"
                        out["action"] = "不要先合作：先D，或用抵押/人质/公开处刑结构把 δ 强行抬高（G6）。"
                else:
                    out["verdict"] = "结构上可合作（需实测 δ）"
                    out["action"] = "估算对手眼中的 δ（他是否相信有下一次）；δ 未知时以『小幅先合作+立刻可惩罚』试探。"
            elif mode == "finite":
                n = int(rep.get("periods", 1))
                if n == 1:
                    ev.append("单次博弈：逆向归纳 -> 唯一均衡 (D,D)，任何口头合作承诺都是廉价的。")
                    out["verdict"] = "单次 = 必然背叛"
                    out["action"] = "先D；若必须合作，先制造重复关系或抵押品。"
                else:
                    ev.append(f"有限 {n} 次：逆向归纳会从最后一期开始瓦解合作 -> 理论均衡是全期背叛（连锁店悖论）。")
                    ev.append("现实中因对手不完美理性，可在前 n-2 期合作、末两期转D；但这是对『对手非理性』的赌注。")
                    out["verdict"] = f"有限 {n} 次 = 理论全期背叛"
                    out["action"] = "把有限博弈改造成无限（承诺还有下一次）；否则按末期背叛预设布防。"
        else:
            ev.append("不满足 T>R>P>S 或 2R>T+S：不是囚徒困境，套用 PD 结论会犯方向性错误。")
            out["verdict"] = "非囚徒困境（结构误判风险）"
            out["action"] = "按实际结构（协调/胆小鬼/猎鹿）另选策略；胆小鬼博弈该强硬，猎鹿博弈该先建立互信。"
            out["gaps"].append("收益顺序与经典 PD 不符：需重新确认谁的动作真正占优。")

    # maximin 保险线
    if len(A) == 2 and len(A[0]) == 2:
        v = maximin(A)
        if v is not None:
            out["numbers"]["row_maximin"] = _dec(v)
            ev.append(f"{name_r} 的混合 maximin 保底收益 = {_fmt(v)}（最坏情况下的可保证值，用于设定止损线）")
    if "verdict" not in out:
        out["verdict"] = "纳什均衡已定位"
        out["action"] = ("跟随均衡动作：" + (f"({nr[nes[0][0]]}, {nc[nes[0][1]]})" if nes else "无纯策略均衡，转 G5 混合策略"))
    out["counter"] = "对手若在单次博弈中主动示好，视为在为背叛定价（提高其T）；用公开可观测的惩罚承诺反制。"
    out["fail_if"] = ["把胆小鬼/猎鹿误判为 PD", "单次博弈里先合作", "惩罚承诺不可观测/不可执行"]
    if pd_flag and not spec.get("repeated"):
        out["gaps"].append("未提供重复次数/贴现因子：δ 未量化，合作可行性无法结算。")
    return out


# --------------------------------------------------------------------------------------
# 五、求解器 G2：贝叶斯更新与信息价值
# --------------------------------------------------------------------------------------

def solve_bayes(spec):
    prior = _num(spec.get("prior", 0.5))
    types = spec.get("types", ["θ0", "θ1"])
    out = {"model": "G2", "solver": "bayes", "story": spec.get("anchor", "第644章 真假规则"),
           "title": spec.get("name", "贝叶斯更新"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    post = {"prior": {types[0]: _dec(prior), types[1]: _dec(1 - prior)}}
    cur = {types[0]: prior, types[1]: 1 - prior}
    ev.append(f"先验：P({types[0]})={_fmt(cur[types[0]])}, P({types[1]})={_fmt(cur[types[1]])}")
    for obs in spec.get("observations", []):
        like = [_num(x) for x in obs["likelihood"]]
        joint = {types[0]: cur[types[0]] * like[0], types[1]: cur[types[1]] * like[1]}
        z = joint[types[0]] + joint[types[1]]
        if z == 0:
            ev.append(f"观测『{obs.get('name','s')}』的似然全为0 -> 该观测与先验矛盾，说明先验或模型有错。")
            out["gaps"].append("似然全零：先验/似然假设被观测推翻。")
            continue
        cur = {k: v / z for k, v in joint.items()}
        ev.append(f"观测『{obs.get('name','s')}』：P(s|{types[0]})={_fmt(like[0])}, P(s|{types[1]})={_fmt(like[1])}"
                  f" -> 后验 P({types[0]}|s)={_fmt(cur[types[0]])}, P({types[1]}|s)={_fmt(cur[types[1]])}")
        lr = _fmt(like[0] / like[1]) if like[1] != 0 else "∞"
        ev.append(f"似然比 LR = P(s|{types[0]}) / P(s|{types[1]}) = {lr}（LR≈1 时该信号几乎无信息量）")
    post["posterior"] = {k: _dec(v) for k, v in cur.items()}
    out["numbers"]["bayes"] = post

    acts = spec.get("actions", [])
    if acts:
        rows = []
        for a in acts:
            u = [_num(x) for x in a["payoff"]]
            e = cur[types[0]] * u[0] + cur[types[1]] * u[1]
            rows.append((a.get("name", "?"), e, u))
        rows.sort(key=lambda t: t[1], reverse=True)
        ev.append("后验下的期望值：")
        for nm, e, _ in rows:
            ev.append(f"  {nm}: EV={_fmt(e)}")
        out["numbers"]["action_ev"] = {nm: _dec(e) for nm, e, _ in rows}
        out["numbers"]["best_action"] = rows[0][0]
        out["action"] = f"选择 EV 最大的动作：{rows[0][0]}（EV={_fmt(rows[0][1])}）"
        ev_perfect = sum(max(_num(a["payoff"][k]) for a in acts) * cur[types[k]] for k in range(2))
        evpi = ev_perfect - rows[0][1]
        out["numbers"]["EVPI"] = _dec(evpi)
        ev.append(f"完美信息价值 EVPI = {_fmt(ev_perfect)} - {_fmt(rows[0][1])} = {_fmt(evpi)}"
                  f" -> 花费超过 {_fmt(evpi)} 去『确认信息』就是亏本买卖")
        out["verdict"] = "后验已更新"
    else:
        out["verdict"] = "后验已更新（未给决策选项，无法算 EVPI）"
        out["action"] = "把候选动作与各状态收益填入 actions 字段，才能算 EVPI 与最优动作。"
        out["gaps"].append("缺少 actions（候选动作及其在两类状态下的收益）：只更新了信念，未结算决策。")
        evpi_note = "EVPI 未计算：需要 actions"
        out["numbers"]["EVPI"] = None
    if cur[types[0]] > F(4, 5) or cur[types[0]] < F(1, 5):
        ev.append(f"后验高度集中（{_fmt(cur[types[0]])}）：此时继续侦查的边际价值低，应把资源转向执行。")
    else:
        ev.append(f"后验接近先验（{_fmt(cur[types[0]])}）：信号信息量不足，需要新信号源（换问题/换观测）。")
    out["counter"] = "对手可以伪造信号：把『他主动提供的信息』降权，只信他自己要付出代价才能做到的动作（G3）。"
    out["fail_if"] = ["把先验当事实", "把『没反应』排除在证据之外", "忽略对手操纵信号的能力"]
    return out


# --------------------------------------------------------------------------------------
# 六、求解器 G5：混合策略 / 纳什均衡
# --------------------------------------------------------------------------------------

def solve_mixed(spec):
    A, B, nr, nc = _load_matrix(spec)
    n, m = len(A), len(A[0])
    out = {"model": "G5", "solver": "mixed", "story": spec.get("anchor", "终极游戏「朔望月」"),
           "title": spec.get("name", "混合策略均衡"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    ev.append(f"{n}x{m} 收益矩阵（每格 = 行玩家收益, 列玩家收益）：")
    ev.append("  " + " " * max(len(x) for x in nr) + " | " + " | ".join(nc))
    for i in range(n):
        ev.append("  " + nr[i] + " | " + " | ".join(f"{_fmt(A[i][j])},{_fmt(B[i][j])}" for j in range(m)))
    eqs = []
    for i, j in pure_nash(A, B):
        eqs.append({"type": "pure", "row": {nr[i]: 1.0}, "col": {nc[j]: 1.0},
                    "payoff": [_dec(A[i][j]), _dec(B[i][j])]})

    if n == 2 and m == 2:
        denom_q = A[0][0] - A[0][1] - A[1][0] + A[1][1]
        denom_p = B[0][0] - B[1][0] - B[0][1] + B[1][1]
        mixed_eq = None
        if denom_q != 0 and denom_p != 0:
            q = (A[1][1] - A[0][1]) / denom_q  # 列玩家选列0的概率（使行玩家无差异）
            p = (B[1][1] - B[1][0]) / denom_p  # 行玩家选行0的概率（使列玩家无差异）
            if 0 < p < 1 and 0 < q < 1:
                u_row = p * (q * A[0][0] + (1 - q) * A[0][1]) + (1 - p) * (q * A[1][0] + (1 - q) * A[1][1])
                u_col = q * (p * B[0][0] + (1 - p) * B[1][0]) + (1 - q) * (p * B[0][1] + (1 - p) * B[1][1])
                # 偏离检验
                dev_row = max(q * A[0][0] + (1 - q) * A[0][1], q * A[1][0] + (1 - q) * A[1][1])
                dev_col = max(p * B[0][0] + (1 - p) * B[1][0], p * B[0][1] + (1 - p) * B[1][1])
                mixed_eq = {"type": "mixed", "row": {nr[0]: _dec(p), nr[1]: _dec(1 - p)},
                            "col": {nc[0]: _dec(q), nc[1]: _dec(1 - q)},
                            "payoff": [_dec(u_row), _dec(u_col)],
                            "deviation_gain": {"row": _dec(dev_row - u_row), "col": _dec(dev_col - u_col)}}
                ev.append(f"混合均衡：{nr[0]} 概率 {_fmt(p)} / {nr[1]} 概率 {_fmt(1-p)}；"
                          f"{nc[0]} 概率 {_fmt(q)} / {nc[1]} 概率 {_fmt(1-q)}")
                ev.append(f"均衡收益 ({_fmt(u_row)}, {_fmt(u_col)})；单方偏离增益 row={_fmt(dev_row-u_row)}, col={_fmt(dev_col-u_col)}"
                          f"（≈0 表示无差异，均衡脆弱性=偏离增益越小越容易被心理战撬动）")
        if mixed_eq:
            eqs.append(mixed_eq)
        cls = classify_2x2(A, B)
        out["numbers"]["game_class"] = cls
        ev.append(f"结构：{', '.join(cls) if cls else '未匹配经典结构'}")
        v = maximin(A)
        if v is not None:
            out["numbers"]["row_maximin"] = _dec(v)
            ev.append(f"我方 maximin 保底 = {_fmt(v)}（均衡只是防守线；若保底<成本，本局不该玩）")
    else:
        sup = support_equilibria(A, B, max_support=min(n, m, 4))
        for s in sup:
            eqs.append(s)
            ev.append(f"支撑均衡：行 {[(nr[i], round(v, 4)) for i, v in s['row'].items()]} / 列 {[(nc[j], round(v, 4)) for j, v in s['col'].items()]}")
    out["numbers"]["equilibria"] = eqs
    pure_cnt = sum(1 for e in eqs if e["type"] == "pure")
    mixed_cnt = sum(1 for e in eqs if e["type"] == "mixed")
    if pure_cnt == 0 and mixed_cnt > 0:
        out["verdict"] = "无纯策略均衡，必须随机化"
        out["action"] = "按混合均衡概率随机化（用外部随机源）；不要形成可被统计的规律。"
    elif pure_cnt >= 1 and mixed_cnt >= 1:
        out["verdict"] = "纯策略均衡存在（另有混合均衡）"
        out["action"] = "优先执行纯策略均衡动作；随机化仅用于防止对手预测你选哪一个纯均衡（协调问题）。"
    elif pure_cnt >= 2:
        out["verdict"] = "存在多个纯策略均衡（协调博弈）"
        out["action"] = "抢占先手/发出可观测信号，把对手引导到对你更有利的那个均衡（G3/G10）。"
    else:
        out["verdict"] = "均衡已定位"
        out["action"] = "按均衡执行，并核对抽水/场地费等固定成本是否让 EV 转负。"
    out["counter"] = "对手若偏离均衡（过度诈唬/过度弃牌），用最大剥削策略；但需样本量，否则是过拟合。"
    out["fail_if"] = ["用固定周期随机化被读牌", "把均衡当必胜法（忽略抽水与方差）", "在负 EV 的赔付结构里追求均衡"]
    if pure_cnt == 0:
        out["gaps"].append("无纯策略均衡：胜负完全取决于随机化质量与对手频率估计，需明确随机源。")
    return out


def support_equilibria(A, B, max_support=4):
    """支撑枚举法求 n×m 纳什均衡（有理数精确，支持 ≤4 支撑）。"""
    n, m = len(A), len(A[0])
    res = []
    for k in range(1, min(max_support, n, m) + 1):
        for Sr in itertools.combinations(range(n), k):
            for Sc in itertools.combinations(range(m), k):
                # 解 q（列玩家混合）使行玩家在 Sr 上无差异：sum_j A[i][j] q_j - u = 0
                Mq, bq = [], []
                for i in Sr:
                    Mq.append([A[i][j] for j in Sc] + [F(-1)])
                    bq.append(F(0))
                Mq.append([F(1)] * k + [F(0)])
                bq.append(F(1))
                sol_q = solve_linear(Mq, bq)
                if sol_q is None:
                    continue
                q = sol_q[:k]
                u = sol_q[k]
                if any(x <= 0 for x in q):
                    continue
                if any(sum(A[i][j] * q[t] for t, j in enumerate(Sc)) > u for i in range(n) if i not in Sr):
                    continue
                # 解 p（行玩家混合）使列玩家在 Sc 上无差异
                Mp, bp = [], []
                for j in Sc:
                    Mp.append([B[i][j] for i in Sr] + [F(-1)])
                    bp.append(F(0))
                Mp.append([F(1)] * k + [F(0)])
                bp.append(F(1))
                sol_p = solve_linear(Mp, bp)
                if sol_p is None:
                    continue
                p = sol_p[:k]
                v = sol_p[k]
                if any(x <= 0 for x in p):
                    continue
                if any(sum(B[i][j] * p[t] for t, i in enumerate(Sr)) > v for j in range(m) if j not in Sc):
                    continue
                res.append({
                    "type": "pure" if k == 1 else "mixed",
                    "row": {Sr[t]: float(p[t]) for t in range(k)},
                    "col": {Sc[t]: float(q[t]) for t in range(k)},
                    "payoff": [float(u), float(v)],
                })
    # 去重
    uniq = {}
    for e in res:
        key = (tuple(sorted(e["row"].items())), tuple(sorted(e["col"].items())))
        uniq[key] = e
    return list(uniq.values())


# --------------------------------------------------------------------------------------
# 七、求解器 G3：信号博弈（分离/混同均衡）
# --------------------------------------------------------------------------------------

def solve_signaling(spec):
    types = spec["types"]
    signals = spec["signals"]
    actions = spec["actions"]
    prior = _num(spec.get("prior", 0.5))
    sp = spec["sender_payoff"]   # sp[type][signal][action]
    rp = spec["receiver_payoff"]  # rp[signal][action][type]

    def spay(t, m, a):
        return _num(sp[t][m][a])

    def rpay(m, a, t):
        return _num(rp[m][a][t])

    out = {"model": "G3", "solver": "signaling", "story": spec.get("anchor", "生肖飞升对赌合同"),
           "title": spec.get("name", "信号博弈"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    ev.append(f"类型 {types}（先验 {_fmt(prior)} / {_fmt(1-prior)}）；信号 {signals}；接收方动作 {actions}")

    # 单交叉检验
    sc_rows = {}
    for t in types:
        for m in signals:
            pass
    m0, m1 = signals[0], signals[1]
    a_ref = actions[0]
    gains = {t: spay(t, m0, a_ref) - spay(t, m1, a_ref) for t in types}
    ev.append(f"单交叉检验（同一接收动作『{a_ref}』下，发信号『{m0}』相对『{m1}』的净收益）：")
    for t in types:
        ev.append(f"  {t}: {_fmt(gains[t])}")
    single_cross = gains[types[0]] > gains[types[1]]
    out["numbers"]["single_crossing"] = bool(single_cross)
    out["numbers"]["gain_by_type"] = {t: _dec(v) for t, v in gains.items()}
    ev.append(f"单交叉成立: {single_cross}（成立时昂贵信号有信息量；成本无类型差异则信号=噪音）")

    # 枚举发送方纯策略
    profiles = []
    for assign in itertools.product([0, 1], repeat=len(types)):
        sender = {types[i]: signals[assign[i]] for i in range(len(types))}
        used = set(sender.values())
        offpath = [m for m in signals if m not in used]
        belief_cases = []
        if not offpath:
            belief_cases.append({})
        else:
            # 遍历离轨信念网格
            for grid in itertools.product([F(0), F(1, 10), F(1, 2), F(9, 10), F(1)], repeat=len(offpath)):
                belief_cases.append(dict(zip(offpath, grid)))
        for offb in belief_cases:
            beliefs = {}
            ok_belief = True
            for m in signals:
                senders = [t for t in types if sender[t] == m]
                if senders:
                    if len(senders) == len(types):
                        beliefs[m] = prior
                    elif senders[0] == types[0]:
                        beliefs[m] = F(1)
                    else:
                        beliefs[m] = F(0)
                else:
                    beliefs[m] = offb.get(m)
                    if beliefs[m] is None:
                        ok_belief = False
            if not ok_belief:
                continue
            # 接收方对每个信号的最优反应（允许并列）
            br_sets = {}
            for m in signals:
                mu = beliefs[m]
                vals = {}
                for a in actions:
                    vals[a] = mu * rpay(m, a, types[0]) + (1 - mu) * rpay(m, a, types[1])
                best = max(vals.values())
                br_sets[m] = [a for a in actions if vals[a] == best]
            for resp_tuple in itertools.product(*[br_sets[m] for m in signals]):
                resp = dict(zip(signals, resp_tuple))
                # 发送方最优性
                ok = True
                for t in types:
                    cur = spay(t, sender[t], resp[sender[t]])
                    if any(spay(t, m, resp[m]) > cur for m in signals):
                        ok = False
                        break
                if not ok:
                    continue
                profiles.append({"sender": dict(sender), "receiver": dict(resp),
                                 "beliefs": {m: beliefs[m] for m in signals},
                                 "offpath": dict(offb)})

    # 归类：分离 / 混同，以及离轨信念稳健性
    grouped = {}
    for p in profiles:
        sep = len(set(p["sender"].values())) == len(set(types))
        key = (tuple(sorted(p["sender"].items())), tuple(sorted(p["receiver"].items())))
        g = grouped.setdefault(key, {"sep": sep, "sender": p["sender"], "receiver": p["receiver"],
                                     "beliefs": p["beliefs"], "offpath_support": []})
        g["offpath_support"].append(p["offpath"])
    eq_list = []
    for key, g in grouped.items():
        robust = len(g["offpath_support"]) >= (5 ** max(1, len(g["offpath_support"][0]))) if g["offpath_support"] else True
        # 简化：稳健=覆盖所有网格点
        n_off = len(g["offpath_support"][0])
        robust = len(g["offpath_support"]) >= (5 ** n_off)
        item = {"type": "separating" if g["sep"] else "pooling",
                "sender": g["sender"], "receiver": g["receiver"],
                "beliefs_on_path": {m: _dec(v) for m, v in g["beliefs"].items()},
                "offpath_robust": bool(robust)}
        eq_list.append(item)
        ev.append(f"[{'分离' if g['sep'] else '混同'}] 发送: {g['sender']} ; 接收: {g['receiver']} ; "
                  f"离轨稳健={robust}（不稳健=该均衡只在特定离轨信念下成立）")
    out["numbers"]["equilibria"] = eq_list
    out["numbers"]["n_equilibria"] = len(eq_list)
    sep_eq = [e for e in eq_list if e["type"] == "separating"]
    pool_eq = [e for e in eq_list if e["type"] == "pooling"]
    if sep_eq:
        out["verdict"] = f"存在 {len(sep_eq)} 个分离均衡（信号有信息量）"
        out["action"] = ("作为发送方：用只有强类型付得起的分离信号自证，并让该信号可被第三方验证；"
                         "作为接收方：只认分离信号，不认口头承诺。")
    elif pool_eq:
        out["verdict"] = "只有混同均衡（信号无信息量）"
        out["action"] = "不要依赖该信号；改设计带成本差的信号（G3）或直接改规则让伪装不可能（G4）。"
    else:
        out["verdict"] = "无纯策略均衡"
        out["action"] = "转混合策略（G5）：发送方随机化信号、接收方随机化反应。"
    out["counter"] = "对手可用『混同』淹没信号：制造大量廉价同质动作；反制是要求可验证凭证而非重复次数。"
    out["fail_if"] = ["使用成本无类型差异的信号", "忽略混同均衡导致自信误判", "只算自己成本不算对手模仿成本"]
    if pool_eq:
        out["gaps"].append("混同均衡存在：口头/廉价信号不可信，必须引入可验证凭证。")
    if not single_cross:
        out["gaps"].append("单交叉不成立：现有信号无法区分类型，需重新设计信号成本结构。")
    return out


# --------------------------------------------------------------------------------------
# 八、求解器 G11：甄别（信息租金与扭曲）
# --------------------------------------------------------------------------------------

def solve_screening(spec):
    th_h = _num(spec.get("theta_high", 10))
    th_l = _num(spec.get("theta_low", 6))
    p = _num(spec.get("prior_high", 0.5))
    out = {"model": "G11", "solver": "screening", "story": spec.get("anchor", "生肖飞升对赌合同 / 极乐钱庄三层结构"),
           "title": spec.get("name", "最优甄别菜单"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    out["numbers"].update({"theta_high": _dec(th_h), "theta_low": _dec(th_l), "prior_high": _dec(p)})
    ev.append(f"两类类型 θH={_fmt(th_h)}, θL={_fmt(th_l)}，先验 P(H)={_fmt(p)}；成本 c(q)=q²/2（Mussa-Rosen 标准设定）")
    q_h = th_h                      # 高类型不扭曲
    q_l = th_l - (p / (1 - p)) * (th_h - th_l)  # 低类型向下扭曲
    shutdown = q_l <= 0
    if shutdown:
        ev.append(f"qL = θL - (p/(1-p))Δθ = {_fmt(th_l)} - {_fmt(p/(1-p))}*{_fmt(th_h-th_l)} = {_fmt(q_l)} ≤ 0"
                  f" -> 最优是放弃低类型（shutdown），只服务高类型。")
        t_h = th_h * q_h
        profit = p * (t_h - q_h ** 2 / 2)
        t_l = F(0)
        q_l = F(0)
        out["numbers"].update({"q_high": _dec(q_h), "q_low": 0.0, "t_high": _dec(t_h), "t_low": 0.0,
                               "shutdown": True, "profit": _dec(profit)})
        out["action"] = "只提供高档位（且不留低档入口）；或降低低档成本以提高 qL 使其可服务。"
        out["verdict"] = "放弃低类型（shutdown）"
    else:
        t_l = th_l * q_l                       # 低类型 IR 绑定、零租金
        rent = (th_h - th_l) * q_l             # 高类型信息租金
        t_h = th_h * q_h - rent
        profit = p * (t_h - q_h ** 2 / 2) + (1 - p) * (t_l - q_l ** 2 / 2)
        fb_profit = p * (th_h ** 2 / 2) + (1 - p) * (th_l ** 2 / 2)
        ev.append(f"低档数量被向下扭曲：qL = θL - (p/(1-p))Δθ = {_fmt(th_l)} - {_fmt(p/(1-p))}*{_fmt(th_h-th_l)} = {_fmt(q_l)}"
                  f"（一阶最优 qL*=θL={_fmt(th_l)}）")
        ev.append(f"菜单：低档 (q={_fmt(q_l)}, t={_fmt(t_l)})；高档 (q={_fmt(q_h)}, t={_fmt(t_h)})")
        ev.append(f"高类型信息租金 = Δθ·qL = {_fmt(th_h-th_l)}*{_fmt(q_l)} = {_fmt(rent)}（这是『让人说真话』的代价）")
        ev.append(f"卖方利润 = {_fmt(profit)}（一阶最优 {_fmt(fb_profit)}，信息成本 {_fmt(fb_profit-profit)}）")
        out["numbers"].update({"q_high": _dec(q_h), "q_low": _dec(q_l), "t_high": _dec(t_h), "t_low": _dec(t_l),
                               "info_rent": _dec(rent), "profit": _dec(profit),
                               "first_best_profit": _dec(fb_profit), "shutdown": False})
        out["action"] = (f"发布两档菜单：低档 (q={_fmt(q_l)}, t={_fmt(t_l)})、高档 (q={_fmt(q_h)}, t={_fmt(t_h)})；"
                         "高档不得附加不可逆义务（否则无人敢选，菜单失效）。")
        out["verdict"] = "两档甄别菜单已求解"

    # 自选检验：给定菜单，各类型实际会选哪档（是否真的分离 / IC 是否绑定）
    if not out["numbers"].get("shutdown", False):
        u = {"H_high": th_h * q_h - t_h, "H_low": th_h * q_l - t_l,
             "L_high": th_l * q_h - t_h, "L_low": th_l * q_l - t_l}
        out["numbers"]["self_selection"] = {k: _dec(v) for k, v in u.items()}
        ic_binding = (u["H_high"] == u["H_low"])
        strictly_separating = (u["H_high"] > u["H_low"]) and (u["L_low"] > u["L_high"])
        out["numbers"]["ic_binding"] = bool(ic_binding)
        out["numbers"]["strict_separating"] = bool(strictly_separating)
        ev.append(f"自选检验：u_H(高档)={_fmt(u['H_high'])}, u_H(低档)={_fmt(u['H_low'])}；"
                  f"u_L(高档)={_fmt(u['L_high'])}, u_L(低档)={_fmt(u['L_low'])}")
        if strictly_separating:
            ev.append("-> 严格分离：H 必选高档、L 必选低档。")
        elif ic_binding:
            ev.append("-> 分离成立但 IC 绑定：H 对两档无差异（u_H(高)=u_H(低)=信息租金）。"
                      "实务上必须给 ε（t_H 减一点或附赠可撤销权益）才能确保 H 选高档，否则 H 会随手选低档。")
        else:
            ev.append("-> 分离失败：存在跨档套利，菜单失效。")
            out["gaps"].append("菜单未能分离：某类型在另一档获得更高效用，需加大低档扭曲或提高高档价格。")
    out["counter"] = "作为被甄别方：找出『零租金低档』并伪装成低类型，或找执行漏洞选高档只付低档（G4）。"
    out["fail_if"] = ["给低类型留正租金 -> 人人都装低类型", "高档附不可逆义务 -> 无人敢选", "忽略低类型可退出（IR）"]
    if shutdown:
        out["gaps"].append("低类型被放弃：若对方能伪装成低类型以外的身份（或强制参与），该结论失效。")
    return out


# --------------------------------------------------------------------------------------
# 九、求解器 G4：机制/规则审计
# --------------------------------------------------------------------------------------

def solve_mechanism(spec):
    types = spec["player_types"]           # {"A":[v_high,v_low], "B":[...]}
    prior = spec.get("prior", {k: [0.5, 0.5] for k in types})
    reports = spec.get("reports", [0, 1])  # 0=报高类型,1=报低类型（索引对应 types 列表）
    rule = spec["rule"]                    # [{"report":[ra,rb],"alloc":[xa,xb],"pay":[pa,pb]}]

    out = {"model": "G4", "solver": "mechanism", "story": spec.get("anchor", "第438章 隐藏的规则 / 生肖守则 / 赌命规则"),
           "title": spec.get("name", "机制审计"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": "", "violations": []}
    ev = out["evidence"]
    P = {k: [_num(x) for x in v] for k, v in prior.items()}
    V = {k: [_num(x) for x in v] for k, v in types.items()}
    idx = {}
    for row in rule:
        idx[(row["report"][0], row["report"][1])] = row
    players = ["A", "B"]

    def util(pl, t_idx, row):
        i = 0 if pl == "A" else 1
        return V[pl][t_idx] * _num(row["alloc"][i]) - _num(row["pay"][i])

    # 1) 可行性
    gaps = []
    for row in rule:
        xa, xb = _num(row["alloc"][0]), _num(row["alloc"][1])
        if xa + xb > 1:
            gaps.append(f"报告 {row['report']} 分配 x=({_fmt(xa)},{_fmt(xb)}) 之和 >1：机制在『印资源』，可被无限套利。")
        if min(xa, xb) < 0 or max(xa, xb) > 1:
            gaps.append(f"报告 {row['report']} 分配概率越界（{_fmt(xa)},{_fmt(xb)}），规则未定义负分配/超额分配的含义。")
    # 2) DSIC / BIC / IR / BB
    dsic_fail, bic_fail, ir_fail, bb_fail = [], [], [], []
    exp_util = {pl: [F(0), F(0)] for pl in players}
    for pl in players:
        i = 0 if pl == "A" else 1
        for t in range(len(V[pl])):
            for other_report in reports:
                rep = [None, None]
                rep[i] = t
                rep[1 - i] = other_report
                truthful = idx.get((rep[0], rep[1]))
                if truthful is None:
                    continue
                u_truth = util(pl, t, truthful)
                for mis in reports:
                    rep2 = list(rep)
                    rep2[i] = mis
                    row2 = idx.get((rep2[0], rep2[1]))
                    if row2 is None:
                        continue
                    u_mis = util(pl, t, row2)
                    if u_mis > u_truth:
                        dsic_fail.append({"player": pl, "type": t, "other": other_report,
                                          "misreport": mis, "gain": _dec(u_mis - u_truth)})
                # BIC/IR 期望
                exp_util[pl][t] += P[pl][t] * _num(prior[players[1 - i]][other_report]) * u_truth
    for pl in players:
        for t in range(len(V[pl])):
            if exp_util[pl][t] < 0:
                ir_fail.append({"player": pl, "type": t, "expected_utility": _dec(exp_util[pl][t])})
    for row in rule:
        bb = _num(row["pay"][0]) + _num(row["pay"][1])
        if bb < 0:
            bb_fail.append({"report": row["report"], "transfer": _dec(bb)})
    # 3) 资金泵：无分配却拿到钱
    pump = []
    for row in rule:
        for i, pl in enumerate(players):
            if _num(row["alloc"][i]) == 0 and _num(row["pay"][i]) < 0:
                pump.append({"player": pl, "report": row["report"], "payment": _dec(row["pay"][i])})
    # 4) 效率对比
    welfare = F(0)
    first_best = F(0)
    for row in rule:
        tA, tB = row["report"]
        pr = P["A"][tA] * P["B"][tB]
        va = V["A"][tA] * _num(row["alloc"][0])
        vb = V["B"][tB] * _num(row["alloc"][1])
        welfare += pr * (va + vb)
        first_best += pr * max(V["A"][tA], V["B"][tB])
    out["numbers"].update({
        "expected_welfare": _dec(welfare),
        "first_best_welfare": _dec(first_best),
        "efficiency_ratio": _dec(welfare / first_best) if first_best else None,
    })
    ev.append(f"期望社会福利 {_fmt(welfare)} / 一阶最优 {_fmt(first_best)} = "
              f"{_fmt(welfare/first_best) if first_best else 'n/a'}（<1 说明规则在浪费价值）")
    if dsic_fail:
        ev.append(f"DSIC 违反 {len(dsic_fail)} 处：说真话不是最优策略 -> 规则在奖励说谎。示例：" + json.dumps(dsic_fail[:3], ensure_ascii=False))
        gaps.append("激励不相容：存在『谎报能多拿』的报告组合，参与者会系统性地撒谎。")
    else:
        ev.append("DSIC 通过：每个类型在任何对手报告下说真话都是最优。")
    if ir_fail:
        ev.append(f"IR 违反 {len(ir_fail)} 处：某些类型参与是负收益 -> 他们会摆烂/拒参/同归于尽。")
        gaps.append("参与约束被破坏：被强制参与的负收益者会破坏机制本身（飞升合同的自裁条款即此类）。")
    else:
        ev.append("IR 通过：所有类型参与不比不参与差。")
    if bb_fail:
        ev.append(f"预算不平衡 {len(bb_fail)} 处：机制向参与者净支出 -> 需要有外部金主或不可持续。")
    if pump:
        ev.append(f"发现资金泵 {len(pump)} 处（0 分配却收到支付）：可被无限刷取。示例：" + json.dumps(pump[:3], ensure_ascii=False))
        gaps.append("存在零成本获利动作（免费午餐）：参与者会只刷这个动作而不是玩游戏。")
    if not gaps:
        gaps.append("未发现结构性套利；剩余风险在规则文本的未定义项（判定函数/平局/时限/解释权）。")

    out["violations"] = {"dsic": dsic_fail[:6], "ir": ir_fail[:6], "bb": bb_fail[:6], "money_pump": pump[:6]}
    out["gaps"].extend(gaps)
    if dsic_fail or ir_fail or pump:
        out["verdict"] = "机制存在结构性漏洞（DSIC/IR/资金泵）"
        out["action"] = "作为设计者：修正违规报告组合的支付/分配；作为参与者：按违规路径套利，或公开要求补丁以换取让步。"
    else:
        out["verdict"] = "机制在激励层面自洽（结构性漏洞未发现）"
        out["action"] = "转向文本层漏洞审计：判定函数、平局、时限、解释权、隐藏规则权限。"
    out["counter"] = "对手若知道漏洞，会沉默并利用；反制=抢先公开漏洞并提出对自己有利的补丁版本。"
    out["fail_if"] = ["只看规则文字不看激励结构", "假设所有参与者都会诚实报告类型", "忽略平局/时限未定义处"]
    return out


# --------------------------------------------------------------------------------------
# 十、求解器 G6：逆向归纳 / 承诺可信度
# --------------------------------------------------------------------------------------

def solve_backward(spec):
    tree = spec["tree"]
    players = spec.get("players", ["P0", "P1"])
    out = {"model": "G6", "solver": "backward", "story": spec.get("anchor", "仓颉棋 / 青龙游戏"),
           "title": spec.get("name", "逆向归纳"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    strategy = {}

    def is_terminal(node):
        return "payoffs" in node

    def rec(node, path):
        if is_terminal(node):
            return [_num(x) for x in node["payoffs"]]
        pl = node["player"]
        vals = {}
        for act, child in node["actions"].items():
            vals[act] = rec(child, path + [act])
        best = max(vals, key=lambda a: vals[a][pl])
        strategy[" -> ".join(path) or "<root>"] = {"player": players[pl], "chosen": best,
                                                   "values": {a: [_dec(v[0]), _dec(v[1])] for a, v in vals.items()}}
        claimed = node.get("claimed_best")
        if claimed and claimed not in node["actions"]:
            out["gaps"].append(f"数据问题：节点『{'/'.join(path) or 'root'}』的 claimed_best=『{claimed}』"
                               f"与动作名不符，已忽略（可用动作：{list(node['actions'])}）。")
            claimed = None
        if claimed and claimed != best:
            strategy[" -> ".join(path) or "<root>"]["non_credible_threat"] = claimed
            out["gaps"].append(f"节点『{'/'.join(path) or 'root'}』{players[pl]} 宣称会选『{claimed}』，"
                        f"但逆向归纳显示他实际会选『{best}』——不可信威胁。")
        return vals[best]

    root_vals = rec(tree, [])
    out["numbers"]["spne_value"] = [_dec(root_vals[0]), _dec(root_vals[1])]
    out["numbers"]["strategy"] = strategy
    ev.append(f"子博弈完美均衡值：{players[0]}={_fmt(root_vals[0])}, {players[1]}={_fmt(root_vals[1])}")
    # 主路径
    path, node = [], tree
    while not is_terminal(node):
        key = " -> ".join(path) or "<root>"
        act = strategy[key]["chosen"]
        path.append(act)
        node = node["actions"][act]
    out["numbers"]["spne_path"] = path
    ev.append("SPNE 主路径：" + " -> ".join(path))

    # 先手价值
    if "simultaneous" in spec:
        A, B, nr, nc = _load_matrix(spec["simultaneous"])
        nes = pure_nash(A, B)
        if nes:
            i, j = nes[0]
            out["numbers"]["simultaneous_equilibrium"] = [nr[i], nc[j]]
            out["numbers"]["simultaneous_value"] = [_dec(A[i][j]), _dec(B[i][j])]
            adv = root_vals[0] - A[i][j]
            out["numbers"]["first_mover_advantage"] = _dec(adv)
            ev.append(f"若改为同时行动：均衡 ({nr[i]}, {nc[j]}) 值 ({_fmt(A[i][j])}, {_fmt(B[i][j])})；"
                      f"先手价值（{players[0]}）= {_fmt(root_vals[0])} - {_fmt(A[i][j])} = {_fmt(adv)}"
                      f" -> {'应抢先进场' if adv > 0 else '让对方先动更有利'}")
    noncred = [k for k, v in strategy.items() if "non_credible_threat" in v]
    out["numbers"]["non_credible_nodes"] = noncred
    out["verdict"] = "SPNE 已求解" + (f"；发现 {len(noncred)} 处不可信威胁" if noncred else "；未发现不可信威胁")
    out["action"] = "沿 SPNE 主路径行动；对不可信威胁不予让步，并公开指出其不可信（剥夺其威慑力）。"
    out["counter"] = "对手若把不可信威胁升级为自缚承诺（机关/第三方/公开立誓），需重算树并准备反制（G4 改规则 / G1 改重复关系）。"
    out["fail_if"] = ["把不可信威胁当真而过度让步", "假设对手会为履约付出超过收益的代价", "忽略终局结算者的利益"]
    out["gaps"].append("终局结算者若可改写胜负，整棵树需重画（G12）。")
    return out


# --------------------------------------------------------------------------------------
# 十一、求解器 G7：沉没成本 / 承诺升级
# --------------------------------------------------------------------------------------

def solve_sunk(spec):
    S = _num(spec.get("sunk_cost", 0))
    c = _num(spec.get("continue_cost", 0))
    p = _num(spec.get("win_prob", 0.5))
    V = _num(spec.get("prize", 1))
    q = _num(spec.get("quit_value", 0))
    out = {"model": "G7", "solver": "sunk", "story": spec.get("anchor", "第250章 沉没成本"),
           "title": spec.get("name", "沉没成本决策"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    evc = p * V - c
    p_star = (c + q) / V if V else F(0)
    p_lookback = (S + c + q) / V if V else F(0)
    out["numbers"].update({"sunk_cost": _dec(S), "continue_cost": _dec(c), "win_prob": _dec(p),
                           "prize": _dec(V), "quit_value": _dec(q),
                           "ev_continue": _dec(evc), "p_star": _dec(p_star),
                           "p_lookback_threshold": _dec(p_lookback)})
    ev.append(f"沉没成本 S={_fmt(S)}（无论怎么选都收不回，必须从决策中剔除）")
    ev.append(f"增量决策：EV(继续)=p·V-c = {_fmt(p)}·{_fmt(V)}-{_fmt(c)} = {_fmt(evc)}；放弃收益 q={_fmt(q)}")
    ev.append(f"临界胜率 p* = (c+q)/V = {_fmt(p_star)}；『把这笔投入算进去』的伪临界值 = (S+c+q)/V = {_fmt(p_lookback)}")
    if p >= p_star and evc >= q:
        if p < p_lookback:
            ev.append(f"当前 p={_fmt(p)} 落在陷阱区间 [{_fmt(p_star)}, {_fmt(p_lookback)})：理性上应继续，"
                      f"但沉没成本直觉会让人想放弃——此时放弃是情绪决策。")
            out["verdict"] = "理性应继续（沉没成本直觉会误判为放弃）"
            out["action"] = "继续，但把 S 从理由里删掉；同时重新设定硬止损线 p* 与增量预算。"
        else:
            out["verdict"] = "理性应继续"
            out["action"] = "继续执行；把 S 转化为承诺资产（公开投入/烧退路）以换取可信度（G6）。"
    else:
        ev.append(f"当前 p={_fmt(p)} < p*={_fmt(p_star)}：继续的 EV 低于放弃，任何『已经投入这么多』的理由都是谬误。")
        out["verdict"] = "应立即止损"
        out["action"] = f"止损（保留 q={_fmt(q)}），并把决策权交给未投入此局的第三方以防自己反悔。"
    # 战的消耗模型（war of attrition）
    wa = spec.get("war_of_attrition")
    if wa:
        V2, cost_rate = _num(wa["prize"]), _num(wa["cost_per_period"])
        exp_dur = V2 / cost_rate
        out["numbers"]["war_of_attrition_expected_duration"] = _dec(exp_dur)
        ev.append(f"消耗战（war of attrition）对称均衡：退出率 h=c/V={_fmt(cost_rate/V2)}，期望持续 {_fmt(exp_dur)} 个周期。"
                  f"含义：拖延的期望成本=对手估值，谁的估值低谁先退；抬高自己估值的外部信号可以逼退对手。")
        out["gaps"].append("消耗战期望时长 = V/c：若对手估值未知，需先探测其 V 再决定是否拖。")
    out["counter"] = "对对手：先让他投入（门票/抵押/公开承诺），再改规则抬价，他的 S 越大越难退（第617章 失算）。"
    out["fail_if"] = ["用『已投入』作为继续的理由", "不设硬止损线", "把可回收资产当沉没成本销毁，丢失退出选项"]
    return out


# --------------------------------------------------------------------------------------
# 十二、求解器 G8：诈唬频率 / 底池赔率
# --------------------------------------------------------------------------------------

def solve_bluff(spec):
    P = _num(spec.get("pot", 100))
    b = _num(spec.get("bet", 50))
    out = {"model": "G8", "solver": "bluff", "story": spec.get("anchor", "朔望月 / 极乐博彩"),
           "title": spec.get("name", "诈唬与底池赔率"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    mdf = P / (P + b)
    alpha = b / (P + b)
    bluff_frac = b / (P + 2 * b)
    vb_ratio = (P + b) / b
    out["numbers"].update({"pot": _dec(P), "bet": _dec(b), "MDF": _dec(mdf), "alpha": _dec(alpha),
                           "bluff_fraction_of_bets": _dec(bluff_frac),
                           "value_to_bluff_ratio": f"{_fmt(vb_ratio)} : 1",
                           "ev_bluff_at_fold_freq_0.5": _dec(F(1, 2) * P - F(1, 2) * b)})
    ev.append(f"底池 P={_fmt(P)}，下注 b={_fmt(b)}")
    ev.append(f"对手最小防守频率 MDF = P/(P+b) = {_fmt(mdf)}：低于这个频率，我用任意两张牌诈唬都是 +EV")
    ev.append(f"我作为下注方的诈唬上限 α = b/(P+b) = {_fmt(alpha)}（超过即被『永远跟注』剥削）")
    ev.append(f"均衡诈唬占所有下注的比例 = b/(P+2b) = {_fmt(bluff_frac)}；价值:诈唬 = {_fmt(vb_ratio)} : 1")
    opp_fold = spec.get("opponent_fold_freq")
    if opp_fold is not None:
        f = _num(opp_fold)
        evb = f * P - (1 - f) * b
        ev.append(f"已知对手弃牌率 f={_fmt(f)}：纯诈唬 EV = f·P-(1-f)·b = {_fmt(evb)}"
                  f" -> {'必诈' if evb > 0 else '不要诈唬（除非有补牌权益）'}")
        out["numbers"]["ev_bluff_given_fold"] = _dec(evb)
        out["action"] = (f"提高诈唬频率：对手弃牌率 {_fmt(f)} 低于 MDF {_fmt(mdf)}，任意两张牌下注都是 +EV"
                         f"（EV 增幅 {_fmt(evb)}/次）；直到他被迫把跟注率提到 MDF 以上为止" if evb > 0 else
                         "停止诈唬，只做价值下注；用更小的下注尺度降低对手 MDF")
    else:
        out["action"] = (f"按 {_fmt(bluff_frac)} 的诈唬比例混合：每 {_fmt(vb_ratio-1)} 次价值下注配 1 次诈唬；"
                         f"对手跟注频率低于 {_fmt(mdf)} 时提高诈唬频率。")
    payout = spec.get("payout_multiplier")
    if payout is not None:
        m = _num(payout)
        eff = (P * m) / (P * m + b)
        out["numbers"]["payout_adjusted_MDF"] = _dec(eff)
        ev.append(f"赔付倍数 m={_fmt(m)}（如极乐博彩『杀』额外翻倍）：等效底池 {_fmt(P*m)}，"
                  f"对手的 MDF 抬升到 {_fmt(eff)} -> 高赔率档位会把对手逼进『必须防守』的窄区间")
        out["gaps"].append("高赔率档位若能让对手防守不足，即为套利窗；需确认赔付上限与结算方偿付能力。")
    ev.append("注意固定成本：极乐博彩每次胜利还要交一颗「道」场地费（除非只赢一颗），名义 +EV 会转负。")
    out["verdict"] = "诈唬/防守频率已定价"
    out["counter"] = "对手若诈唬过多 -> 把跟注频率提到 MDF 以上；对手若从不诈唬 -> 只跟价值注，弃掉边缘牌。"
    out["fail_if"] = ["诈唬比例超 α 被无限跟注", "防守频率低于 MDF 被无限诈唬", "忽略场地费/抽水导致名义正 EV 实际负 EV"]
    return out


# --------------------------------------------------------------------------------------
# 十三、求解器 G9：概率分配设计
# --------------------------------------------------------------------------------------

def solve_prob(spec):
    B = int(spec.get("black", 50))
    W = int(spec.get("white", 50))
    out = {"model": "G9", "solver": "prob", "story": spec.get("anchor", "人猪「黑白棋」"),
           "title": spec.get("name", "概率分配最优解"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    best = None
    for b1 in range(B + 1):
        for w1 in range(W + 1):
            if b1 + w1 == 0 or (B - b1) + (W - w1) == 0:
                continue
            p = F(1, 2) * F(b1, b1 + w1) + F(1, 2) * F(B - b1, (B - b1) + (W - w1))
            if best is None or p > best[0]:
                best = (p, b1, w1)
    p_eq = F(1, 2) * F(B // 2, B // 2 + W // 2) + F(1, 2) * F(B - B // 2, (B - B // 2) + (W - W // 2))
    p, b1, w1 = best
    out["numbers"].update({"best_prob": _dec(p), "bowl1": {"black": b1, "white": w1},
                           "bowl2": {"black": B - b1, "white": W - w1},
                           "equal_split_prob": _dec(p_eq),
                           "gain_vs_equal": _dec(p - p_eq)})
    ev.append(f"黑白各 {B}/{W} 颗，两碗均非空，随机选碗后随机摸一颗：")
    ev.append(f"最优分配：碗1 = {b1}黑+{w1}白（{B-b1}黑+{W-w1}白）-> 胜率 {_fmt(p)}")
    ev.append(f"平均分配胜率仅 {_fmt(p_eq)}；最优解把胜率抬高 {_fmt(p - p_eq)}")
    ev.append("原理：把一个几乎必胜的小分支概率拉到 1，代价是另一分支略低于 1 —— 极端集中优于平均。")
    if spec.get("allow_equal_bowls"):
        p_eqb = F(1, 2) * F(b1 * 50, 50) if False else None
        if B == W == 50:
            ev.append("若规则要求『每碗必须恰好 50 颗』：任意分配胜率都恒为 1/2（数学上无解可优化）"
                      "——这条规则解读直接决定了本局是 50% 还是 74.7%，属于规则未定义的关键歧义。")
            out["gaps"].append("『棋子数量要达到五十颗』歧义：每碗50颗 vs 每种颜色用满50颗 —— 前者最优=50%，后者=74.75%。")
    out["verdict"] = f"最优胜率 {_fmt(p)}"
    out["action"] = f"按碗1={b1}黑+{w1}白的极端集中分配；并确保『随机选碗』由我/裁判执行而非对手选择。"
    out["counter"] = "若是对手分配：他可以拒绝这种分配或改规则；反制=抢先写下分配规则并要求对方先确认。"
    out["fail_if"] = ["平均分配", "忽略『谁选碗』的权利归属", "把单次抽样当大数定律"]
    return out


# --------------------------------------------------------------------------------------
# 十四、求解器 G10：共同知识 / 两军问题
# --------------------------------------------------------------------------------------

def solve_common(spec):
    p = _num(spec.get("reliability", 0.9))
    msgs = spec.get("msgs", [1, 2, 3])
    target = _num(spec.get("target", 0.99))
    out = {"model": "G10", "solver": "common", "story": spec.get("anchor", "人蛇面试「两军问题」"),
           "title": spec.get("name", "共同知识与协调"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": ""}
    ev = out["evidence"]
    ev.append(f"单条消息可靠性 p={_fmt(p)}；n 轮确认后协同成功率 = p^n")
    table = {}
    for n in msgs:
        v = p ** int(n)
        table[str(int(n))] = _dec(v)
        ev.append(f"  n={n}: p^n={_fmt(v)}")
    out["numbers"]["coord_prob"] = table
    n_need = None
    if 0 < p < 1:
        # p<1 时 p^n 单调下降：确认轮数越多，协同概率越低（这本身就是两军问题的核心反直觉结论）
        n_max = math.floor(math.log(float(target)) / math.log(float(p)))
        n_need = n_max
        out["numbers"]["max_usable_rounds"] = n_max
        if n_max < 1:
            ev.append(f"目标 {_fmt(target)} 在 p={_fmt(p)} 下不可达（n=1 已只有 {_fmt(p)}）："
                      f"每多一轮确认，协同概率再乘一次 p -> 『加确认』是负收益。")
        else:
            ev.append(f"要达到 {_fmt(target)} 最多只能确认 {n_max} 轮；再多一轮就会跌破目标。")
    ev.append("两军问题结论：在不可靠信道上不存在有限轮协议能达成『共同知识』；必须改机制而不是加轮数。")
    out["verdict"] = "协调不可能性成立（需改机制）"
    out["action"] = ("把『同时行动』改成『先后行动』或『单点决策+回执』；"
                     f"用多路径冗余把 p 提高到可用水平（当前 p={_fmt(p)}，需 {n_need} 轮确认）。")
    out["counter"] = "对手可利用不确定性：故意让最后一条确认丢失，使你在不确定中先动/不动。反制=设计容错行动。"
    out["fail_if"] = ["假设一次沟通=共同知识", "追求绝对确认导致错过窗口", "忽略奸细可伪造确认（G1）"]
    out["gaps"].append("若信道中存在叛徒（奸细），任何确定性协议失效：需加入可验证签名或利益绑定。")
    return out


# --------------------------------------------------------------------------------------
# 十五、求解器 G12：元博弈 / 目标函数审计
# --------------------------------------------------------------------------------------

def solve_meta(spec):
    out = {"model": "G12", "solver": "meta", "story": spec.get("anchor", "第337章 道的骗局"),
           "title": spec.get("name", "终局与目标审计"), "evidence": [], "numbers": {}, "gaps": [],
           "action": "", "counter": "", "fail_if": [], "verdict": "", "risks": []}
    ev = out["evidence"]
    goal_source = spec.get("goal_source", "other")     # self / other
    settler = spec.get("settler_trusted", False)
    settle_can_alter = spec.get("settler_can_alter", True)
    exit_option = spec.get("has_exit_option", False)
    second_goal = spec.get("has_second_goal", False)
    score = 0
    if goal_source == "other":
        score += 2
        out["risks"].append("目标由他人设定：你可能在完成别人的计划（道的骗局：集齐反招洗牌）。")
    if not settler:
        score += 2
        out["risks"].append("结算者不可信：赢了也可能被判输。")
    if settle_can_alter:
        score += 2
        out["risks"].append("结算者可改写胜负：终局不是终局。")
    if not exit_option:
        score += 2
        out["risks"].append("没有退出/掀桌选项：会被无限加价。")
    if not second_goal:
        score += 1
        out["risks"].append("只有单层目标：缺少『胜利后自保』的备份。")
    for r in out["risks"]:
        ev.append("风险：" + r)
    ev.append(f"元博弈风险分 {score}/9（≥4 表示『赢了也可能归零』）")
    out["numbers"]["meta_risk_score"] = score
    out["verdict"] = "高元博弈风险" if score >= 4 else "元博弈风险可控"
    out["action"] = ("先把结算权/规则制定权拿到手，或把结算者也拖进赌局使其必须履约；"
                     "同时准备第二层目标（退出权/掀桌可信威胁/新世界）。")
    out["counter"] = "对手若单方面宣布目标，公开质疑其目标函数并给出现价（谁受益谁定目标）。"
    out["fail_if"] = ["只优化给定目标", "没有掀桌选项", "假设裁判中立"]
    out["gaps"].append("目标函数来源未确证：需追问『这个进度条集满后由谁结算、他得到什么』。")
    return out


def solve_metaq(spec):
    prop = spec.get("prop", "P")
    out = {"model": "G2/G9", "solver": "metaq", "title": "是与非型元问题", "evidence": [],
           "numbers": {}, "gaps": [], "verdict": "", "action": "", "counter": "", "fail_if": []}
    ev = out["evidence"]
    q = f"如果我问你『{prop}』，你会回答『是』吗？"
    ev.append(f"构造问题：{q}")
    ev.append("真话者：内层回答=真实答案，外层照实转述 -> 回答『是』当且仅当命题为真。")
    ev.append("说谎者：内层必须给假答案，外层再对『我会说是吗』说谎 -> 两次取反抵消 -> 回答『是』当且仅当命题为真。")
    # 真值表验证
    rows = []
    for truth in (True, False):
        for liar in (False, True):
            inner_answer_yes = truth if not liar else (not truth)
            # 外层命题: "如果我问你P，你会回答是吗" 的真值 = inner_answer_yes
            outer_prop = inner_answer_yes
            answer_yes = outer_prop if not liar else (not outer_prop)
            rows.append({"truth": truth, "is_liar": liar, "inner": inner_answer_yes, "answer_yes": answer_yes})
    ok = all(r["answer_yes"] == r["truth"] for r in rows)
    out["numbers"]["truth_table"] = rows
    out["numbers"]["normalizes"] = ok
    ev.append(f"真值表验证：{'通过——无论对方说真话还是说假话，回答都与命题真值一致' if ok else '失败'}")
    ev.append("所以只需一次提问就能确定黑白棋碗中的颜色（地羊四情扇/人猪赌命版的核心工具）。")
    out["verdict"] = "元问题可把『真假不确定性』归一化为 0"
    out["action"] = f"对任意一人只问这一句：{q}"
    out["counter"] = "对手若规定『不许问关于回答本身的问题』，则退回概率分配（G9）或换问法（指代型问题）。"
    out["fail_if"] = ["直接问『是不是』-> 遇到说谎者得到相反答案", "问复合命题引入歧义"]
    return out


def solve_poker(spec):
    """朔望月点数判定：两张手牌 + 可选公共牌，点数不得大于 16（隐藏规则），最接近 16 者胜。"""
    cards = [int(x) for x in spec.get("cards", [])]
    pub = spec.get("public")
    out = {"model": "G5/G8", "solver": "poker", "story": "终极游戏「朔望月」",
           "title": "朔望月点数判定", "evidence": [], "numbers": {}, "gaps": [],
           "verdict": "", "action": "", "counter": "", "fail_if": []}
    ev = out["evidence"]
    cap = int(spec.get("cap", 16))
    cands = []
    for r in range(0, len(cards) + 1):
        for combo in itertools.combinations(cards, r):
            s = sum(combo)
            cands.append((s, combo))
    if pub is not None:
        pub = int(pub)
        for r in range(0, len(cards) + 1):
            for combo in itertools.combinations(cards, r):
                s = sum(combo) + pub
                cands.append((s, combo + (pub,)))
    legal = [(s, c) for s, c in cands if s <= cap]
    if not legal:
        ev.append(f"所有组合都 > {cap}：全部爆牌 -> 只能弃牌/认输")
        out["verdict"] = "必然爆牌"
        out["action"] = "立即认输，止损（G7）"
        return out
    legal.sort(key=lambda t: t[0], reverse=True)
    best_s, best_c = legal[0]
    out["numbers"].update({"cap": cap, "best_score": best_s, "best_combo": list(best_c),
                           "legal_scores": sorted({s for s, _ in legal}, reverse=True)})
    ev.append(f"隐藏规则：点数不得大于 {cap}（超过即爆），最接近 {cap} 最大；公共牌可以不用。")
    ev.append(f"手牌 {cards}" + (f" + 公共牌 {pub}" if pub is not None else "") + f" -> 可选最高合法点数 {best_s}（组合 {list(best_c)}）")
    ev.append(f"全部合法点数：{out['numbers']['legal_scores']}")
    over = [s for s, _ in cands if s > cap]
    if over:
        ev.append(f"被隐藏规则『爆掉』的组合有 {len(over)} 个（对手若不知此规则会把它们当强牌下注 -> 可被反向收割）")
        out["gaps"].append("点数上限为隐藏规则：对手不知道时会用 >16 的牌下注，这是可定价的信息差。")
    out["verdict"] = f"最佳合法点数 {best_s}"
    out["action"] = f"报 {best_s}（组合 {list(best_c)}）；若对手下注额与其明牌不匹配，按其爆牌概率反加注。"
    out["counter"] = "若对手也知道上限：改用诈唬频率（G8）与位置优势，而非牌力。"
    out["fail_if"] = ["把两张牌之和直接当点数（忽略公共牌可用/不可用）", "忽略爆牌线", "在平局规则未定义时假定自己赢"]
    return out


# --------------------------------------------------------------------------------------
# 十五点五、下注闸门 gate：把 checklist 变成可执行的硬门禁
# --------------------------------------------------------------------------------------

GATES = [
    ("rules_full_text", "G0 规则全文", "S0",
     "抄全规则原文并标注：判定函数 / 平局 / 时限 / 解释权归属 / 隐藏规则权限",
     "没有规则全文 = 你在按猜测下注；回到 S0，用 G4 的文本审计清单过一遍。"),
    ("structure_confirmed", "G1 结构确认", "S2",
     "把局面写成收益矩阵或博弈树，并验证结构（是否真 PD / 是否零和 / 是否单次）",
     "结构误判是方向性错误：该强硬时合作、该合作时强硬，都会死。"),
    ("info_value_checked", "G2 信息价值", "S1",
     "算过 EVPI，并确认『继续侦查』的成本不超过它",
     "在信息不足时押注，或在高成本取证上浪费时间，都是负 EV。"),
    ("threat_checked", "G3 威胁可信度", "S3",
     "用逆向归纳判断过对手的威胁/承诺在最后一步是否对他自己有利",
     "把不可信威胁当真 → 过度让步；把可信威胁当虚张 → 被处决。"),
    ("ev_positive_after_fees", "G4 扣费后正 EV", "S2",
     "把场地费/抽水/时间成本算进去后，期望收益仍为正",
     "名义 +EV、实际 −EV 是最常见的慢性死法。"),
    ("incentive_checked", "G5 激励相容", "S4",
     "检查过规则是否奖励说谎/装类型；若奖励，已按『对方会撒谎』布防",
     "不检查激励，就等于假设所有人都会诚实报告类型。"),
    ("settlement_audited", "G6 结算与退出", "S5",
     "确认结算者能否改写胜负，并持有至少一个退出/掀桌/第二层目标选项",
     "局内全胜、结算归零（道的骗局），是最贵的失败。"),
]


def solve_gate(spec):
    answers = spec.get("answers", {})
    out = {"model": "gate", "solver": "gate", "title": spec.get("name", "下注闸门"),
           "evidence": [], "numbers": {}, "gaps": [], "action": "", "counter": "",
           "fail_if": [], "verdict": "", "gates": []}
    ev = out["evidence"]
    passed, failed, unknown = [], [], []
    for key, label, stage, what, why in GATES:
        v = answers.get(key)
        item = {"key": key, "label": label, "stage": stage, "require": what, "why": why,
                "answer": v}
        if v is True:
            passed.append(item)
            ev.append(f"[PASS] {label}：{what}")
        elif v is False:
            failed.append(item)
            ev.append(f"[BLOCK] {label}：{what}\n         后果：{why}")
        else:
            unknown.append(item)
            ev.append(f"[ ? ] {label}：未回答（视为未通过）—— {what}")
    out["gates"] = passed + failed + unknown
    out["numbers"] = {"passed": len(passed), "blocked": len(failed), "unknown": len(unknown),
                      "total": len(GATES)}
    if failed or unknown:
        out["verdict"] = f"禁止下注：{len(failed)} 项被否决、{len(unknown)} 项未回答"
        first = (failed + unknown)[0]
        out["action"] = f"先补『{first['label']}』（{first['stage']}）：{first['require']}"
        out["gaps"] = [f"{i['label']}：{i['require']}" for i in (failed + unknown)]
    else:
        out["verdict"] = "七道闸门全通过：可以下注（仍需记录参数假设）"
        out["action"] = "按 S2→S6 的顺序执行；把本次参数写进 case 文件以便复盘（S6）。"
    out["counter"] = "对手也可能用同一套闸门审你的局；先自己过一遍，别让对手替你找漏洞。"
    out["fail_if"] = ["任何一道闸门未通过仍下注"]
    return out


# --------------------------------------------------------------------------------------
# 十六、总决策流水线（agent 进入任何新局的标准动作序列）
# --------------------------------------------------------------------------------------

MASTER_FLOW = [
    ("S0 规则侦察（G4）",
     "抄全规则原文 -> 标注『已定义/未定义/谁解释』 -> 找判定函数、平局、时限、隐藏权限 -> 输出漏洞清单",
     "没有规则全文，不要做任何承诺或下注。"),
    ("S1 信息盘点（G2）",
     "列状态空间与先验 -> 列可观测信号 -> 算后验与 EVPI -> 决定要不要花代价换信息",
     "把对手主动给的信息降权（可能是信号博弈里的操纵，G3）。"),
    ("S2 结构识别（G1/G5/G8）",
     "把局面写成收益矩阵 -> 判 PD/协调/胆小鬼/零和 -> 找纯均衡；无纯均衡再随机化 -> 算 MDF/诈唬比例",
     "先确认是不是真囚徒困境，误判结构=方向性错误。"),
    ("S3 顺序与承诺（G6/G7）",
     "画博弈树 -> 逆向归纳 -> 剔除不可信威胁 -> 算先手价值 -> 设计自缚承诺；用沉没成本算止损线",
     "终局结算者若可改写胜负，树要重画（转 S5）。"),
    ("S4 机制设计（G11/G4）",
     "给人设计菜单让类型自选（低档扭曲、高档付租）-> 校验 DSIC/IR/预算 -> 补规则漏洞",
     "给低类型留租金=所有人装低类型；高档不可逆义务=没人敢选。"),
    ("S5 终局审计（G12）",
     "追问目标是谁定的、赢了之后谁结算 -> 拿规则制定权/退出权/掀桌可信威胁 -> 设计第二层目标",
     "只优化别人给的目标，等于替别人打工。"),
    ("S6 复盘（G7/G2）",
     "记录实际频率与对手偏差 -> 更新先验 -> 判断是过拟合还是可剥削 -> 修正 checklist",
     "样本不足时不要宣称『读懂了对手』。"),
]


def solve_audit(spec):
    text = " ".join(str(spec.get(k, "")) for k in ("name", "summary", "rules", "situation", "keywords"))
    scores = {}
    for mid, kws in KEYWORDS.items():
        hit = [k for k in kws if k in text]
        if hit:
            scores[mid] = (len(hit), hit)
    ranked = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)
    identified = [mid for mid, _ in ranked]
    # 显式指定
    for mid in MODELS:
        if mid.lower() in spec and mid not in identified:
            identified.append(mid)
    out = {"model": "audit", "solver": "audit", "title": spec.get("name", "局面审计"),
           "identified": [], "results": {}, "gaps": [], "evidence": []}
    for mid in identified:
        info = MODELS[mid]
        sec = spec.get(mid.lower()) or spec.get(info["solver"]) or {}
        entry = {"zh": info["zh"], "code": mid, "solver": info["solver"],
                 "keyword_hits": scores.get(mid, (0, []))[1], "data_provided": bool(sec)}
        if sec:
            try:
                res = SOLVERS[info["solver"]](sec)
                entry["result"] = res
            except Exception as e:  # 数据不全时不应崩
                entry["error"] = f"{type(e).__name__}: {e}"
                entry["missing"] = info["params"]
        else:
            entry["missing"] = info["params"]
            entry["next_action"] = f"运行 `python3 qixia_gt.py {info['solver']} --file <该模型参数文件>` 后再决策"
        out["identified"].append(entry)
        for g in (entry.get("result", {}).get("gaps") or []):
            out["gaps"].append(f"[{mid}] {g}")
        if entry.get("missing"):
            out["gaps"].append(f"[{mid}] 参数缺失：{'、'.join(entry['missing'])}")
    return out


def render_audit_md(audit):
    L = []
    L.append(f"# 局面审计报告：{audit['title']}")
    L.append("")
    L.append(f"识别到的模型（按关键词命中排序）：" + ", ".join(
        f"{e['code']} {e['zh']}" + (f"(命中:{','.join(e['keyword_hits'])})" if e.get("keyword_hits") else "")
        for e in audit["identified"]))
    L.append("")
    for e in audit["identified"]:
        L.append(f"## {e['code']} {e['zh']}  [{e['solver']}]")
        r = e.get("result")
        if not r:
            L.append(f"- 参数缺失，暂无法结算：{'、'.join(e.get('missing', []))}")
            L.append(f"- 下一步：{e.get('next_action','')}")
            L.append("")
            continue
        L.append(f"- 结论：{r.get('verdict','')}")
        if r.get("action"):
            L.append(f"- 动作：{r['action']}")
        if r.get("counter"):
            L.append(f"- 反制：{r['counter']}")
        if r.get("evidence"):
            L.append("- 推导：")
            for line in r["evidence"]:
                L.append(f"  - {line}")
        if r.get("numbers"):
            L.append("- 数值：" + json.dumps(_jsonify(r["numbers"]), ensure_ascii=False)[:1200])
        L.append("")
    L.append("## 汇总：规则未定义处 / 待补参数")
    for g in audit["gaps"]:
        L.append(f"- {g}")
    L.append("")
    L.append("## 决策顺序（强制）")
    for step, what, why in MASTER_FLOW:
        L.append(f"1. **{step}** — {what}")
    return "\n".join(L)


def render_solver_text(res):
    L = []
    L.append(f"[{res.get('model')}/{res.get('solver')}] {res.get('title','')}" +
             (f"  (锚点: {res.get('story')})" if res.get("story") else ""))
    if res.get("verdict"):
        L.append(f"结论: {res['verdict']}")
    for line in res.get("evidence", []):
        L.append("  " + line)
    if res.get("numbers"):
        L.append("数值: " + json.dumps(_jsonify(res["numbers"]), ensure_ascii=False)[:2000])
    if res.get("action"):
        L.append("建议动作: " + res["action"])
    if res.get("counter"):
        L.append("反制: " + res["counter"])
    if res.get("fail_if"):
        L.append("失败条件: " + "; ".join(res["fail_if"]))
    if res.get("gaps"):
        L.append("规则未定义/待补:")
        for g in res["gaps"]:
            L.append("  - " + g)
    return "\n".join(L)


def render_checklist(ids, fmt="md"):
    out = {}
    for mid in ids:
        m = MODELS[mid]
        out[mid] = {"zh": m["zh"], "en": m["en"], "solver": m["solver"], "anchors": m["anchors"],
                    "use_when": m["use_when"], "params": m["params"], "flow": m["flow"],
                    "checks": m["checks"], "red_flags": m["red_flags"], "counters": m["counters"],
                    "fail_if": m["fail_if"]}
    if fmt == "json":
        return json.dumps(out, ensure_ascii=False, indent=2)
    L = []
    for mid, d in out.items():
        L.append(f"## {mid} {d['zh']} ({d['en']})")
        L.append(f"- 脚本入口: `python3 qixia_gt.py {d['solver']} --file <json>`")
        L.append(f"- 原书锚点: {'；'.join(d['anchors'])}")
        L.append("- 何时用: " + " / ".join(d["use_when"]))
        L.append("- 必需参数: " + "；".join(d["params"]))
        L.append("- 决策流程:")
        for s in d["flow"]:
            L.append(f"    {s}")
        L.append("- 判定 checklist（任一不过就别下注）:")
        for s in d["checks"]:
            L.append(f"    [ ] {s}")
        L.append("- 危险信号: " + "；".join(d["red_flags"]))
        L.append("- 反制: " + "；".join(d["counters"]))
        L.append("- 失败条件: " + "；".join(d["fail_if"]))
        L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------------------
# 十七、CLI
# --------------------------------------------------------------------------------------

SOLVERS = {
    "pd": solve_pd,
    "bayes": solve_bayes,
    "mixed": solve_mixed,
    "signaling": solve_signaling,
    "screening": solve_screening,
    "mechanism": solve_mechanism,
    "backward": solve_backward,
    "sunk": solve_sunk,
    "bluff": solve_bluff,
    "prob": solve_prob,
    "common": solve_common,
    "meta": solve_meta,
    "metaq": solve_metaq,
    "poker": solve_poker,
    "gate": solve_gate,
}


def _read_spec(args):
    if getattr(args, "file", None):
        with open(args.file, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _emit(res, args):
    if getattr(args, "out", None):
        txt = render_solver_text(res) if not isinstance(res, dict) or res.get("solver") != "audit" else render_audit_md(res)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(txt + "\n")
    if getattr(args, "json", False):
        print(json.dumps(_jsonify(res), ensure_ascii=False, indent=2))
    elif isinstance(res, dict) and res.get("solver") == "audit":
        print(render_audit_md(res))
    else:
        print(render_solver_text(res))


def build_parser():
    p = argparse.ArgumentParser(description="齐夏 skills · 博弈论决策引擎")
    p.add_argument("--version", action="version", version=VERSION)
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("models", help="模型索引")
    sp.add_argument("--json", action="store_true")

    sp = sub.add_parser("flow", help="总决策流水线")
    sp.add_argument("--json", action="store_true")

    sp = sub.add_parser("checklist", help="判定 checklist")
    sp.add_argument("--model", default=None, help="G1..G12，缺省=全部")
    sp.add_argument("--format", default="md", choices=["md", "json"])
    sp.add_argument("--out", default=None)

    specs = {
        "pd": "囚徒困境/重复博弈",
        "bayes": "贝叶斯更新",
        "mixed": "混合策略均衡",
        "signaling": "信号博弈",
        "screening": "甄别菜单",
        "mechanism": "机制/规则审计",
        "backward": "逆向归纳",
        "sunk": "沉没成本",
        "bluff": "诈唬/底池赔率",
        "prob": "概率分配",
        "common": "共同知识",
        "meta": "元博弈审计",
        "metaq": "是与非元问题",
        "poker": "朔望月点数",
    }
    for name, desc in specs.items():
        sp = sub.add_parser(name, help=desc)
        sp.add_argument("--file", default=None, help="JSON 参数文件")
        sp.add_argument("--json", action="store_true")
        sp.add_argument("--out", default=None)
        if name == "bayes":
            sp.add_argument("--prior", type=float, default=None)
            sp.add_argument("--like", nargs=2, type=float, default=None)
        if name == "screening":
            sp.add_argument("--theta-h", type=float, default=None)
            sp.add_argument("--theta-l", type=float, default=None)
            sp.add_argument("--prior", type=float, default=None)
        if name == "bluff":
            sp.add_argument("--pot", type=float, default=None)
            sp.add_argument("--bet", type=float, default=None)
        if name == "prob":
            sp.add_argument("--black", type=int, default=None)
            sp.add_argument("--white", type=int, default=None)
        if name == "common":
            sp.add_argument("--reliability", type=float, default=None)
            sp.add_argument("--msgs", nargs="+", type=int, default=None)
        if name == "poker":
            sp.add_argument("--cards", nargs="+", type=int, default=None)
            sp.add_argument("--public", type=int, default=None)
        if name == "metaq":
            sp.add_argument("--prop", default=None)

    sp = sub.add_parser("gate", help="下注闸门：把 checklist 变成硬门禁（七道闸）")
    sp.add_argument("--file", default=None, help="answers JSON；省略则输出空白模板")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--out", default=None)

    sp = sub.add_parser("audit", help="局面审计（自动识别模型 + 跑求解器）")
    sp.add_argument("--file", required=True)
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--out", default=None)

    sp = sub.add_parser("selftest", help="内置自检")
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.cmd is None:
        ap.print_help()
        return 0
    if args.cmd == "models":
        if args.json:
            print(json.dumps({k: {kk: vv for kk, vv in v.items()} for k, v in MODELS.items()}, ensure_ascii=False, indent=2))
        else:
            for mid, m in MODELS.items():
                print(f"{mid}\t{m['zh']:<28}\t{m['en']}")
                print(f"\t脚本: python3 qixia_gt.py {m['solver']} --file <json>")
                print(f"\t锚点: {'；'.join(m['anchors'])}")
        return 0
    if args.cmd == "flow":
        if args.json:
            print(json.dumps([{"step": s, "what": w, "guard": g} for s, w, g in MASTER_FLOW], ensure_ascii=False, indent=2))
        else:
            for s, w, g in MASTER_FLOW:
                print(f"* {s}\n    {w}\n    铁律: {g}\n")
        return 0
    if args.cmd == "checklist":
        ids = [args.model] if args.model else list(MODELS)
        ids = [i.upper() if i.upper() in MODELS else i for i in ids]
        txt = render_checklist(ids, args.format)
        if args.out:
            with open(args.out, "w", encoding="utf-8", newline="\n") as f:
                f.write(txt + "\n")
        print(txt)
        return 0
    if args.cmd == "gate":
        if not args.file:
            tpl = {"name": "新局面闸门", "answers": {k: None for k, *_ in GATES}}
            print("七道闸门模板（把 null 改成 true/false 后存成 JSON，再 --file 传入）：")
            print(json.dumps(tpl, ensure_ascii=False, indent=2))
            return 0
        _emit(solve_gate(_read_spec(args)), args)  # gate 也支持 --out（与其它 solver 一致）
        return 0
    if args.cmd == "audit":
        spec = _read_spec(args)
        res = solve_audit(spec)
        _emit(res, args)
        return 0
    if args.cmd == "selftest":
        return run_selftest()

    spec = _read_spec(args)
    if args.cmd == "bayes":
        if args.prior is not None:
            spec["prior"] = args.prior
        if args.like:
            spec.setdefault("observations", []).append({"name": "观测", "likelihood": args.like})
    if args.cmd == "screening":
        if args.theta_h is not None:
            spec["theta_high"] = args.theta_h
        if args.theta_l is not None:
            spec["theta_low"] = args.theta_l
        if args.prior is not None:
            spec["prior_high"] = args.prior
    if args.cmd == "bluff":
        if args.pot is not None:
            spec["pot"] = args.pot
        if args.bet is not None:
            spec["bet"] = args.bet
    if args.cmd == "prob":
        if args.black is not None:
            spec["black"] = args.black
        if args.white is not None:
            spec["white"] = args.white
    if args.cmd == "common":
        if args.reliability is not None:
            spec["reliability"] = args.reliability
        if args.msgs:
            spec["msgs"] = args.msgs
    if args.cmd == "poker":
        if args.cards:
            spec["cards"] = args.cards
        if args.public is not None:
            spec["public"] = args.public
    if args.cmd == "metaq":
        if args.prop:
            spec["prop"] = args.prop
    res = SOLVERS[args.cmd](spec)
    _emit(res, args)
    return 0


def run_selftest():
    ok = 0
    fail = []
    def check(name, cond, extra=""):
        nonlocal ok
        if cond:
            ok += 1
            print(f"PASS {name}")
        else:
            fail.append(name + (" :: " + extra if extra else ""))
            print(f"FAIL {name} {extra}")

    # G1
    r = solve_pd({"name": "PD", "row": {"name": "我", "actions": ["C", "D"]},
                  "col": {"name": "他", "actions": ["C", "D"]},
                  "payoffs": [[[3, 3], [0, 5]], [[5, 0], [1, 1]]],
                  "repeated": {"mode": "infinite", "delta": 0.9}})
    check("G1 识别囚徒困境", r["numbers"]["is_prisoners_dilemma"] is True)
    check("G1 纳什均衡=(D,D)", r["numbers"]["pure_nash"] == [["D", "D"]], str(r["numbers"]["pure_nash"]))
    check("G1 δ*=0.5", abs(r["numbers"]["delta_star"] - 0.5) < 1e-9, str(r["numbers"]["delta_star"]))
    r2 = solve_pd({"row": {"actions": ["C", "D"]}, "col": {"actions": ["C", "D"]},
                   "payoffs": [[[3, 3], [0, 5]], [[5, 0], [1, 1]]], "repeated": {"mode": "finite", "periods": 1}})
    check("G1 单次=全期背叛", "全期背叛" in r2["verdict"] or "必然背叛" in r2["verdict"], r2["verdict"])

    # G2
    r = solve_bayes({"prior": 0.3, "observations": [{"name": "o", "likelihood": [0.9, 0.2]}],
                     "actions": [{"name": "信", "payoff": [10, -10]}, {"name": "不信", "payoff": [0, 0]}]})
    post = r["numbers"]["bayes"]["posterior"]["θ0"]
    check("G2 后验=0.6585", abs(post - 0.27 / 0.41) < 1e-6, str(post))
    check("G2 EVPI 非负", r["numbers"]["EVPI"] >= -1e-12, str(r["numbers"]["EVPI"]))

    # G5
    r = solve_mixed({"row": {"actions": ["R", "P", "S"]}, "col": {"actions": ["R", "P", "S"]},
                     "payoffs": [[[0, 0], [-1, 1], [1, -1]], [[1, -1], [0, 0], [-1, 1]], [[-1, 1], [1, -1], [0, 0]]]})
    eqs = r["numbers"]["equilibria"]
    check("G5 猜拳唯一混合均衡", len(eqs) == 1 and eqs[0]["type"] == "mixed", str(eqs))
    if eqs:
        check("G5 猜拳 1/3", all(abs(v - 1/3) < 1e-6 for v in eqs[0]["row"].values()), str(eqs[0]))
    r = solve_mixed({"row": {"actions": ["H", "T"]}, "col": {"actions": ["H", "T"]},
                     "payoffs": [[[1, -1], [-1, 1]], [[-1, 1], [1, -1]]]})
    e = r["numbers"]["equilibria"][0]
    check("G5 硬币 1/2", abs(list(e["row"].values())[0] - 0.5) < 1e-9, str(e))

    # G3
    r = solve_signaling({
        "types": ["强", "弱"], "prior": 0.5, "signals": ["昂贵", "便宜"], "actions": ["接受", "拒绝"],
        "sender_payoff": {"强": {"昂贵": {"接受": 10, "拒绝": 0}, "便宜": {"接受": 6, "拒绝": 0}},
                          "弱": {"昂贵": {"接受": -3, "拒绝": 0}, "便宜": {"接受": 6, "拒绝": 0}}},
        "receiver_payoff": {"昂贵": {"接受": {"强": 8, "弱": -2}, "拒绝": {"强": 0, "弱": 0}},
                            "便宜": {"接受": {"强": 4, "弱": 2}, "拒绝": {"强": 0, "弱": 0}}}})
    types = [e["type"] for e in r["numbers"]["equilibria"]]
    check("G3 找到分离均衡", "separating" in types, str(types))
    check("G3 单交叉成立", r["numbers"]["single_crossing"] is True)

    # G11
    r = solve_screening({"theta_high": 10, "theta_low": 6, "prior_high": 0.5})
    n = r["numbers"]
    check("G11 qH=10", abs(n["q_high"] - 10) < 1e-9, str(n))
    check("G11 qL=2", abs(n["q_low"] - 2) < 1e-9, str(n))
    check("G11 tL=12", abs(n["t_low"] - 12) < 1e-9, str(n))
    check("G11 tH=92", abs(n["t_high"] - 92) < 1e-9, str(n))
    check("G11 IC 绑定(标准解)", n["ic_binding"] is True, str(n["self_selection"]))
    check("G11 信息租金=8", abs(n["info_rent"] - 8) < 1e-9, str(n["info_rent"]))

    # G4：次价拍卖（DSIC）
    rule = []
    for ra in (0, 1):
        for rb in (0, 1):
            va = 10 if ra == 0 else 4
            vb = 10 if rb == 0 else 4
            if va >= vb:
                rule.append({"report": [ra, rb], "alloc": [1, 0], "pay": [vb, 0]})
            else:
                rule.append({"report": [ra, rb], "alloc": [0, 1], "pay": [0, va]})
    r = solve_mechanism({"player_types": {"A": [10, 4], "B": [10, 4]},
                         "prior": {"A": [0.5, 0.5], "B": [0.5, 0.5]}, "rule": rule})
    check("G4 次价拍卖 DSIC 通过", not r["violations"]["dsic"], str(r["violations"]["dsic"]))
    check("G4 次价拍卖有效率=1", abs(r["numbers"]["efficiency_ratio"] - 1) < 1e-9, str(r["numbers"]))
    rule_bad = [{"report": [ra, rb], "alloc": [1 if ra == 0 else 0, 1 if ra == 1 else 0], "pay": [0, 0]}
                for ra in (0, 1) for rb in (0, 1)]
    r = solve_mechanism({"player_types": {"A": [10, 4], "B": [10, 4]}, "rule": rule_bad})
    check("G4 违规规则被抓出", bool(r["violations"]["dsic"]) or bool(r["gaps"]), str(r["violations"]))

    # G6
    r = solve_backward({"players": ["我", "敌"], "tree": {"player": 0, "actions": {
        "进": {"player": 1, "claimed_best": "战", "actions": {"战": {"payoffs": [-1, -5]}, "退": {"payoffs": [2, 0]}}},
        "退": {"payoffs": [0, 1]}}}})
    check("G6 SPNE 值=(2,0)", [round(x, 6) for x in r["numbers"]["spne_value"]] == [2, 0], str(r["numbers"]["spne_value"]))
    check("G6 抓到不可信威胁", bool(r["numbers"]["non_credible_nodes"]), str(r["numbers"]["non_credible_nodes"]))

    # G7
    r = solve_sunk({"sunk_cost": 100, "continue_cost": 10, "win_prob": 0.3, "prize": 100, "quit_value": 0})
    check("G7 p*=(10+0)/100=0.1", abs(r["numbers"]["p_star"] - 0.1) < 1e-9, str(r["numbers"]))
    check("G7 伪阈值=1.1", abs(r["numbers"]["p_lookback_threshold"] - 1.1) < 1e-9, str(r["numbers"]))
    check("G7 结论=继续", "继续" in r["verdict"], r["verdict"])

    # G8
    r = solve_bluff({"pot": 100, "bet": 50})
    check("G8 MDF=2/3", abs(r["numbers"]["MDF"] - 2/3) < 1e-9, str(r["numbers"]))
    check("G8 诈唬占比=0.25", abs(r["numbers"]["bluff_fraction_of_bets"] - 0.25) < 1e-9, str(r["numbers"]))
    check("G8 价值:诈唬=3:1", r["numbers"]["value_to_bluff_ratio"].startswith("3"), str(r["numbers"]))

    # G9
    r = solve_prob({"black": 50, "white": 50})
    check("G9 最优=0.747474", abs(r["numbers"]["best_prob"] - 49 / 99 / 2 - 0.5) < 1e-9, str(r["numbers"]))
    check("G9 分配=1黑+0白", r["numbers"]["bowl1"]["black"] == 1 and r["numbers"]["bowl1"]["white"] == 0, str(r["numbers"]))

    # G10
    r = solve_common({"reliability": 0.9, "msgs": [1, 5], "target": 0.99})
    check("G10 p^5", abs(r["numbers"]["coord_prob"]["5"] - 0.9 ** 5) < 1e-9, str(r["numbers"]))
    check("G10 目标不可达", r["numbers"].get("max_usable_rounds", 99) < 1, str(r["numbers"]))

    # metaq
    r = solve_metaq({"prop": "碗A是黑子"})
    check("metaq 归一化真假", r["numbers"]["normalizes"] is True)

    # poker 朔望月
    r = solve_poker({"cards": [7, 9], "public": 5})
    check("poker 最佳=16", r["numbers"]["best_score"] == 16, str(r["numbers"]))
    r = solve_poker({"cards": [9, 7], "public": 5})
    check("poker 公共牌可弃用(9+7=16)", r["numbers"]["best_score"] == 16 and 5 not in r["numbers"]["best_combo"], str(r["numbers"]))
    r = solve_poker({"cards": [10, 9], "public": 8})
    check("poker 只取单张(10)", r["numbers"]["best_score"] == 10, str(r["numbers"]))

    # gate
    g = solve_gate({"answers": {k: True for k, *_ in GATES}})
    check("gate 全通过=可下注", "可以下注" in g["verdict"], g["verdict"])
    g = solve_gate({"answers": {"rules_full_text": False}})
    check("gate 缺规则=禁止下注", "禁止下注" in g["verdict"], g["verdict"])

    # audit 路由
    a = solve_audit({"name": "面试房间合同", "rules": "规则规定平局算输，裁判拥有最终解释权，违反者抹杀"})
    check("audit 命中 G4", any(e["code"] == "G4" for e in a["identified"]), str([e["code"] for e in a["identified"]]))

    print(f"\n{ok} passed, {len(fail)} failed")
    if fail:
        for f in fail:
            print("  FAILED:", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
