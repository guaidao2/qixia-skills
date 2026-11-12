#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全包集成验收：结构 / 索引 / 交叉链接 / 计数一致性 / 可复现性。

本脚本只读（除 --repro 会复跑既有生成脚本，产物应逐字节不变），
不修改 P1–P5 与 G1–G12 正文，只做「交付层」校验。

用法：
    python3 scripts/check_package.py                # 结构与索引校验（快）
    python3 scripts/check_package.py --repro        # 追加可复现性校验（慢，约 3s）
    python3 scripts/check_package.py --json         # 机器可读
    python3 scripts/check_package.py --write-manifest PACKAGE.json
退出码：0 全部通过；1 有 FAIL。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable or "python3"
SOLVERS = {"pd", "bayes", "mixed", "signaling", "screening", "mechanism", "backward",
           "sunk", "bluff", "prob", "common", "meta", "metaq", "poker", "audit", "gate"}

results: list[dict] = []


def rec(check: str, ok: bool, detail: str = "", level: str = "FAIL") -> None:
    results.append({"check": check, "status": "PASS" if ok else level, "detail": detail})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


# 包内文件枚举：仓库元数据 .git、字节码、.cairn 内部状态都不属于交付物
EXCLUDE_PARTS = {"__pycache__", ".git", ".cairn"}


def package_files() -> list[Path]:
    out: list[Path] = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.suffix == ".pyc":
            continue
        if any(part in EXCLUDE_PARTS for part in p.relative_to(ROOT).parts):
            continue
        out.append(p)
    return out


# ---------------------------------------------------------------- 1. 结构
REQUIRED = [
    "README.md", "VERSION", "build_package.sh", "INDEX.json", "qixia.py",
    "methodology/README.md", "methodology/00-methodology-overview.md",
    "methodology/01-rule-recon.md", "methodology/02-rule-deception.md",
    "methodology/03-nested-plans.md", "methodology/04-bets-commitment.md",
    "methodology/05-psych-warfare.md", "methodology/patterns.index.json",
    "methodology/casebook.yaml", "methodology/examples/ex01-jile-qianzhuang-walkthrough.md",
    "methodology/scripts/pattern_cli.py", "methodology/scripts/validate.py",
    "skills/game-theory/SKILL.md", "skills/game-theory/AGENT_PLAYBOOK.md",
    "skills/game-theory/SCHEMAS.md", "skills/game-theory/CASES.md",
    "skills/game-theory/checklists.md",
    "scripts/gt/qixia_gt.py", "scripts/gt/run_cases.sh",
    "cases/gt/manifest.json", "knowledge/sources/shiri_baike.txt",
]


def check_structure() -> None:
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    rec("structure:required-files", not missing,
        "全部存在" if not missing else "缺失: " + ", ".join(missing))
    models = [f"skills/game-theory/models/G{i}.md" for i in range(1, 13)]
    lost = [m for m in models if not (ROOT / m).exists()]
    rec("structure:models-G1..G12", not lost,
        "12 个模型文档齐备" if not lost else "缺失: " + ", ".join(lost))
    empties = [rel(p) for p in package_files()
               if b"\x00" not in p.read_bytes()[:1] and p.stat().st_size == 0]
    rec("structure:no-empty-files", not empties,
        "无 0 字节文件" if not empties else "空文件: " + ", ".join(empties))


# ---------------------------------------------------------------- 2. 模式索引
def check_patterns() -> dict:
    path = ROOT / "methodology/patterns.index.json"
    try:
        idx = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        rec("patterns:parse", False, f"{path} 解析失败: {exc}")
        return {}
    pats = idx.get("patterns") or []
    rec("patterns:parse", bool(pats), f"{len(pats)} 个模式, version={idx.get('version')}")
    ids = [p.get("id") for p in pats]
    rec("patterns:unique-ids", len(set(ids)) == len(ids), f"ids={ids}")

    bodies: dict[str, str] = {}
    bad_file, bad_ref, bad_report = [], [], []
    case_dir = ROOT / "cases/gt"
    for p in pats:
        f = p.get("file")
        if not f or not (ROOT / "methodology" / f).exists():
            bad_file.append(f"{p.get('id')}→{f}")
            continue
        body = (ROOT / "methodology" / f).read_text(encoding="utf-8")
        bodies[p["id"]] = body
        # 索引里的模式名必须是该章正文的一级/二级标题
        if p.get("name") and p["name"] not in body:
            bad_file.append(f"{p.get('id')} 名称未出现在 {f} 正文")
        for ref in p.get("gt_refs") or []:
            if not (case_dir / ref).exists():
                bad_ref.append(f"{p.get('id')}→{ref}")
            elif not (ROOT / "reports/gt" / (ref[:-5] + ".md")).exists():
                bad_report.append(f"{p.get('id')}→{ref}")
    bad_link = [f"{c.get('from')}→{c.get('to')}"
                for c in idx.get("cross_links") or []
                if c.get("from") not in ids or c.get("to") not in ids]
    rec("patterns:cross-links", not bad_link and bool(idx.get("cross_links")),
        f"{len(idx.get('cross_links') or [])} 条模式间接口关系全部指向真实模式"
        if not bad_link else "悬空: " + ", ".join(bad_link))
    rec("patterns:file-exists", not bad_file, "5 个模式文件与名称一一对应" if not bad_file else "; ".join(bad_file))
    rec("patterns:gt-refs-exist", not bad_ref, "全部 gt_refs 命中 cases/gt/*.json" if not bad_ref else "; ".join(bad_ref))
    rec("patterns:gt-refs-reported", not bad_report, "全部 gt_refs 已有报告" if not bad_report else "; ".join(bad_report))

    # 子元素 ID（P2.D4、P3.BOC、P4.S1…）必须在本模式结构化数据中真实存在
    valid_sub: dict[str, set[str]] = {}
    for p in pats:
        subs = set()
        for key in ("triggers", "steps", "failure_modes", "counters"):
            for item in p.get(key) or []:
                if isinstance(item, dict) and item.get("id"):
                    subs.add(item["id"])
        for item in p.get("subpatterns") or []:
            text = item.get("id", "") if isinstance(item, dict) else str(item)
            tok = text.split()[0] if text.split() else ""
            if tok:
                subs.add(tok)
        valid_sub[p["id"]] = subs
    return {"index": idx, "valid_sub": valid_sub, "bodies": bodies}


def ref_ok(ref: str, valid_sub: dict[str, set[str]], bodies: dict[str, str]) -> tuple[bool, str]:
    """解析 P? 或 P?.子元素 形式的引用：元素 id → 子模式 id/复合(BOC) → 章节号(4.5) → 正文关键词。"""
    ref = str(ref).strip()
    pid, _, sub = ref.partition(".")
    if pid not in valid_sub:
        return False, "未知模式"
    if not sub or sub in valid_sub[pid]:
        return True, ""
    if len(sub) > 1 and all(ch in valid_sub[pid] for ch in sub):
        return True, ""
    body = bodies.get(pid, "")
    if re.fullmatch(r"\d+(?:\.\d+)+", sub):
        if re.search(r"^#{2,6}\s*" + re.escape(sub.split(".", 1)[1]) + r"\b", body, re.M):
            return True, ""
    if len(sub) >= 2 and sub in body:
        return True, ""
    return False, "模式内无此元素"


# ---------------------------------------------------------------- 3. 案例库
def check_casebook(valid_sub: dict[str, set[str]], bodies: dict[str, str]) -> dict:
    try:
        import yaml
    except ImportError:
        rec("casebook:parse", True, "跳过（无 PyYAML）", level="WARN")
        return {}
    path = ROOT / "methodology/casebook.yaml"
    cb = yaml.safe_load(path.read_text(encoding="utf-8"))
    deep = cb.get("cases") or []
    chapters = cb.get("chapter_cases") or []
    rec("casebook:parse", bool(deep), f"深度案例 {len(deep)} 条 / 章节级 {len(chapters)} 条")

    src = ROOT / "knowledge/sources/shiri_baike.txt"
    lines = src.read_text(encoding="utf-8").splitlines() if src.exists() else []
    bad_line, bad_pat = [], []
    for c in deep:
        rng = str(c.get("line", ""))
        parts = [x.strip() for x in rng.split(",") if x.strip()]
        okfmt, out_of_range = bool(parts), False
        for part in parts:
            m = re.match(r"^(\d+)(?:\s*-\s*(\d+))?$", part)
            if not m:
                okfmt = False
                break
            lo = int(m.group(1)); hi = int(m.group(2) or m.group(1))
            if not (1 <= lo <= hi <= len(lines)):
                out_of_range = True
        if not okfmt:
            bad_line.append(f"{c.get('id')} 行号格式 {rng!r}")
        elif out_of_range:
            bad_line.append(f"{c.get('id')} 行号 {rng} 超出证据快照 {len(lines)} 行")
        for ref in c.get("patterns") or []:
            ok, why = ref_ok(ref, valid_sub, bodies)
            if not ok:
                bad_pat.append(f"{c.get('id')}→{ref} ({why})")
    rec("casebook:line-refs", not bad_line,
        f"全部行号落在证据快照 1..{len(lines)} 内" if not bad_line else "; ".join(bad_line[:6]))
    rec("casebook:pattern-refs", not bad_pat,
        "全部案例→模式引用有效" if not bad_pat else "; ".join(bad_pat[:6]))

    # 章节级索引必须带 evidence 标注（区分标题线索与剧情事实）
    noev = [c.get("id") for c in chapters if not c.get("evidence")]
    rec("casebook:chapter-evidence", not noev,
        f"{len(chapters)} 条章节线索均标注 evidence" if not noev else "缺 evidence: " + ", ".join(map(str, noev[:6])))
    return {"deep": len(deep), "chapters": len(chapters)}


# ---------------------------------------------------------------- 3.5 结构化案例层（knowledge/cases）
EVIDENCE_TAGS = {"E1", "E2", "E3", "E4"}
RELATIONS = {"distinct", "extends", "duplicate_of", "upgraded_to_fact"}


def _walk_records(obj, out: list) -> None:
    if isinstance(obj, dict):
        if obj.get("id"):
            out.append(obj)
        for v in obj.values():
            _walk_records(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_records(v, out)


def check_knowledge_cases(valid_sub: dict[str, set[str]], bodies: dict[str, str]) -> dict:
    d = ROOT / "knowledge/cases"
    if not d.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    src = ROOT / "knowledge/sources/shiri_baike.txt"
    n_src = len(src.read_text(encoding="utf-8").splitlines())

    zp = d / "zodiac_mechanisms.yaml"
    stats = {}
    ids: set[str] = set()
    if zp.exists():
        data = yaml.safe_load(zp.read_text(encoding="utf-8"))
        recs: list = []
        _walk_records(data, recs)
        bad_line, bad_pat, bad_ev = [], [], []
        for r in recs:
            ids.add(str(r["id"]))
            rng = str(r.get("lines") or r.get("line") or "")
            for part in (x.strip() for x in rng.split(",")):
                if not part:
                    continue
                m = re.match(r"^(\d+)(?:\s*-\s*(\d+))?$", part)
                if not m:
                    bad_line.append(f"{r['id']} 行号格式 {rng!r}")
                    break
                lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
                if not (1 <= lo <= hi <= n_src):
                    bad_line.append(f"{r['id']} 行号 {rng} 越界")
                    break
            for ref in r.get("patterns") or []:
                ok, why = ref_ok(ref, valid_sub, bodies)
                if not ok:
                    bad_pat.append(f"{r['id']}→{ref} ({why})")
            # 只有「叶子记录」（带 tier/rules/breakpoint 的具体局）必须带证据标签；
            # 生肖族容器记录（含 games/branch）本身不承载规则原文。
            is_leaf = bool(r.get("tier") or r.get("rules") or r.get("breakpoint"))
            ev = r.get("evidence")
            if is_leaf and ev not in EVIDENCE_TAGS:
                bad_ev.append(f"{r['id']} evidence={ev!r}")
        st = {k: v for k, v in (data or {}).items() if not isinstance(v, (list, dict))}
        rec("cases-layer:zodiac-parse", bool(recs),
            f"{zp.name} 解析出 {len(recs)} 条记录（共 {st.get('version', '?')} 版）")
        rec("cases-layer:zodiac-lines", not bad_line,
            f"全部行号落在证据快照 1..{n_src} 内" if not bad_line else "; ".join(bad_line[:5]))
        rec("cases-layer:zodiac-patterns", not bad_pat,
            "全部 patterns 引用有效" if not bad_pat else "; ".join(bad_pat[:5]))
        rec("cases-layer:zodiac-evidence", not bad_ev,
            "全部记录带 E1–E4 证据标签" if not bad_ev else "; ".join(bad_ev[:5]))
        stats["zodiac_yaml_records"] = len(recs)

    dp = d / "dedupe_map.yaml"
    if dp.exists():
        data = yaml.safe_load(dp.read_text(encoding="utf-8")) or {}
        cb = ROOT / "methodology/casebook.yaml"
        casebook_ids = {str(c.get("id")) for c in (yaml.safe_load(cb.read_text(encoding="utf-8")).get("cases") or [])}
        rel_keys = set((data.get("relations") or {}).keys()) if isinstance(data.get("relations"), dict) else set()
        rel_keys |= {"distinct"}
        mapped = data.get("map") or []
        omitted = data.get("omitted") or []
        clues = data.get("chapter_clue_status") or []

        clue_ids = {str(c.get("id")) for c in clues}
        bad_rel, bad_target, bad_new = [], [], []
        for r in mapped:
            rel = r.get("relation")
            if rel not in rel_keys:
                bad_rel.append(f"{r.get('new_id')} relation={rel!r}")
            tgt = r.get("existing")
            if tgt:
                pool = clue_ids if rel == "upgrades_clue" else casebook_ids
                if tgt not in pool:
                    bad_target.append(f"{r.get('new_id')}→{tgt}")
            if rel in ("extends", "upgrades_clue") and not r.get("what_is_new"):
                bad_new.append(str(r.get("new_id")))
        rec("cases-layer:dedupe-relations", not bad_rel,
            f"{len(mapped)} 条去重登记 relation 合法" if not bad_rel else "; ".join(bad_rel[:5]))
        rec("cases-layer:dedupe-targets", not bad_target,
            "去重目标均指向 casebook 的 C 系列" if not bad_target else "; ".join(bad_target[:5]))
        rec("cases-layer:dedupe-extends-has-delta", not bad_new,
            "extends/upgrades_clue 均写明增量 what_is_new" if not bad_new else "; ".join(bad_new[:5]))

        bad_status = [f"{c.get('id')} status={c.get('status')!r}" for c in clues
                      if c.get("status") not in ("clue_only", "upgraded_to_fact")]
        bad_upg = [str(c.get("id")) for c in clues
                   if c.get("status") == "upgraded_to_fact" and not c.get("upgraded_by")]
        rec("cases-layer:chapter-clue-status", not bad_status,
            f"{len(clues)} 条章节线索状态合法（clue_only / upgraded_to_fact）" if not bad_status else "; ".join(bad_status[:5]))
        rec("cases-layer:chapter-clue-upgrade-provenance", not bad_upg,
            "升级为事实的线索都给出 upgraded_by 出处" if not bad_upg else "; ".join(bad_upg[:5]))

        stats_chk = {
            "extends": sum(1 for r in mapped if r.get("relation") == "extends"),
            "upgrades_clue": sum(1 for r in mapped if r.get("relation") == "upgrades_clue"),
            "duplicate_of": sum(1 for r in mapped if r.get("relation") == "duplicate_of"),
        }
        claimed = data.get("stats") or {}
        drift = [f"{k}: 声明={claimed.get(k)} 实际={v}" for k, v in stats_chk.items()
                 if k in claimed and claimed[k] != v]
        rec("cases-layer:dedupe-stats", not drift,
            "去重统计与实际条目一致" if not drift else "; ".join(drift))
        stats["dedupe_entries"] = len(mapped) + len(omitted) + len(clues)
    return stats


# ---------------------------------------------------------------- 4. GT 案例
def check_gt() -> dict:
    man_path = ROOT / "cases/gt/manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    cases = {p.name for p in (ROOT / "cases/gt").glob("*.json")} - {"manifest.json"}
    missing = [f for f in man if f not in cases]
    extra = sorted(cases - set(man))
    rec("gt:manifest-cases-exist", not missing, f"{len(man)} 条映射全部命中" if not missing else "缺: " + ", ".join(missing))
    rec("gt:covers-all-cases", not extra, "无未登记案例" if not extra else "未登记: " + ", ".join(extra))

    bad_solver, bad_report = [], []
    for fname, solver in man.items():
        if solver not in SOLVERS:
            bad_solver.append(f"{fname}→{solver}")
        base = fname[:-5]
        rep = ROOT / "reports/gt" / f"{base}.md"
        if not rep.exists() or rep.stat().st_size < 200:
            bad_report.append(base)
    rec("gt:manifest-solvers", not bad_solver, "solver 名均在引擎子命令内" if not bad_solver else "; ".join(bad_solver))
    rec("gt:report-per-case", not bad_report, f"{len(man)} 个案例均有报告" if not bad_report else "缺报告: " + ", ".join(bad_report))

    mismatch, thin = [], []
    for fname in man:
        base = fname[:-5]
        case = json.loads((ROOT / "cases/gt" / fname).read_text(encoding="utf-8"))
        rep = ROOT / "reports/gt" / f"{base}.md"
        if not rep.exists():
            continue
        body = rep.read_text(encoding="utf-8")
        head = body.splitlines()[0] if body.splitlines() else ""
        if case.get("name") and case["name"] not in head:
            mismatch.append(f"{base}: 报告标题与 case.name 不符")
        # 单模型报告与 audit 报告的渲染格式不同，但都必须给出「结论 + 数值 + 反制」
        need = ["结论", "数值", "反制"] + ([] if man[fname] in ("audit", "gate") else ["建议动作"])
        if not all(k in body for k in need):
            thin.append(base)
    rec("gt:report-matches-case", not mismatch,
        "每份报告标题都与对应 case.name 一致" if not mismatch else "; ".join(mismatch[:5]))
    rec("gt:report-has-contract-fields", not thin,
        "每份报告都含 结论/数值/反制（单模型另含建议动作）"
        if not thin else "缺字段: " + ", ".join(thin[:5]))
    return {"gt_cases": len(man)}


# ---------------------------------------------------------------- 4.5 L0 能力索引
def actual_counts() -> dict:
    """从产物反推能力计数，用于和 INDEX.json / 文档声明对账。"""
    man = json.loads((ROOT / "cases/gt/manifest.json").read_text(encoding="utf-8"))
    pats = json.loads((ROOT / "methodology/patterns.index.json").read_text(encoding="utf-8"))
    cb = None
    try:
        import yaml
        cb = yaml.safe_load((ROOT / "methodology/casebook.yaml").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        cb = {}
    c = {
        "patterns": len(pats.get("patterns") or []),
        "models": len(list((ROOT / "skills/game-theory/models").glob("G*.md"))),
        "gt_cases": len(man),
        "gt_reports": len(list((ROOT / "reports/gt").glob("*.md"))),
        "deep_cases": len((cb or {}).get("cases") or []),
        "chapter_cases": len((cb or {}).get("chapter_cases") or []),
        "prompt_templates": len([p for p in (ROOT / "prompts").glob("[0-9]*.md")]),
        "solvers": len(SOLVERS - {"audit", "gate"}),
    }
    idx = ROOT / "knowledge/cases/cases.index.json"
    if idx.exists():
        d = json.loads(idx.read_text(encoding="utf-8"))
        recs = d.get("records") or []
        c["case_records"] = len(recs)
        c["zodiac_games"] = (d.get("stats") or {}).get("zodiac_games")
        c["qixia_battles"] = (d.get("stats") or {}).get("qixia_cases")
        c["families"] = len(d.get("families") or [])
    return c


def check_index() -> None:
    path = ROOT / "INDEX.json"
    if not path.exists():
        return
    idx = json.loads(path.read_text(encoding="utf-8"))
    paths = [p for layer in idx.get("layers") or [] for p in layer.get("paths") or []]
    missing = [p for p in paths if not (ROOT / p).exists()]
    rec("index:declared-paths-exist", not missing,
        f"{len(paths)} 条 L0 声明路径全部存在" if not missing else "缺失: " + ", ".join(missing))
    eps = idx.get("entrypoints") or {}
    bad_eps = [f"{k}={v}" for k, v in eps.items() if not (ROOT / v).exists()]
    rec("index:entrypoints-exist", not bad_eps,
        f"{len(eps)} 个入口均存在" if not bad_eps else "缺失: " + ", ".join(bad_eps))

    actual = actual_counts()
    claimed = idx.get("counts") or {}
    drift = [f"{k}: 声明={v} 实际={actual.get(k)}"
             for k, v in claimed.items() if k in actual and actual[k] is not None and actual[k] != v]
    rec("index:counts-match", not drift,
        "INDEX.json 的能力计数与产物一致" if not drift else "; ".join(drift))
    return


def check_cases_index() -> None:
    idxp = ROOT / "knowledge/cases/cases.index.json"
    if not idxp.exists():
        return
    d = json.loads(idxp.read_text(encoding="utf-8"))
    recs = d.get("records") or []
    uids = [r.get("uid") for r in recs]
    rec("cases-index:unique-uids", bool(uids) and len(set(uids)) == len(uids) and all(uids),
        f"{len(uids)} 条记录，uid 唯一" if len(set(uids)) == len(uids) else "uid 缺失或重复")

    src_dir = ROOT / "knowledge/cases"
    src_text = ""
    for y in ("zodiac_mechanisms.yaml", "qixia_battles.yaml"):
        f = src_dir / y
        if f.exists():
            src_text += f.read_text(encoding="utf-8")
    lost = [u for u in uids if f"id: {u}" not in src_text]
    rec("cases-index:records-backed-by-yaml", not lost,
        f"{len(uids)} 条记录均可在 YAML 源中找到" if not lost else "无源记录: " + ", ".join(map(str, lost[:6])))

    # 指纹：对两个源 YAML 的字节流做 sha256，取前 16 位（build_case_index.py 的定义）
    h = hashlib.sha256()
    for y in ("zodiac_mechanisms.yaml", "qixia_battles.yaml"):
        f = src_dir / y
        if f.exists():
            h.update(f.read_bytes())
    fp = h.hexdigest()[:16]
    rec("cases-index:source-fingerprint", d.get("source_fingerprint") == fp,
        f"source_fingerprint={d.get('source_fingerprint')}（实测 {fp}）")

    base = ROOT / "knowledge/sources/shiri_baike.txt"
    n_lines = len(base.read_text(encoding="utf-8").splitlines())
    rec("cases-index:baseline-lines", d.get("baseline_lines") == n_lines,
        f"baseline_lines={d.get('baseline_lines')}（实测 {n_lines}）")

    st = d.get("stats") or {}
    from collections import Counter
    kinds = Counter(str(r.get("kind")) for r in recs)
    actual = {
        "total": len(recs),
        "zodiac_games": kinds["zodiac_game"],
        "zodiac_special": kinds["zodiac_special"],
        "qixia_cases": kinds["qixia_case"],
        "named_only": kinds["named_only"],
        "families": len({r.get("family") for r in recs
                         if r.get("kind") == "zodiac_game" and r.get("family")}),
    }
    fam_listed = len(d.get("families") or [])
    if fam_listed and fam_listed != actual["families"]:
        actual["families"] = actual["families"]        # 以记录反推为准，下面会报差异
    drift = [f"{k}: 声明={st.get(k)} 实际={v}"
             for k, v in actual.items() if k in st and st[k] != v]
    if fam_listed and fam_listed != st.get("families"):
        drift.append(f"families 列表长度={fam_listed} 与 stats={st.get('families')} 不一致")
    rec("cases-index:stats-match", not drift,
        "案例统计（总数/生肖局/特殊局/战例/家族）与记录一致" if not drift else "; ".join(drift))

    # 行号必须落在基线文件内
    bad_line = []
    for r in recs:
        rng = str(r.get("lines") or "")
        for part in (x.strip() for x in rng.split(",")):
            if not part:
                continue
            m = re.match(r"^(\d+)(?:\s*-\s*(\d+))?$", part)
            if not m:
                bad_line.append(f"{r.get('uid')} 行号格式 {rng!r}")
                break
            lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
            if not (1 <= lo <= hi <= n_lines):
                bad_line.append(f"{r.get('uid')} 行号 {rng} 越界")
                break
    rec("cases-index:line-refs", not bad_line,
        f"全部行号落在证据快照 1..{n_lines} 内" if not bad_line else "; ".join(bad_line[:5]))
    return


# ---------------------------------------------------------------- 5. 交叉链接
TOKEN_RE = re.compile(r"`([^`\n]{2,120})`")
LINK_RE = re.compile(r"\[[^\]\n]{1,80}\]\(([^)\n]{1,200})\)")
FILE_EXT = (".md", ".py", ".json", ".yaml", ".yml", ".sh", ".txt")
TOP_DIRS = {"methodology", "skills", "scripts", "cases", "reports", "knowledge",
            "prompts", "docs", "dist", "qixia-skills", "."}


def looks_like_path(tok: str) -> bool:
    """只把「看起来确实是路径」的 token 当引用：避免把 T/R/P/S、--pot/--bet 这类字段列表判成悬空。"""
    if "..." in tok or tok.startswith(("-", "/", "~", "<", ".")):
        return False
    if not re.match(r"^[\w.\-*/{}?]+$", tok):
        return False
    parts = tok.split("/")
    if parts[0] in TOP_DIRS:
        return True
    return parts[-1].endswith(FILE_EXT)
KNOWN_DIRS = ["", "methodology", "methodology/scripts", "methodology/examples",
              "skills/game-theory", "skills/game-theory/models", "scripts/gt", "cases/gt",
              "reports/gt", "knowledge/sources", "knowledge/cases", "prompts"]


EXTERNAL_OUTPUT = ("dist/",)   # 包外构建产物：由 build_package.sh 生成，不随包分发


def resolve(token: str, md_dir: Path) -> bool:
    token = token.split("#")[0].split(":")[0].strip().strip("`'\"")
    if token.startswith(EXTERNAL_OUTPUT):
        return True            # 包外产物（打包后才存在），不算悬空
    if token.startswith(ROOT.name + "/"):
        token = token[len(ROOT.name) + 1:]   # 文档里常从工作区视角写成 qixia-skills/xxx
    if not token or token.startswith(("http", "-", "~", "/")) or " " in token:
        return False
    if token in (".md", "md") or token.startswith(("...",)):
        return False
    cands = [token] if "/" in token else [d + "/" + token if d else token for d in KNOWN_DIRS]
    for cand in cands:
        bases = [ROOT, md_dir]   # 只看包内：解包后必须仍然成立
        for base in bases:
            p = (base / cand)
            if any(ch in cand for ch in "*?{"):
                if list(base.glob(cand)):
                    return True
            elif p.exists():
                return True
    if "/" not in token:
        # 兜底：包内任意位置的同名文件（文档常用裸文件名指代）
        return any(ROOT.rglob(token))
    return False


def check_links() -> dict:
    # 排序：保证 PACKAGE.json 的输出顺序与目录读取顺序无关（可复现打包要求）
    md_files = sorted((p for p in package_files() if p.suffix == ".md"), key=lambda p: rel(p))
    dangling, anchor_bad, bare = [], [], []
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        tokens = sorted(set(TOKEN_RE.findall(text)))
        for raw in tokens:
            tok = raw.strip()
            if not looks_like_path(tok):
                continue
            if not resolve(tok, md.parent):
                # 带目录的引用 = 对包内路径的硬承诺；裸文件名可能只是「你要自己造的文件」
                if "/" in tok:
                    dangling.append(f"{rel(md)} → `{tok}`")
                else:
                    bare.append(f"{rel(md)} → `{tok}`")
        for raw in LINK_RE.findall(text):
            t = raw.strip()
            if t.startswith(("http", "mailto:")):
                continue
            path, _, anchor = t.partition("#")
            if path:
                if not (md.parent / path).exists() and not (ROOT / path).exists():
                    dangling.append(f"{rel(md)} → [{t}]")
                    continue
                target = (md.parent / path) if (md.parent / path).exists() else (ROOT / path)
                if anchor and target.suffix == ".md":
                    heads = {re.sub(r"[^\w\u4e00-\u9fff-]", "", h.strip().lower()).replace(" ", "-")
                             for h in re.findall(r"^#{1,6}\s+(.+)$", target.read_text(encoding="utf-8"), re.M)}
                    if anchor.lower() not in heads:
                        anchor_bad.append(f"{rel(md)} → #{anchor} in {rel(target)}")
    rec("links:no-dangling-references", not dangling,
        f"{len(md_files)} 个 md 文件，引用全部可解析" if not dangling else f"{len(dangling)} 处悬空: " + "; ".join(dangling[:8]))
    rec("links:bare-names", not bare,
        "裸文件名引用均可解析" if not bare else f"{len(bare)} 处裸文件名未落盘（可能是会话内产物）: " + "; ".join(bare[:6]),
        level="WARN")
    rec("links:anchors-resolve", not anchor_bad,
        "锚点全部命中标题" if not anchor_bad else "; ".join(anchor_bad[:6]))
    return {"md_files": len(md_files), "dangling": len(dangling)}


# ---------------------------------------------------------------- 6. 版本与计数
COUNT_CLAIMS = [
    (re.compile(r"(\d+)\s*条深度案例"), "deep", "深度案例"),
    (re.compile(r"(\d+)\s*条章节级"), "chapters", "章节级线索"),
    (re.compile(r"(\d+)\s*个案例"), "gt_cases", "GT 案例"),
    (re.compile(r"(\d+)\s*项自检|(\d+)\s*self-tests"), "selftest", "自检项"),
    (re.compile(r"(\d+)\s*个模式"), "patterns", "模式"),
    (re.compile(r"(\d+)\s*个模型"), "models", "模型"),
    (re.compile(r"(\d+)\s*份报告"), "gt_reports", "GT 报告"),
    (re.compile(r"(\d+)\s*个求解器"), "solvers", "求解器"),
    (re.compile(r"(\d+)\s*条记录"), "case_records", "结构化案例记录"),
    (re.compile(r"(\d+)\s*生肖局"), "zodiac_games", "生肖局"),
    (re.compile(r"(\d+)\s*条战例|(\d+)\s*个战例"), "qixia_battles", "战例"),
]


def check_counts(counts: dict) -> None:
    md_files = [p for p in package_files() if p.suffix == ".md"]
    stale = []
    for md in md_files:
        for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            for rx, key, label in COUNT_CLAIMS:
                for m in rx.finditer(line):
                    got = m.group(1) or (m.group(2) if m.lastindex and m.lastindex >= 2 else None)
                    if got is None:
                        continue
                    want = counts.get(key)
                    if want is not None and int(got) != want:
                        stale.append(f"{rel(md)}:{i} 称 {label}={got}，实际={want}")
    rec("counts:doc-claims-consistent", not stale,
        "文档中的计数与实际产物一致" if not stale else "; ".join(stale[:8]))


def check_versions() -> None:
    ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    idx_ver = json.loads((ROOT / "INDEX.json").read_text(encoding="utf-8")).get("version")
    pat_ver = json.loads((ROOT / "methodology/patterns.index.json").read_text(encoding="utf-8")).get("version")
    pkg = ROOT / "PACKAGE.json"
    vers = {"VERSION": ver, "INDEX.json": idx_ver, "patterns.index.json": pat_ver}
    if pkg.exists():
        vers["PACKAGE.json"] = json.loads(pkg.read_text(encoding="utf-8")).get("version")
    rec("versions:consistent", len(set(vers.values())) == 1,
        " / ".join(f"{k}={v}" for k, v in vers.items()))
    return


# ---------------------------------------------------------------- 6.5 清单完整性
def check_manifest(path: Path) -> None:
    if not path.exists():
        rec("manifest:present", False, f"缺少 {path}")
        return
    mf = json.loads(path.read_text(encoding="utf-8"))
    listed = {f["path"]: f for f in mf.get("files", [])}
    bad = []
    for relpath, meta in listed.items():
        p = ROOT / relpath
        if not p.exists():
            bad.append(f"{relpath} 缺失")
        elif p.stat().st_size != meta["bytes"] or sha256(p) != meta["sha256"]:
            bad.append(f"{relpath} 内容与清单不符")
    actual = {rel(p) for p in package_files()}
    extra = sorted(actual - set(listed) - {rel(path)})
    rec("manifest:files-intact", not bad, f"{len(listed)} 个文件与 PACKAGE.json 逐一匹配"
        if not bad else "; ".join(bad[:6]))
    rec("manifest:no-extra-files", not extra,
        "无清单外文件" if not extra else "清单外: " + ", ".join(extra[:6]))
    rec("manifest:version", mf.get("version") == (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        f"PACKAGE.json version={mf.get('version')}")


# ---------------------------------------------------------------- 7. 可复现性
def run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def hash_tree(globs: tuple[str, ...]) -> dict[str, str]:
    out = {}
    for g in globs:
        for p in ROOT.glob(g):
            out[rel(p)] = sha256(p)
    return out


def check_repro() -> dict:
    # 7.1 模式库自校验
    r = run([PY, "methodology/scripts/validate.py"])
    rec("repro:pattern-validate", r.returncode == 0 and "错误=0" in r.stdout,
        (r.stdout.strip().splitlines() or ["<no output>"])[-1])

    # 7.2 博弈论引擎自检
    r = run([PY, "scripts/gt/qixia_gt.py", "selftest"])
    last = (r.stdout.strip().splitlines() or ["<no output>"])[-1]
    passed = re.search(r"(\d+) passed, (\d+) failed", last)

    # 7.3 20 个案例复跑后报告逐字节不变
    before = hash_tree(("reports/gt/*.md",))
    r2 = run(["sh", "scripts/gt/run_cases.sh"])
    after = hash_tree(("reports/gt/*.md",))
    n_reports = len(after)
    ok_cases = r2.returncode == 0 and before == after
    rec("repro:gt-run-cases-stable", ok_cases,
        (r2.stdout.strip().splitlines() or ["<no output>"])[-1] +
        ("" if before == after else " 但报告内容发生变化"))

    # 7.4 模型文档可由代码注册表重新生成且不变
    before = hash_tree(("skills/game-theory/models/G*.md",))
    r3 = run([PY, "scripts/gt/build_docs.py"])
    after = hash_tree(("skills/game-theory/models/G*.md",))
    rec("repro:models-docs-regenerable", r3.returncode == 0 and before == after,
        "build_docs.py 重跑后 G1–G12 文档逐字节一致" if before == after else "文档发生变化或生成失败")

    # 7.45 结构化案例层：自带审计 + 索引再生成
    if (ROOT / "scripts/cases/audit_cases.py").exists():
        r4 = run([PY, "scripts/cases/audit_cases.py"])
        tail = (r4.stdout.strip().splitlines() or ["<no output>"])[-1]
        ok = r4.returncode == 0 and "错误 0" in tail
        rec("repro:cases-audit", ok, tail)
        if (ROOT / "scripts/cases/build_case_index.py").exists():
            before = hash_tree(("knowledge/cases/*.json", "knowledge/cases/*.md"))
            r5 = run([PY, "scripts/cases/build_case_index.py"])
            after = hash_tree(("knowledge/cases/*.json", "knowledge/cases/*.md"))
            rec("repro:cases-index-regenerable", r5.returncode == 0 and before == after,
                "build_case_index.py 重跑后索引与覆盖矩阵逐字节一致"
                if before == after else "索引发生变化或生成失败")

    # 7.5 双引擎入口冒烟
    smoke = [
        ("pattern_cli:list", [PY, "methodology/scripts/pattern_cli.py", "list"]),
        ("pattern_cli:match", [PY, "methodology/scripts/pattern_cli.py", "match", "对手也在骗我"]),
        ("gt:models", [PY, "scripts/gt/qixia_gt.py", "models"]),
        ("gt:audit", [PY, "scripts/gt/qixia_gt.py", "audit", "--file", "cases/gt/situation_interview_room.json"]),
    ]
    bad = [(n, r.stdout[-120:] + r.stderr[-120:]) for n, c in smoke
           if (r := run(c)).returncode != 0]
    rec("repro:cli-smoke", not bad, "四个 CLI 入口全部可用" if not bad else str(bad))

    selftest = int(passed.group(1)) if passed else 0
    return {"selftest": selftest, "reports": n_reports}


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repro", action="store_true", help="追加可复现性校验")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-manifest", metavar="PATH", help="写入机器可读清单 PACKAGE.json")
    ap.add_argument("--verify-manifest", nargs="?", const="PACKAGE.json", metavar="PATH",
                    help="按清单逐文件校验 sha256 与体积（解包自检用）")
    args = ap.parse_args()

    counts: dict = {}
    check_structure()
    pats = check_patterns()
    valid_sub = pats.get("valid_sub", {})
    counts["patterns"] = len((pats.get("index") or {}).get("patterns") or [])
    counts["models"] = 12
    counts.update(check_casebook(valid_sub, pats.get("bodies", {})))
    counts.update(check_knowledge_cases(valid_sub, pats.get("bodies", {})))
    counts.update(check_gt())
    check_index()
    check_cases_index()
    counts.update(check_links())
    check_versions()
    r = run([PY, "scripts/gt/qixia_gt.py", "selftest"])
    m = re.search(r"(\d+) passed, (\d+) failed", r.stdout)
    counts["selftest"] = int(m.group(1)) if m else None
    rec("selftest:gt-engine", bool(m) and m.group(2) == "0",
        (r.stdout.strip().splitlines() or ["<no output>"])[-1])
    if args.verify_manifest:
        check_manifest(Path(args.verify_manifest))
    if args.repro:
        counts.update(check_repro())
    check_counts(counts)

    fails = [r for r in results if r["status"] == "FAIL"]
    warns = [r for r in results if r["status"] == "WARN"]
    summary = {"root": str(ROOT), "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
               "counts": counts, "checks": results,
               "failed": len(fails), "warned": len(warns), "passed": len(results) - len(fails) - len(warns)}

    if args.write_manifest:
        files = []
        for p in package_files():
            if p.resolve() == Path(args.write_manifest).resolve():
                continue
            files.append({"path": rel(p), "bytes": p.stat().st_size, "sha256": sha256(p)})
        manifest = {
            "name": "qixia-skills",
            "display_name": "齐夏 skills",
            "version": summary["version"],
            "generated_by": "scripts/check_package.py --write-manifest",
            "entrypoints": {
                "readme": "README.md", "skill": "SKILL.md", "quickstart": "QUICKSTART.md",
                "routing": "ROUTING.md", "index": "INDEX.json", "cli": "qixia.py",
                "methodology": "methodology/README.md", "patterns": "methodology/patterns.index.json",
                "casebook": "methodology/casebook.yaml", "gt_engine": "scripts/gt/qixia_gt.py",
                "gt_skill": "skills/game-theory/SKILL.md", "evidence": "knowledge/sources/shiri_baike.txt",
            },
            "capabilities": {
                "methodology_patterns": [p["id"] for p in (pats.get("index") or {}).get("patterns", [])],
                "game_theory_models": [f"G{i}" for i in range(1, 13)],
                "counts": counts,
            },
            "checks": {"passed": summary["passed"], "failed": summary["failed"],
                       "warned": summary["warned"], "items": results},
            "files": files,
            "file_count": len(files),
        }
        with open(args.write_manifest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"齐夏 skills 全包验收 v{summary['version']} @ {ROOT}\n")
        for r in results:
            mark = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL"}[r["status"]]
            print(f"[{mark}] {r['check']:<38} {r['detail']}")
        print(f"\n通过 {summary['passed']} / 警告 {summary['warned']} / 失败 {summary['failed']}")
        if counts:
            print("计数：" + "  ".join(f"{k}={v}" for k, v in counts.items() if v is not None))
        print("\n验收通过 ✅" if not fails else "\n验收失败 ❌")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
