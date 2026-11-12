#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 + 自检 结构化棋局案例库（仅依赖标准库 + PyYAML）。

输入：
  knowledge/cases/zodiac_mechanisms.yaml   十二生肖 37 局 + 2 特殊局
  knowledge/cases/qixia_battles.yaml       齐夏战例 21 条
  methodology/casebook.yaml               既有的 C01–C23 深度案例与 X 系列章节线索（用于去重与线索状态）

输出：
  knowledge/cases/cases.index.json        扁平、可检索的机器索引（CLI 的唯一输入）
  knowledge/cases/dedupe_map.yaml         去重台账（由案例文件的 dedupe 字段机械汇总）
  knowledge/cases/coverage.md             覆盖矩阵（十二生肖 / 战例 / 证据分级 / 去重统计）

用法：
  python3 scripts/cases/build_case_index.py            # 生成全部产物并自检
  python3 scripts/cases/build_case_index.py --check    # 只自检，不写文件
退出码 0 = 通过；1 = 有硬错误。
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))            # qixia-skills/
CASES = os.path.join(ROOT, "knowledge", "cases")
SRC = os.path.join(ROOT, "knowledge", "sources", "shiri_baike.txt")
CASEBOOK = os.path.join(ROOT, "methodology", "casebook.yaml")
ZODIAC = os.path.join(CASES, "zodiac_mechanisms.yaml")
BATTLES = os.path.join(CASES, "qixia_battles.yaml")
INDEX = os.path.join(CASES, "cases.index.json")
DEDUPE = os.path.join(CASES, "dedupe_map.yaml")
COVERAGE = os.path.join(CASES, "coverage.md")

EVIDENCE = {"E1", "E2", "E3", "E4"}
RELATIONS = {"distinct", "extends", "duplicate_of", "upgrades_clue"}
PATTERN_HEAD = {"P1", "P2", "P3", "P4", "P5"}
FAMILY_ORDER = ["鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"]

errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def load_yaml(path: str):
    try:
        import yaml
    except Exception:
        print("[FATAL] 需要 PyYAML：pip install pyyaml", file=sys.stderr)
        raise SystemExit(2)
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def line_refs(value) -> list[int]:
    """解析 "1483-1497,637" -> [1483..1497, 637]"""
    out: list[int] = []
    if value is None:
        return out
    for part in str(value).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            if a.isdigit() and b.isdigit():
                out.extend(range(int(a), int(b) + 1))
            else:
                err(f"无法解析行号区间: {part}")
        elif part.isdigit():
            out.append(int(part))
        else:
            err(f"无法解析行号: {part}")
    return out


def normalize_dedupe(raw) -> list[dict]:
    """dedupe 既支持映射也支持列表；统一成 [{relation, ref, what_is_new}]。"""
    if not raw:
        return [{"relation": "distinct"}]
    items = raw if isinstance(raw, list) else [raw]
    out = []
    for it in items:
        if not isinstance(it, dict) or "relation" not in it:
            err(f"dedupe 结构非法: {it}")
            continue
        rel = it.get("relation")
        if rel not in RELATIONS:
            err(f"未知 dedupe relation: {rel}")
        out.append({"relation": rel, "ref": it.get("ref"), "what_is_new": it.get("what_is_new")})
    return out


def build() -> dict:
    zodiac = load_yaml(ZODIAC)
    battles = load_yaml(BATTLES)
    casebook = load_yaml(CASEBOOK)

    n_lines = sum(1 for _ in open(SRC, encoding="utf-8"))
    cb_cases = {c["id"]: c for c in (casebook.get("cases") or [])}
    cb_names = {str(c.get("name", "")) for c in (casebook.get("cases") or [])}
    chapters = casebook.get("chapter_cases") or []
    chap_ids = {c.get("id") for c in chapters}

    records: list[dict] = []

    # ---------- 十二生肖局 ----------
    for fam in zodiac.get("families") or []:
        if fam.get("family") not in FAMILY_ORDER:
            err(f"{fam.get('id')}: 未知生肖家族 {fam.get('family')}")
        for g in fam.get("games") or []:
            for key in ("id", "name", "tier", "host", "lines"):
                if not g.get(key):
                    err(f"{g.get('id')}: 缺少必填字段 {key}")
            if not g.get("rules") and not g.get("note"):
                err(f"{g.get('id')}: rules 与 note 不能同时为空（无规则原文时必须写明原因）")
            if not (g.get("breakpoint") or g.get("breakpoint_na")):
                err(f"{g.get('id')}: 缺少 breakpoint（E3 破局点）")
            if not g.get("lesson"):
                err(f"{g.get('id')}: 缺少 lesson")
            if g.get("evidence") not in EVIDENCE:
                err(f"{g.get('id')}: evidence 非法 {g.get('evidence')}")
            if str(g.get("name")) in cb_names:
                err(f"{g.get('id')}: 名称与既有 casebook 案例重复（{g.get('name')}）")
            dn = normalize_dedupe(g.get("dedupe"))
            if not g.get("what_is_new") and any(d["relation"] != "distinct" for d in dn):
                # zodiac 文件把 what_is_new 写在 dedupe 同级
                err(f"{g.get('id')}: 非 distinct 关系必须提供 what_is_new")
            dedupe = []
            for d in dn:
                if d["relation"] != "distinct" and not d.get("what_is_new"):
                    d = {**d, "what_is_new": g.get("what_is_new")}
                if d["relation"] != "distinct" and not d.get("what_is_new"):
                    err(f"{g.get('id')}: dedupe 缺少 what_is_new")
                if d.get("ref") and d["ref"] not in cb_cases and d["ref"] not in chap_ids:
                    err(f"{g.get('id')}: dedupe 指向不存在的案例 {d['ref']}")
                dedupe.append(d)
            rec = {
                "uid": g["id"],
                "kind": "zodiac_game",
                "name": g["name"],
                "family": fam.get("family"),
                "branch": fam.get("branch"),
                "core": fam.get("core"),
                "hidden_permission": fam.get("hidden_permission"),
                "tier": g.get("tier"),
                "host": g.get("host"),
                "players": g.get("players"),
                "ticket": g.get("ticket"),
                "status": g.get("status"),
                "note": g.get("note"),
                "clue_refs": g.get("clue_refs") or [],
                "lines": g.get("lines"),
                "rules": g.get("rules") or [],
                "hidden_rules": g.get("hidden_rules") or [],
                "gaps": g.get("gaps") or [],
                "breakpoint": g.get("breakpoint") or [],
                "counter": g.get("counter") or [],
                "lesson": g.get("lesson"),
                "patterns": g.get("patterns") or [],
                "dedupe": dedupe,
                "evidence": g.get("evidence"),
                "source_file": "knowledge/cases/zodiac_mechanisms.yaml",
            }
            records.append(rec)

    # ---------- 特殊局 ----------
    for s in zodiac.get("supplement") or []:
        dn = normalize_dedupe(s.get("dedupe"))
        rec = {
            "uid": s["id"], "kind": "zodiac_special", "name": s["name"],
            "family": "特殊", "branch": None, "core": None, "hidden_permission": None,
            "tier": s.get("tier"), "host": s.get("host"), "players": s.get("players"),
            "ticket": s.get("ticket"), "status": s.get("status"), "note": s.get("note"),
            "clue_refs": s.get("clue_refs") or [], "lines": s.get("lines"),
            "rules": s.get("rules") or [], "hidden_rules": s.get("hidden_rules") or [],
            "gaps": s.get("gaps") or [], "breakpoint": s.get("breakpoint") or [],
            "counter": s.get("counter") or [], "lesson": s.get("lesson"),
            "patterns": s.get("patterns") or [], "dedupe": dn, "evidence": s.get("evidence"),
            "source_file": "knowledge/cases/zodiac_mechanisms.yaml",
        }
        if not s.get("lesson") or not s.get("breakpoint"):
            err(f"{s.get('id')}: supplement 缺少 breakpoint 或 lesson")
        records.append(rec)

    # ---------- 仅存名目 ----------
    for nso in zodiac.get("named_only") or []:
        for key in ("id", "name", "owner", "lines", "note"):
            if not nso.get(key):
                err(f"{nso.get('id')}: named_only 缺少 {key}")
        records.append({
            "uid": nso["id"], "kind": "named_only", "name": nso["name"],
            "family": None, "branch": None, "core": None, "hidden_permission": None,
            "tier": "名目（无规则）", "host": nso.get("owner"), "players": None,
            "ticket": None, "status": "仅存名目", "note": nso.get("note"),
            "clue_refs": [], "lines": nso.get("lines"),
            "rules": [], "hidden_rules": [], "gaps": [], "breakpoint": [],
            "counter": [], "lesson": None, "patterns": [], "dedupe": [{"relation": "distinct"}],
            "evidence": "E1", "source_file": "knowledge/cases/zodiac_mechanisms.yaml",
        })

    # ---------- 齐夏战例 ----------
    for c in battles.get("cases") or []:
        for key in ("id", "name", "category", "lines", "what_happened", "breakpoint", "failure_lesson", "patterns"):
            if not c.get(key):
                err(f"{c.get('id')}: 缺少必填字段 {key}")
        if c.get("evidence") not in EVIDENCE:
            err(f"{c.get('id')}: evidence 非法 {c.get('evidence')}")
        if str(c.get("name")) in cb_names:
            err(f"{c.get('id')}: 名称与既有 casebook 案例重复")
        dedupe = normalize_dedupe(c.get("dedupe"))
        for d in dedupe:
            if d["relation"] != "distinct" and not d.get("what_is_new"):
                err(f"{c.get('id')}: dedupe({d['relation']}) 缺少 what_is_new")
            if d.get("ref") and d["ref"] not in cb_cases and d["ref"] not in chap_ids:
                err(f"{c.get('id')}: dedupe 指向不存在的案例 {d['ref']}")
        rec = {
            "uid": c["id"], "kind": "qixia_case", "name": c["name"],
            "family": None, "branch": None, "core": None, "hidden_permission": None,
            "tier": c.get("category"), "host": None, "players": None, "ticket": None,
            "status": c.get("timeline"), "note": c.get("note"),
            "clue_refs": c.get("clue_refs") or [], "lines": c.get("lines"),
            "rules": c.get("rule_basis") or [], "hidden_rules": [],
            "gaps": [], "breakpoint": c.get("breakpoint") or [],
            "counter": c.get("counter") or [],
            "lesson": "；".join(c.get("failure_lesson") or []),
            "what_happened": c.get("what_happened") or [],
            "patterns": c.get("patterns") or [], "dedupe": dedupe,
            "evidence": c.get("evidence"),
            "source_file": "knowledge/cases/qixia_battles.yaml",
        }
        records.append(rec)

    # ---------- 通用校验 ----------
    seen: set[str] = set()
    for r in records:
        if r["uid"] in seen:
            err(f"重复的 id: {r['uid']}")
        seen.add(r["uid"])
        for p in r["patterns"]:
            head = str(p).split(".")[0].upper()
            if head not in PATTERN_HEAD:
                err(f"{r['uid']}: 非法模式编号 {p}")
        refs = line_refs(r["lines"])
        for n in refs:
            if n < 1 or n > n_lines:
                err(f"{r['uid']}: 行号 {n} 超出基线文件行数 {n_lines}")

    fam_meta = []
    for fam in zodiac.get("families") or []:
        fam_meta.append({
            "id": fam.get("id"),
            "family": fam.get("family"),
            "branch": fam.get("branch"),
            "core": fam.get("core"),
            "core_line": fam.get("core_line"),
            "hidden_permission": fam.get("hidden_permission"),
            "family_breakpoint": fam.get("family_breakpoint") or [],
            "family_counter": fam.get("family_counter") or [],
            "patterns": fam.get("patterns") or [],
            "game_ids": [g.get("id") for g in (fam.get("games") or [])],
        })

    import hashlib
    h = hashlib.sha256()
    for path in (ZODIAC, BATTLES):
        h.update(open(path, "rb").read())

    db = {
        "version": "1.0.0",
        "name": "齐夏棋局案例库 / Qixia Game Case Library",
        "source_fingerprint": h.hexdigest()[:16],
        "source_file": "knowledge/sources/shiri_baike.txt",
        "baseline_lines": n_lines,
        "evidence_policy": "knowledge/cases/evidence_policy.md",
        "evidence_levels": {
            "E1": "rule_text 规则原文（可回溯行号）",
            "E2": "plot_fact 剧情陈述（词条直接写出）",
            "E3": "inference 我方推断（破局点/教训/因果链，不得当事实）",
            "E4": "chapter_title 章节标题线索（不得当事实）",
        },
        "families": fam_meta,
        "classification": zodiac.get("classification"),
        "stats": {
            "total": len(records),
            "zodiac_games": sum(1 for r in records if r["kind"] == "zodiac_game"),
            "zodiac_special": sum(1 for r in records if r["kind"] == "zodiac_special"),
            "qixia_cases": sum(1 for r in records if r["kind"] == "qixia_case"),
            "named_only": sum(1 for r in records if r["kind"] == "named_only"),
            "families": len({r["family"] for r in records if r["family"] in FAMILY_ORDER}),
        },
        "records": records,
    }

    # ---------- 去重台账 ----------
    map_rows = []
    for r in records:
        for d in r["dedupe"]:
            if d["relation"] == "distinct":
                continue
            map_rows.append({
                "new_id": r["uid"],
                "new_name": r["name"],
                "existing": d.get("ref"),
                "relation": d["relation"],
                "what_is_new": d.get("what_is_new"),
            })
    covered = {row["existing"] for row in map_rows}
    omitted = []
    for cid, c in cb_cases.items():
        if cid in covered:
            continue
        # 找出本库中引用了该既有案例的条目（正文出现 C 编号或名称关键片段）
        key = str(c.get("name", ""))[:6]
        referenced = [
            r["uid"] for r in records
            if cid in json.dumps(r, ensure_ascii=False) or (key and key in json.dumps(r, ensure_ascii=False))
        ]
        omitted.append({
            "existing": cid,
            "existing_name": c.get("name"),
            "covered_by": "不重复收录（内容已在 casebook 确认）",
            "reason": "本库只记增量：该条规则原文与结论已在 methodology/casebook.yaml 逐条确认，重复收录会破坏可检索性",
            "referenced_by": referenced,
        })

    clue_status = []
    for ch in chapters:
        status, upgraded_by, note = "clue_only", None, "仅标题级证据，不得据此断言剧情；若需使用请先在规则/时间线原文中另找支撑"
        if ch.get("id") == "X337":
            status, upgraded_by = "upgraded_to_fact", "Q17"
            note = "Q17 以 E1/E2 事实取代标题推测（五城阈值/洗牌/器官筹码/蝼蚁动机）"
        clue_status.append({
            "id": ch.get("id"), "chapter": ch.get("chapter"), "title": ch.get("title"),
            "status": status, "upgraded_by": upgraded_by, "note": note,
        })
    upgraded_ids = {c["upgraded_by"] for c in clue_status if c["upgraded_by"]}
    for uid in upgraded_ids:
        if uid not in {r["uid"] for r in records}:
            err(f"chapter_clue_status 指向不存在的案例 {uid}")

    dedupe_doc = {
        "version": "1.0.0",
        "generated_by": "scripts/cases/build_case_index.py",
        "note": "本文件由案例文件的 dedupe 字段机械汇总生成，勿手改；改来源文件后重跑生成脚本。",
        "relations": {
            "distinct": "与既有案例无重叠（不登记）",
            "extends": "主题相同，本条只记录增量（what_is_new 必填）",
            "duplicate_of": "内容已被既有案例完全覆盖（无增量）",
            "upgrades_clue": "把既有「章节标题线索」升级为 E1/E2 事实（what_is_new 必填）",
        },
        "map": map_rows,
        "omitted": omitted,
        "chapter_clue_status": clue_status,
        "stats": {
            "extends": sum(1 for r in map_rows if r["relation"] == "extends"),
            "upgrades_clue": sum(1 for r in map_rows if r["relation"] == "upgrades_clue"),
            "duplicate_of": sum(1 for r in map_rows if r["relation"] == "duplicate_of"),
            "casebook_cases_total": len(cb_cases),
            "casebook_cases_referenced": len(covered),
            "chapter_clues_total": len(chapters),
            "chapter_clues_upgraded": len(upgraded_ids),
        },
    }
    return {"db": db, "dedupe": dedupe_doc, "casebook": casebook, "records": records}


def render_dedupe_yaml(doc: dict) -> str:
    import yaml
    head = (
        "# 去重台账（dedupe_map）— 自动生成，勿手改\n"
        "# 生成器：scripts/cases/build_case_index.py\n"
        "# 作用：说明本案例库与 methodology/casebook.yaml（C01–C23 深度案例、X 系列章节线索）的边界，\n"
        "#       并逐条登记「新增了什么」，同时把章节标题线索与剧情事实分开。\n"
    )
    return head + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200)


def render_coverage(db: dict, casebook: dict) -> str:
    recs = db["records"]
    lines = []
    lines.append("# 覆盖矩阵（coverage）— 自动生成，勿手改")
    lines.append("")
    lines.append(f"基线：`knowledge/sources/shiri_baike.txt`（{db['baseline_lines']} 行）　"
                 f"生成器：`scripts/cases/build_case_index.py`")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    st = db["stats"]
    lines.append(f"- 生肖局（人/地/天/终极）：**{st['zodiac_games']}** 条")
    lines.append(f"- 特殊局（刑官/神兽第三类）：**{st['zodiac_special']}** 条")
    lines.append(f"- 齐夏战例：**{st['qixia_cases']}** 条")
    lines.append(f"- 仅存名目（词条只给名称、无规则）：**{st.get('named_only', 0)}** 条（已标注证据到此为止）")
    lines.append(f"- 十二生肖家族覆盖：**{st['families']}/12**")
    lines.append(f"- 既有多层案例（casebook C 系列）：**{len(casebook.get('cases') or [])}** 条，"
                 f"章节级线索：**{len(casebook.get('chapter_cases') or [])}** 条")
    lines.append("")
    lines.append("## 十二生肖 × 机制 × 局")
    lines.append("")
    lines.append("| 地支 | 生肖 | 机制内核 | 隐藏规则权限 | 局数 | 局（层级） |")
    lines.append("|---|---|---|---|---|---|")
    for fam in FAMILY_ORDER:
        fam_recs = [r for r in recs if r["family"] == fam]
        core = fam_recs[0]["core"] if fam_recs else "-"
        branch = fam_recs[0]["branch"] if fam_recs else "-"
        perm = fam_recs[0]["hidden_permission"] if fam_recs else None
        names = "、".join(f"{r['name']}（{r['tier']}）" for r in fam_recs)
        lines.append(f"| {branch} | {fam} | {core} | {perm or '无（原文未授权）'} | {len(fam_recs)} | {names} |")
    lines.append("")
    lines.append("## 齐夏战例（Q 系列）")
    lines.append("")
    lines.append("| 编号 | 战例 | 类别 | 时间 | 主要模式 |")
    lines.append("|---|---|---|---|---|")
    for r in recs:
        if r["kind"] != "qixia_case":
            continue
        lines.append(f"| {r['uid']} | {r['name']} | {r['tier']} | {r['status'] or '-'} | "
                     f"{', '.join(r['patterns'])} |")
    lines.append("")
    lines.append("## 证据分级统计")
    lines.append("")
    from collections import Counter
    cnt = Counter(r["evidence"] for r in recs)
    e3_items = sum(len(r.get("breakpoint") or []) + len(r.get("gaps") or []) + len(r.get("counter") or [])
                   for r in recs)
    for k in ("E1", "E2"):
        lines.append(f"- {db['evidence_levels'][k]}：{cnt.get(k, 0)} 条（记录主证据）")
    lines.append(f"- inference 我方推断：每条记录的 `breakpoint/gaps/counter` 均属 E3，"
                 f"共 **{e3_items}** 条推断项；`lesson/failure_lesson` 亦为 E3")
    lines.append(f"- chapter_title 章节标题线索：**0** 条进入本库正文（全部隔离在 dedupe_map 的 chapter_clue_status）")
    lines.append("")
    lines.append("> 说明：`E1/E2` 是本库「可当事实用」的部分；每条记录的破局点/教训/反制均为 `E3`，"
                 "属可执行推演，不得当作剧情转述。章节标题（`E4`）一律不进入本库正文，只在 `dedupe_map.yaml` 的 "
                 "`chapter_clue_status` 中登记状态。")
    lines.append("")
    lines.append("## 隐藏规则清单（E1，原文明确写出的部分）")
    lines.append("")
    for r in recs:
        for h in r["hidden_rules"]:
            lines.append(f"- **{r['uid']} {r['name']}**（line {r['lines']}）：{h}")
    lines.append("")
    lines.append("## 仅存名目（无规则，已标注证据边界）")
    lines.append("")
    lines.append("| 编号 | 名称 | 所属 | 行号 | 说明 |")
    lines.append("|---|---|---|---|---|")
    for r in recs:
        if r["kind"] != "named_only":
            continue
        lines.append(f"| {r['uid']} | {r['name']} | {r['host']} | {r['lines']} | {r.get('note')} |")
    lines.append("")
    lines.append("## 模式覆盖（本库引用的谋略模式）")
    lines.append("")
    pc = Counter()
    for r in recs:
        for p in r["patterns"]:
            pc[str(p).split(".")[0]] += 1
    for k in ("P1", "P2", "P3", "P4", "P5"):
        lines.append(f"- {k}：{pc.get(k, 0)} 次引用")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    check_only = "--check" in sys.argv
    built = build()
    db, dedupe_doc, casebook, recs = built["db"], built["dedupe"], built["casebook"], built["records"]

    # 覆盖率底线
    if db["stats"]["families"] < 12:
        err(f"生肖家族覆盖不足 12：{db['stats']['families']}")
    if db["stats"]["zodiac_games"] < 30:
        warn(f"生肖局数量偏少：{db['stats']['zodiac_games']}")
    if db["stats"]["qixia_cases"] < 15:
        warn(f"齐夏战例数量偏少：{db['stats']['qixia_cases']}")

    if not check_only:
        with open(INDEX, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(db, fh, ensure_ascii=False, indent=1)
        with open(DEDUPE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_dedupe_yaml(dedupe_doc))
        with open(COVERAGE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(render_coverage(db, casebook))

    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[FAIL] {e}")
    st = db["stats"]
    print(f"\n记录={st['total']}（生肖局 {st['zodiac_games']} / 特殊 {st['zodiac_special']} / 战例 {st['qixia_cases']}）"
          f"  家族={st['families']}/12  去重登记={len(dedupe_doc['map'])}  错误={len(errors)}  警告={len(warnings)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
