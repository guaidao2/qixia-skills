#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验谋略模式库的完整性与自洽性（仅用标准库）。

校验项：
  1. patterns.index.json 可解析，五要素齐全（触发/步骤/失败/反制/案例/checklist）
  2. 每个模式引用的 .md 文件存在且包含对应章节标题
  3. casebook.yaml 的每个 case 都映射到已存在的模式 ID（需 PyYAML，可选）
  4. 交叉链接合法；索引中的案例锚点可在 casebook 中找到
退出码 0 = 全部通过；1 = 有问题。
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INDEX = os.path.join(ROOT, "patterns.index.json")
CASEBOOK = os.path.join(ROOT, "casebook.yaml")

REQUIRED = ["id", "name", "layer", "risk", "summary", "triggers", "steps",
            "failure_modes", "counters", "cases", "checklist"]
MIN_COUNTS = {"triggers": 3, "steps": 5, "failure_modes": 4, "counters": 5, "cases": 3, "checklist": 5}
errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def check_index() -> dict:
    if not os.path.exists(INDEX):
        err(f"缺少索引文件: {INDEX}")
        return {}
    with open(INDEX, encoding="utf-8") as fh:
        db = json.load(fh)
    if not db.get("patterns"):
        err("索引中没有 patterns")
        return db

    ids = []
    for p in db["patterns"]:
        pid = p.get("id", "?")
        ids.append(pid)
        for key in REQUIRED:
            if key not in p:
                err(f"{pid}: 缺少必填字段 {key}")
        for key, minimum in MIN_COUNTS.items():
            got = len(p.get(key) or [])
            if got < minimum:
                err(f"{pid}: {key} 数量 {got} < 最低要求 {minimum}")
        # 子项结构校验
        for t in p.get("triggers") or []:
            if not t.get("keywords"):
                err(f"{pid}/{t.get('id')}: trigger 缺少 keywords（影响 match 检索）")
        for s in p.get("steps") or []:
            for f in ("id", "name", "action", "artifact", "criterion"):
                if not s.get(f):
                    err(f"{pid}/{s.get('id')}: step 缺少 {f}")
        for f in p.get("failure_modes") or []:
            for k in ("id", "name", "signal", "consequence"):
                if not f.get(k):
                    err(f"{pid}/{f.get('id')}: failure_mode 缺少 {k}")
        for c in p.get("counters") or []:
            if not c.get("action"):
                err(f"{pid}/{c.get('id')}: counter 缺少 action")
        if not p.get("file"):
            err(f"{pid}: 缺少 file")
    if len(ids) < 5:
        err(f"模式数量 {len(ids)} < 5（要求覆盖五类谋略模式）")
    if len(set(ids)) != len(ids):
        err("模式 ID 重复")

    # 交叉链接
    for link in db.get("cross_links") or []:
        for side in ("from", "to"):
            if link.get(side) not in ids:
                err(f"cross_link 引用了不存在的模式: {link}")
    return db


def check_markdown(db: dict) -> None:
    for p in db.get("patterns") or []:
        path = os.path.join(ROOT, p.get("file", ""))
        if not os.path.exists(path):
            err(f"{p['id']}: 文件不存在 {path}")
            continue
        text = open(path, encoding="utf-8").read()
        for section, pat in (
            ("触发条件", r"##\s*\d+\.?\s*触发条件|##\s*触发条件"),
            ("执行步骤", r"##\s*\d+\.?\s*执行步骤|##\s*执行步骤|##\s*D\d"),
            ("失败条件", r"##\s*\d+\.?\s*失败条件|##\s*失败条件"),
            ("反制", r"##\s*\d+\.?\s*反制|##\s*反制"),
            ("案例", r"##\s*\d+\.?\s*案例锚点|##\s*案例"),
        ):
            if not re.search(pat, text):
                err(f"{p['id']} ({p['file']}): 缺少「{section}」章节")
        if p["name"] not in text:
            warn(f"{p['id']} ({p['file']}): 文件中未出现模式名称「{p['name']}」")


def check_gt_refs(db: dict) -> None:
    """模式到博弈论案例（../cases/gt）的引用必须真实存在。"""
    gt_dir = os.path.join(os.path.dirname(ROOT), "cases", "gt")
    if not os.path.isdir(gt_dir):
        warn("未找到 ../cases/gt，跳过 gt_refs 校验")
        return
    existing = set(os.listdir(gt_dir))
    for p in db.get("patterns") or []:
        refs = p.get("gt_refs") or []
        if not refs:
            warn(f"{p['id']}: 缺少 gt_refs（与博弈论模型层的对接）")
        for r in refs:
            if r not in existing:
                err(f"{p['id']}: gt_refs 指向不存在的案例 {r}")


def check_casebook(db: dict) -> None:
    if not os.path.exists(CASEBOOK):
        warn("缺少 casebook.yaml，跳过案例交叉校验")
        return
    try:
        import yaml
    except Exception:
        warn("未安装 PyYAML，跳过 casebook.yaml 校验")
        return
    with open(CASEBOOK, encoding="utf-8") as fh:
        cb = yaml.safe_load(fh)
    ids = {p["id"] for p in db.get("patterns") or []}
    seen = []
    for c in cb.get("cases") or []:
        cid = c.get("id")
        seen.append(cid)
        for key in ("name", "patterns", "extracted", "lesson"):
            if not c.get(key):
                err(f"casebook/{cid}: 缺少 {key}")
        for ref in c.get("patterns") or []:
            head = str(ref).split(".")[0].upper()
            if head not in ids:
                err(f"casebook/{cid}: 引用了不存在的模式 {ref}")
    if len(seen) < 10:
        warn(f"casebook 案例数 {len(seen)} 偏少（建议 >=10）")

    chapters = cb.get("chapter_cases") or []
    chap_titles = {str(c.get("title", "")) for c in chapters}
    chap_nums = {int(c.get("chapter")) for c in chapters if c.get("chapter")}
    for c in chapters:
        for ref in c.get("patterns") or []:
            head = str(ref).split(".")[0].upper()
            if head not in ids:
                err(f"casebook/chapter_cases/{c.get('id')}: 引用不存在的模式 {ref}")
        if c.get("evidence") != "chapter_title":
            warn(f"chapter_cases/{c.get('id')}: evidence 应为 chapter_title（标题级证据）")

    case_names = [str(c.get("name", "")) for c in cb.get("cases") or []]

    def grams(text: str, n: int = 3) -> set:
        cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", text)
        return {cleaned[i:i + n] for i in range(max(0, len(cleaned) - n + 1))}

    name_grams = set()
    for n in case_names + [str(t) for t in chap_titles]:
        name_grams |= grams(n)

    for p in db.get("patterns") or []:
        for c in p.get("cases") or []:
            anchor = str(c.get("anchor", ""))
            if not anchor:
                continue
            ok = bool(grams(anchor) & name_grams)
            if not ok:
                m = re.search(r"第\s*(\d+)\s*章", anchor)
                if m and int(m.group(1)) in chap_nums:
                    ok = True
            if not ok:
                warn(f"{p['id']}: 案例锚点「{anchor}」未在 casebook 中登记")
    print(f"casebook: 深度案例 {len(case_names)} 条 / 章节级索引 {len(chapters)} 条")


def main() -> int:
    db = check_index()
    if db:
        check_markdown(db)
        check_casebook(db)
        check_gt_refs(db)
    for w in warnings:
        print(f"[WARN] {w}")
    for e in errors:
        print(f"[FAIL] {e}")
    pats = len(db.get("patterns") or []) if db else 0
    print(f"\n模式数={pats}  错误={len(errors)}  警告={len(warnings)}")
    if errors:
        return 1
    print("校验通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
