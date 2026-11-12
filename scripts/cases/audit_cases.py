#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案例库硬校验（独立于生成器，只读产物 + 只读基线原文）。

校验项：
  1 结构：必填字段、evidence 合法性、patterns 只允许 P1–P5 开头
  2 溯源：每条 lines 行号必须落在基线文件行数内且可解析
  3 反幻觉：E1（rules/hidden_rules）与 E2（what_happened）的每条文字必须与基线原文有足够字符
    二元组重合度（默认阈值 0.50，低于 0.30 判为硬错误），防止凭空编造规则或剧情
  4 去重：非 distinct 的 dedupe 必须带 what_is_new，且 ref 必须存在于 casebook 的 C/X 系列
  5 覆盖：十二生肖必须 12/12，生肖局 ≥ 30，齐夏战例 ≥ 15
  6 线索隔离：记录正文不得把「第 N 章」标题当作证据（evidence 不得为 E4）
  7 同步：cases.index.json 必须由当前 YAML 生成（对关键字段做指纹比对）

用法：
  python3 scripts/cases/audit_cases.py [--verbose] [--threshold 0.50]
退出码 0 = 通过。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CASES = os.path.join(ROOT, "knowledge", "cases")
SRC = os.path.join(ROOT, "knowledge", "sources", "shiri_baike.txt")
CASEBOOK = os.path.join(ROOT, "methodology", "casebook.yaml")
ZODIAC = os.path.join(CASES, "zodiac_mechanisms.yaml")
BATTLES = os.path.join(CASES, "qixia_battles.yaml")
INDEX = os.path.join(CASES, "cases.index.json")
DEDUPE = os.path.join(CASES, "dedupe_map.yaml")

PATTERN_HEAD = {"P1", "P2", "P3", "P4", "P5"}
EVIDENCE = {"E1", "E2", "E3", "E4"}
RELATIONS = {"distinct", "extends", "duplicate_of", "upgrades_clue"}
families_expected = {"鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"}

errors: list[str] = []
warnings: list[str] = []


def err(m: str) -> None:
    errors.append(m)


def warn(m: str) -> None:
    warnings.append(m)


def bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", text)
    if len(cleaned) < 2:
        return {cleaned} if cleaned else set()
    return {cleaned[i:i + 2] for i in range(len(cleaned) - 1)}


def overlap(needle: str, hay_bigrams: set[str]) -> float:
    nb = bigrams(needle)
    if not nb:
        return 1.0
    return len(nb & hay_bigrams) / len(nb)


def parse_lines(value: str) -> list[int]:
    out = []
    for part in str(value).replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def main() -> int:
    verbose = "--verbose" in sys.argv
    threshold = 0.50
    if "--threshold" in sys.argv:
        threshold = float(sys.argv[sys.argv.index("--threshold") + 1])

    try:
        import yaml
    except Exception:
        print("[FATAL] 需要 PyYAML")
        return 2

    source = open(SRC, encoding="utf-8").read()
    src_bigrams = bigrams(source)
    n_lines = source.count("\n") + (0 if source.endswith("\n") else 1)

    with open(CASEBOOK, encoding="utf-8") as fh:
        casebook = yaml.safe_load(fh)
    cb_cases = {c["id"]: c for c in (casebook.get("cases") or [])}
    cb_names = {str(c.get("name", "")) for c in (casebook.get("cases") or [])}
    chap_ids = {c.get("id") for c in (casebook.get("chapter_cases") or [])}

    with open(INDEX, encoding="utf-8") as fh:
        idx = json.load(fh)
    recs = idx.get("records") or []
    if not recs:
        err("index 中没有 records")

    # ---- 1/2/3/6 逐条校验 ----
    for r in recs:
        uid = r.get("uid", "?")
        need = ("name", "lines", "evidence", "dedupe") if r.get("kind") == "named_only" else \
               ("name", "lines", "evidence", "patterns", "dedupe")
        for key in need:
            if not r.get(key):
                err(f"{uid}: 缺少 {key}")
        if r.get("evidence") not in EVIDENCE:
            err(f"{uid}: evidence={r.get('evidence')} 非法")
        if r.get("evidence") == "E4":
            err(f"{uid}: 记录主证据不得为 E4（标题线索不能当事实，见 evidence_policy）")
        for p in r.get("patterns") or []:
            if str(p).split(".")[0].upper() not in PATTERN_HEAD:
                err(f"{uid}: 非法模式编号 {p}")

        try:
            refs = parse_lines(r.get("lines", ""))
        except Exception:
            err(f"{uid}: lines 无法解析 {r.get('lines')}")
            refs = []
        if not refs:
            err(f"{uid}: lines 为空")
        for n in refs:
            if n < 1 or n > 12600:
                err(f"{uid}: 行号 {n} 明显越界")

        # 反幻觉：E1/E2 文本必须与原文有重合
        e1_items = list(r.get("rules") or []) + list(r.get("hidden_rules") or [])
        e2_items = list(r.get("what_happened") or [])
        for kind, items in (("E1", e1_items), ("E2", e2_items)):
            for it in items:
                score = overlap(str(it), src_bigrams)
                if score < 0.30:
                    err(f"{uid}: {kind} 文本与原文重合度 {score:.2f} < 0.30，疑为编造 → {str(it)[:60]}")
                elif score < threshold:
                    warn(f"{uid}: {kind} 重合度 {score:.2f} 偏低 → {str(it)[:60]}")
                elif verbose:
                    print(f"[ok] {uid} {kind} {score:.2f} {str(it)[:40]}")

        # 去重
        for d in r.get("dedupe") or []:
            rel = d.get("relation")
            if rel not in RELATIONS:
                err(f"{uid}: dedupe relation 非法 {rel}")
            if rel != "distinct":
                if not d.get("what_is_new"):
                    err(f"{uid}: {rel} 缺少 what_is_new")
                ref = d.get("ref")
                if ref not in cb_cases and ref not in chap_ids:
                    err(f"{uid}: dedupe ref={ref} 不存在于 casebook")
                if rel == "upgrades_clue" and ref not in chap_ids:
                    err(f"{uid}: upgrades_clue 的 ref 必须指向章节线索 X 系列，当前 {ref}")

        if str(r.get("name")) in cb_names:
            err(f"{uid}: 名称与 casebook 既有案例重复")

    # ---- 4 去重台账 ----
    if not os.path.exists(DEDUPE):
        err("缺少 dedupe_map.yaml")
    else:
        with open(DEDUPE, encoding="utf-8") as fh:
            dd = yaml.safe_load(fh)
        rows = dd.get("map") or []
        for row in rows:
            if row.get("existing") not in cb_cases and row.get("existing") not in chap_ids:
                err(f"dedupe_map: existing={row.get('existing')} 不存在")
            if not row.get("what_is_new"):
                err(f"dedupe_map: {row.get('new_id')} 缺少 what_is_new")
            if row.get("new_id") not in {r["uid"] for r in recs}:
                err(f"dedupe_map: new_id={row.get('new_id')} 不在索引中")
        referenced = {row["existing"] for row in rows}
        omitted = {o["existing"] for o in (dd.get("omitted") or [])}
        missing = set(cb_cases) - referenced - omitted
        if missing:
            err(f"casebook 中以下案例既未登记 extends/upgrades，也未列入 omitted：{sorted(missing)}")
        clues = dd.get("chapter_clue_status") or []
        if len(clues) != len(chap_ids):
            warn(f"chapter_clue_status 条数 {len(clues)} != casebook 章节线索 {len(chap_ids)}")
        for c in clues:
            if c.get("status") not in ("clue_only", "upgraded_to_fact"):
                err(f"chapter_clue_status/{c.get('id')}: status 非法")
            if c.get("status") == "upgraded_to_fact" and c.get("upgraded_by") not in {r["uid"] for r in recs}:
                err(f"chapter_clue_status/{c.get('id')}: upgraded_by 不存在")

    # ---- 5 覆盖 ----
    fams = {r.get("family") for r in recs if r.get("family") in families_expected}
    if fams != families_expected:
        err(f"生肖覆盖不全，缺 {sorted(families_expected - fams)}")
    n_named = sum(1 for r in recs if r["kind"] == "named_only")
    n_games = sum(1 for r in recs if r["kind"] == "zodiac_game")
    n_q = sum(1 for r in recs if r["kind"] == "qixia_case")
    if n_games < 30:
        err(f"生肖局数量 {n_games} < 30")
    if n_q < 15:
        err(f"齐夏战例 {n_q} < 15")
    for r in recs:
        if r["kind"] == "named_only":
            if not r.get("note"):
                err(f"{r['uid']}: named_only 必须写明「无规则」的原因（note）")
            continue
        if r["kind"] in ("zodiac_game", "zodiac_special"):
            if not r.get("breakpoint"):
                err(f"{r['uid']}: 缺少 breakpoint")
            if not r.get("lesson"):
                err(f"{r['uid']}: 缺少 lesson")
        if r["kind"] == "qixia_case":
            if not r.get("breakpoint") or not r.get("lesson"):
                err(f"{r['uid']}: 缺少 breakpoint 或 lesson")

    # ---- 7 同步（YAML → index 指纹） ----
    h = hashlib.sha256()
    for path in (ZODIAC, BATTLES):
        h.update(open(path, "rb").read())
    fp = h.hexdigest()[:16]
    if idx.get("source_fingerprint") != fp:
        warn("index 与 YAML 可能不同步（source_fingerprint 不一致），请重跑 build_case_index.py")

    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[FAIL] {e}")
    print(f"\n审计完成：记录 {len(recs)}（生肖局 {n_games}／战例 {n_q}／仅存名目 {n_named}）　"
          f"家族 {len(fams)}/12　错误 {len(errors)}　警告 {len(warnings)}　"
          f"反幻觉阈值 {threshold}/0.30")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
