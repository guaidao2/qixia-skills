#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""齐夏棋局案例库检索 CLI（仅标准库，读取 knowledge/cases/cases.index.json）。

命令：
  list        过滤列表（--kind/--family/--tier/--pattern/--dedupe/--evidence/--limit）
  search      关键词检索（默认全字段）
  show        显示单条完整记录
  zodiac      十二生肖家族总表
  family      单个家族详情（含家族级攻击面/反制与所属各局）
  patterns    模式引用统计（可指定 P1..P5）
  gaps        汇总所有「未定义/可争议处」（红队清单）
  hidden      汇总所有 E1 级隐藏规则原文
  route       由情境关键词路由到候选局/战例（按命中打分）
  stats       库统计与自检信息

所有命令支持 --json 输出机器可读结果。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
INDEX = os.path.join(ROOT, "knowledge", "cases", "cases.index.json")


def load() -> dict:
    if not os.path.exists(INDEX):
        sys.exit(f"[FATAL] 缺少索引 {INDEX}，先运行 scripts/cases/build_case_index.py")
    with open(INDEX, encoding="utf-8") as fh:
        return json.load(fh)


def split_keywords(raw) -> list[str]:
    out = []
    for chunk in raw:
        for tok in str(chunk).replace("，", ",").replace(",", " ").split():
            if tok.strip():
                out.append(tok.strip())
    return out


def record_text(r: dict) -> str:
    parts = [str(r.get("uid")), str(r.get("name")), str(r.get("family") or ""), str(r.get("core") or ""),
             str(r.get("tier") or ""), str(r.get("host") or ""), str(r.get("status") or ""),
             str(r.get("players") or ""), str(r.get("ticket") or ""),
             "隐藏规则" if (r.get("hidden_rules") or []) else "", "未定义" if (r.get("gaps") or []) else ""]
    for key in ("rules", "hidden_rules", "gaps", "breakpoint", "counter", "what_happened"):
        parts.extend(str(x) for x in (r.get(key) or []))
    parts.append(str(r.get("lesson") or ""))
    parts.extend(str(x) for x in (r.get("patterns") or []))
    return "\n".join(parts)


def brief(r: dict) -> str:
    return (f"{r['uid']:<6} {r['name'][:34]:<36} {(r.get('family') or '-'):<4} "
            f"{(r.get('tier') or '-'):<8} {(r.get('status') or '-'):<10} {r.get('lines')}")


def emit(args, obj, text_lines=None):
    if args.json:
        print(json.dumps(obj, ensure_ascii=False, indent=1))
    else:
        if text_lines:
            print("\n".join(text_lines))
        else:
            print(json.dumps(obj, ensure_ascii=False, indent=1))


def cmd_list(db, args):
    recs = db["records"]
    if args.kind:
        recs = [r for r in recs if r["kind"] == args.kind]
    if args.family:
        recs = [r for r in recs if r.get("family") == args.family]
    if args.tier:
        recs = [r for r in recs if args.tier in str(r.get("tier"))]
    if args.pattern:
        head = args.pattern.split(".")[0].upper()
        recs = [r for r in recs if any(str(p).split(".")[0].upper() == head for p in r["patterns"])]
    if args.dedupe:
        recs = [r for r in recs if any(d["relation"] == args.dedupe for d in r["dedupe"])]
    if args.evidence:
        recs = [r for r in recs if r.get("evidence") == args.evidence]
    recs = recs[: args.limit]
    emit(args, recs, [brief(r) for r in recs])


def cmd_search(db, args):
    kw = [k.lower() for k in split_keywords(args.keywords)]
    scored = []
    for r in db["records"]:
        if args.field == "name":
            hay = (r["name"] + " " + str(r.get("core") or "")).lower()
        elif args.field == "rules":
            hay = "\n".join(str(x) for x in (r.get("rules") or []) + (r.get("hidden_rules") or [])).lower()
        elif args.field == "breakpoint":
            hay = "\n".join(str(x) for x in (r.get("breakpoint") or []) + [str(r.get("lesson") or "")]).lower()
        else:
            hay = record_text(r).lower()
        score = sum(hay.count(k) for k in kw)
        if score:
            scored.append((score, r))
    scored.sort(key=lambda t: (-t[0], t[2]["uid"]))
    out = [{"score": s, **r} for s, r in scored[: args.limit]]
    emit(args, out, [f"[{s:>2}] {brief(r)}" for s, r in scored[: args.limit]])


def cmd_show(db, args):
    rid = args.uid.upper()
    for r in db["records"]:
        if r["uid"].upper() == rid:
            if args.json:
                print(json.dumps(r, ensure_ascii=False, indent=1))
                return
            print(f"=== {r['uid']}  {r['name']} ===")
            print(f"kind={r['kind']}  family={r.get('family')}  tier={r.get('tier')}  "
                  f"host={r.get('host')}  lines={r.get('lines')}  evidence={r.get('evidence')}")
            if r.get("players"):
                print(f"人数={r['players']}  门票={r.get('ticket')}  状态={r.get('status')}")
            for label, key in (("规则要点（E1）", "rules"), ("隐藏规则（E1）", "hidden_rules"),
                               ("剧情陈述（E2）", "what_happened"), ("未定义/可争议（E3）", "gaps"),
                               ("破局点（E3）", "breakpoint"), ("反制（E3）", "counter")):
                vals = r.get(key) or []
                if vals:
                    print(f"\n-- {label} --")
                    for v in vals:
                        print(f"  · {v}")
            if r.get("note"):
                print(f"\n-- 备注（原文缺项说明） --\n  · {r['note']}")
            if r.get("clue_refs"):
                print("\n-- 定位线索（E4，不计入证据） --")
                for v in r["clue_refs"]:
                    print(f"  · {v}")
            if r.get("lesson"):
                print(f"\n-- 教训（E3） --\n  · {r['lesson']}")
            print(f"\n-- 模式编号 --\n  {', '.join(r['patterns'])}")
            print("\n-- 去重 --")
            for d in r["dedupe"]:
                line = f"  {d['relation']}"
                if d.get("ref"):
                    line += f" -> {d['ref']}"
                print(line)
                if d.get("what_is_new"):
                    print(f"     增量：{d['what_is_new']}")
            return
    sys.exit(f"未找到 {args.uid}")


def cmd_zodiac(db, args):
    rows = []
    for f in db["families"]:
        games = [r for r in db["records"] if r["uid"] in f["game_ids"]]
        rows.append({
            "branch": f["branch"], "family": f["family"], "core": f["core"],
            "hidden_permission": f["hidden_permission"],
            "games": [{"uid": g["uid"], "name": g["name"], "tier": g["tier"]} for g in games],
            "family_breakpoint": f["family_breakpoint"],
        })
    if args.json:
        emit(args, rows)
        return
    print(f"{'地支':<5}{'生肖':<4}{'机制内核':<26}{'隐藏权限':<8}局数")
    print("-" * 74)
    for r in rows:
        print(f"{r['branch']:<5}{r['family']:<4}{r['core'][:24]:<26}"
              f"{(r['hidden_permission'] or '无'):<8}{len(r['games'])}")
    print("\n用 `family <生肖>` 查看某族全部规则攻击面与所属各局。")


def cmd_family(db, args):
    fam = args.family
    meta = next((f for f in db["families"] if f["family"] == fam), None)
    if not meta:
        sys.exit(f"未知生肖 {fam}（可用：{'、'.join(f['family'] for f in db['families'])}）")
    games = [r for r in db["records"] if r["uid"] in meta["game_ids"]]
    if args.json:
        emit(args, {"meta": meta, "games": games})
        return
    print(f"=== {meta['branch']}·{meta['family']}（机制内核 {meta['core']}，核心定义 line {meta['core_line']}）===")
    print(f"隐藏规则权限：{meta['hidden_permission'] or '无（原文未授权）'}")
    print(f"模式：{', '.join(meta['patterns'])}")
    print("\n-- 家族级攻击面（E3） --")
    for b in meta["family_breakpoint"]:
        print(f"  · {b}")
    print("\n-- 家族级反制（E3） --")
    for c in meta["family_counter"]:
        print(f"  · {c}")
    print("\n-- 所属各局 --")
    for g in games:
        print(f"\n  [{g['uid']}] {g['name']}（{g['tier']}｜{g['host']}｜line {g['lines']}）")
        for v in g["rules"]:
            print(f"    - {v}")
        if g["hidden_rules"]:
            print("    *隐藏规则：")
            for v in g["hidden_rules"]:
                print(f"      - {v}")


def cmd_patterns(db, args):
    from collections import Counter
    cnt = Counter()
    detail = {}
    for r in db["records"]:
        for p in r["patterns"]:
            head = str(p).split(".")[0].upper()
            cnt[head] += 1
            detail.setdefault(head, []).append(f"{r['uid']}:{p}")
    names = {"P1": "规则侦察与隐藏规则识别", "P2": "规则欺骗与反欺骗", "P3": "连环计与局中局",
             "P4": "对赌与承诺设计", "P5": "心理战与攻心"}
    out = {k: {"name": names[k], "count": cnt.get(k, 0), "refs": detail.get(k, [])}
           for k in ("P1", "P2", "P3", "P4", "P5")}
    if args.json:
        emit(args, out)
        return
    for k, v in out.items():
        print(f"{k} {v['name']}：{v['count']} 次")
        print("   " + "、".join(v["refs"][: 12]) + (" …" if len(v["refs"]) > 12 else ""))


def cmd_gaps(db, args):
    rows = [{"uid": r["uid"], "name": r["name"], "gap": g} for r in db["records"] for g in (r.get("gaps") or [])]
    if args.family:
        rows = [x for x in rows if any(r["uid"] == x["uid"] and r.get("family") == args.family for r in db["records"])]
    emit(args, rows, [f"{x['uid']:<6} {x['gap']}" for x in rows])
    if not args.json:
        print(f"\n共 {len(rows)} 条未定义/可争议处（全部为 E3 推断：可作探针清单，不可当事实）。")


def cmd_hidden(db, args):
    rows = [{"uid": r["uid"], "name": r["name"], "lines": r["lines"], "hidden_rule": h}
            for r in db["records"] for h in (r.get("hidden_rules") or [])]
    emit(args, rows, [f"{x['uid']:<6} (line {x['lines']}) {x['hidden_rule']}" for x in rows])
    if not args.json:
        print(f"\n共 {len(rows)} 条 E1 级隐藏规则（均为原文明确写出的「隐藏规则」）。")


def cmd_route(db, args):
    kws = [k.lower() for k in split_keywords(args.keywords)]
    scored = []
    for r in db["records"]:
        hay = record_text(r).lower()
        score = 0
        hits = []
        for k in kws:
            n = hay.count(k)
            if n:
                score += min(n, 3)
                hits.append(k)
        if score:
            scored.append((score, hits, r))
    scored.sort(key=lambda t: (-t[0], t[2]["uid"]))
    out = [{"score": s, "hits": h, "uid": r["uid"], "name": r["name"], "tier": r.get("tier"),
            "patterns": r["patterns"], "first_breakpoint": (r.get("breakpoint") or [None])[0]}
           for s, h, r in scored[: args.limit]]
    if args.json:
        emit(args, out)
        return
    if not out:
        print("没有命中。试试更抽象的词（如 隐藏规则、下注、人数、时间、阵营、判定、门、筹码）。")
        return
    for x in out:
        print(f"[{x['score']}] {x['uid']} {x['name']}（{x['tier']}） 命中={','.join(x['hits'])}")
        print(f"     模式：{', '.join(x['patterns'])}")
        if x["first_breakpoint"]:
            print(f"     破局点：{x['first_breakpoint']}")


def cmd_stats(db, args):
    st = db["stats"]
    extra = {
        "source_file": db["source_file"],
        "baseline_lines": db["baseline_lines"],
        "evidence_policy": db["evidence_policy"],
        "dedupe_rows": None,
        "hidden_rules": sum(len(r.get("hidden_rules") or []) for r in db["records"]),
        "gaps": sum(len(r.get("gaps") or []) for r in db["records"]),
        "breakpoints": sum(len(r.get("breakpoint") or []) for r in db["records"]),
    }
    dm = os.path.join(ROOT, "knowledge", "cases", "dedupe_map.yaml")
    if os.path.exists(dm):
        try:
            import yaml
            with open(dm, encoding="utf-8") as fh:
                dd = yaml.safe_load(fh)
            extra["dedupe_rows"] = len(dd.get("map") or [])
            extra["chapter_clues"] = len(dd.get("chapter_clue_status") or [])
        except Exception:
            pass
    if args.json:
        emit(args, {"stats": st, **extra})
        return
    print("齐夏棋局案例库")
    for k, v in st.items():
        print(f"  {k:<18}{v}")
    for k, v in extra.items():
        print(f"  {k:<18}{v}")


def main() -> int:
    ap = argparse.ArgumentParser(description="齐夏棋局案例库检索 CLI")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="过滤列表")
    p.add_argument("--kind", choices=["zodiac_game", "zodiac_special", "qixia_case", "named_only"])
    p.add_argument("--family")
    p.add_argument("--tier")
    p.add_argument("--pattern")
    p.add_argument("--dedupe", choices=["extends", "duplicate_of", "upgrades_clue", "distinct"])
    p.add_argument("--evidence", choices=["E1", "E2"])
    p.add_argument("--limit", type=int, default=100)

    p = sub.add_parser("search", help="关键词检索")
    p.add_argument("keywords", nargs="+")
    p.add_argument("--field", choices=["all", "name", "rules", "breakpoint"], default="all")
    p.add_argument("--limit", type=int, default=15)

    p = sub.add_parser("show", help="显示单条")
    p.add_argument("uid")

    sub.add_parser("zodiac", help="十二生肖总表")

    p = sub.add_parser("family", help="单家族详情")
    p.add_argument("family")

    p = sub.add_parser("patterns", help="模式统计")

    p = sub.add_parser("gaps", help="未定义/可争议处清单")
    p.add_argument("--family")

    sub.add_parser("hidden", help="E1 隐藏规则清单")

    p = sub.add_parser("route", help="情境路由")
    p.add_argument("keywords", nargs="+")
    p.add_argument("--limit", type=int, default=8)

    sub.add_parser("stats", help="统计")

    args = ap.parse_args()
    db = load()
    handler = {
        "list": cmd_list, "search": cmd_search, "show": cmd_show, "zodiac": cmd_zodiac,
        "family": cmd_family, "patterns": cmd_patterns, "gaps": cmd_gaps,
        "hidden": cmd_hidden, "route": cmd_route, "stats": cmd_stats,
    }[args.cmd]
    handler(db, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
