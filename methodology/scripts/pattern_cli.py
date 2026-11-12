#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""齐夏谋略模式库 CLI（仅用标准库，无第三方依赖）。

用法：
    python3 pattern_cli.py list                 # 列出全部模式
    python3 pattern_cli.py show P1              # 查看某模式全貌
    python3 pattern_cli.py match "只有口头规则还有裁判"   # 按情境匹配模式
    python3 pattern_cli.py check P1             # 打印 checklist
    python3 pattern_cli.py premortem P3         # 打印失败条件（事前验尸）
    python3 pattern_cli.py counter P4           # 打印反制手段
    python3 pattern_cli.py eight                # 谋略八问
    python3 pattern_cli.py route                # 情境 → 模式 路由表
    任意命令可加 --json 输出机器可读结果。
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(os.path.dirname(HERE), "patterns.index.json")

EIGHT_QUESTIONS = [
    "规则全文在哪？我拿到的是摘要、口头转述，还是原文？",
    "哪些词没有被定义？谁负责解释？",
    "谁是裁判，裁判的激励是什么？裁判是否也是参与者？",
    "赢的判定函数是什么（杀死/最多/最接近/不掉下去/存活）？",
    "输的代价由谁承担？是否牵连到我看不见的第三方？",
    "我有没有「合法的无成本动作」（不动即平衡、小注免佣、标的物销毁则义务解除）？",
    "我能否只赢半步（让对方以为看穿了）？",
    "赢了之后，结算方会做什么？谁能在结算层改写胜负？",
]

ROUTE = [
    ("进入新场景 / 只拿到口头规则 / 存在裁判", ["P1"], ["P1", "P4"]),
    ("规则出现「最终解释权」「请立即」「分类超出请撕毁」", ["P2"], ["P2", "P5"]),
    ("规则公开且对我不利（对手先手、资源更多）", ["P2", "P4"], ["P2", "P4"]),
    ("对手明显强于我，正面对抗必输", ["P3"], ["P3"]),
    ("有人向我提出约定 / 结盟 / 赌注", ["P4"], ["P4"]),
    ("对手开始犹豫、下注过重、反复确认", ["P5"], ["P5"]),
    ("我「看穿了」对方的骗局", ["P2"], ["P2"]),
    ("所有人都在收集同一样东西 / 目标异常清晰", ["P1"], ["P1"]),
]


def load() -> dict:
    with open(INDEX, encoding="utf-8") as fh:
        return json.load(fh)


def find(db: dict, pid: str) -> dict:
    pid = pid.strip().upper()
    for p in db["patterns"]:
        if p["id"].upper() == pid:
            return p
    raise SystemExit(f"未找到模式 {pid}；可用：{', '.join(p['id'] for p in db['patterns'])}")


def _emit(obj, as_json: bool, printer) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        printer(obj)


# ---------------------------------------------------------------- commands
def cmd_list(db: dict, as_json: bool) -> None:
    rows = [
        {
            "id": p["id"],
            "name": p["name"],
            "risk": p["risk"],
            "layer": "/".join(p["layer"]),
            "steps": len(p["steps"]),
            "failures": len(p["failure_modes"]),
            "counters": len(p["counters"]),
            "file": p["file"],
        }
        for p in db["patterns"]
    ]

    def pr(rows):
        print(f"{'ID':4}{'风险':10}{'层':16}{'名':24}步骤 失败 反制  文件")
        for r in rows:
            print(
                f"{r['id']:4}{r['risk']:10}{r['layer']:16}{r['name']:24}"
                f"{r['steps']:^4}{r['failures']:^4}{r['counters']:^4}  {r['file']}"
            )

    _emit(rows, as_json, pr)


def cmd_show(db: dict, pid: str, as_json: bool) -> None:
    p = find(db, pid)

    def pr(p):
        print(f"[{p['id']}] {p['name']}  ({p['en']})")
        print(f"层: {'/'.join(p['layer'])}   风险: {p['risk']}   文件: {p['file']}")
        print(f"\n摘要: {p['summary']}")
        print("\n子模式: " + " | ".join(p["subpatterns"]))
        print("\n触发条件:")
        for t in p["triggers"]:
            print(f"  {t['id']}  {t['text']}")
        print("\n执行步骤:")
        for s in p["steps"]:
            print(f"  {s['id']} {s['name']}: {s['action']}")
            print(f"      产物={s['artifact']}  判据={s['criterion']}")
        print("\n失败条件:")
        for f in p["failure_modes"]:
            print(f"  {f['id']} {f['name']}: 征兆={f['signal']} → {f['consequence']}")
        print("\n反制手段:")
        for c in p["counters"]:
            print(f"  {c['id']} {c['action']}")
        print("\n案例:")
        for c in p["cases"]:
            extra = " / ".join(f"{k}={v}" for k, v in c.items() if k not in ("anchor",))
            print(f"  · {c['anchor']}  —  {extra}")
        print("\nChecklist:")
        for i, q in enumerate(p["checklist"], 1):
            print(f"  [ ] {i}. {q}")

    _emit(p, as_json, pr)


def _score(p: dict, text: str) -> tuple[float, list[str]]:
    score = 0.0
    hits: list[str] = []
    low = text.lower()
    for t in p["triggers"]:
        for kw in t["keywords"]:
            if kw.lower() in low:
                score += 2.0
                hits.append(f"{t['id']}:{kw}")
    for kw, w in ((p["name"], 3.0), (p["summary"], 0.4)):
        if kw and kw.lower() in low:
            score += w
    for sub in p["subpatterns"]:
        core = re.sub(r"^[A-Z]?\d*\s*", "", sub)
        if core and core.lower() in low:
            score += 1.0
            hits.append(f"sub:{core}")
    return score, hits


def cmd_match(db: dict, text: str, as_json: bool) -> None:
    ranked = []
    for p in db["patterns"]:
        s, hits = _score(p, text)
        if s > 0:
            ranked.append({"id": p["id"], "name": p["name"], "score": round(s, 1), "hits": hits})
    ranked.sort(key=lambda r: -r["score"])

    def pr(ranked):
        if not ranked:
            print("未匹配到模式。先读 patterns.index.json 的 triggers，或直接执行「谋略八问」：")
            for i, q in enumerate(EIGHT_QUESTIONS, 1):
                print(f"  {i}. {q}")
            return
        print(f"情境: {text}\n")
        for r in ranked:
            print(f"  {r['id']} {r['name']}  得分={r['score']}  命中={', '.join(r['hits'][:6])}")
        top = ranked[0]["id"]
        print(f"\n建议入口: python3 pattern_cli.py show {top}")

    _emit(ranked, as_json, pr)


def cmd_check(db: dict, pid: str, as_json: bool) -> None:
    p = find(db, pid)
    _emit({"id": p["id"], "checklist": p["checklist"]}, as_json,
          lambda o: [print(f"[ ] {i}. {q}") for i, q in enumerate(o["checklist"], 1)])


def cmd_premortem(db: dict, pid: str, as_json: bool) -> None:
    p = find(db, pid)

    def pr(p):
        print(f"[{p['id']}] {p['name']} — 事前验尸（本模式会怎么死）\n")
        for f in p["failure_modes"]:
            print(f"  {f['id']} {f['name']}")
            print(f"      征兆: {f['signal']}")
            print(f"      后果: {f['consequence']}")

    _emit(p["failure_modes"], as_json, lambda _o: pr(p))


def cmd_counter(db: dict, pid: str, as_json: bool) -> None:
    p = find(db, pid)
    _emit(p["counters"], as_json, lambda o: [print(f"  {c['id']} {c['action']}") for c in o])


def cmd_eight(as_json: bool) -> None:
    _emit(EIGHT_QUESTIONS, as_json, lambda o: [print(f"{i}. {q}") for i, q in enumerate(o, 1)])


def cmd_route(as_json: bool) -> None:
    rows = [{"situation": s, "primary": a, "combo": b} for s, a, b in ROUTE]
    _emit(rows, as_json, lambda o: [print(f"  {r['situation']}\n      → {'+'.join(r['primary'])}  (组合 {'+'.join(r['combo'])})") for r in o])


USAGE = __doc__


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    db = load()
    cmd, rest = argv[0], argv[1:]
    if cmd == "list":
        cmd_list(db, as_json)
    elif cmd == "show":
        cmd_show(db, rest[0] if rest else "", as_json)
    elif cmd == "match":
        cmd_match(db, " ".join(rest), as_json)
    elif cmd == "check":
        cmd_check(db, rest[0] if rest else "", as_json)
    elif cmd == "premortem":
        cmd_premortem(db, rest[0] if rest else "", as_json)
    elif cmd == "counter":
        cmd_counter(db, rest[0] if rest else "", as_json)
    elif cmd == "eight":
        cmd_eight(as_json)
    elif cmd == "route":
        cmd_route(as_json)
    else:
        print(USAGE)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
