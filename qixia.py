#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""齐夏 skills · 统一前台 CLI（agent 的唯一入口，零第三方依赖）。

设计原则：
  1. 不复制逻辑：模式检索仍由 methodology/scripts/pattern_cli.py 负责，
     博弈论求解仍由 scripts/gt/qixia_gt.py 负责；本文件只做「发现 + 路由 + 透传 + 体检 + 打包」。
  2. 不修改下层：本脚本只读，不写任何既有文件（pack 只读打包）。
  3. 机器可读：所有子命令支持 --json，字段稳定，便于 agent 直接消费。

用法：
    python3 qixia.py status                     # 包里有什么、在哪
    python3 qixia.py where                      # 打印包根目录绝对路径
    python3 qixia.py ask "只有口头规则还有个裁判有最终解释权"
                                                # 一句话 → 该用哪个模式 / 哪个模型（P + G 联合路由）
    python3 qixia.py route "<情境>" --json      # 同上，机器可读
    python3 qixia.py pattern match "<情境>"     # 透传模式库 CLI（list/show/match/check/premortem/counter/eight/route）
    python3 qixia.py run audit --file cases/gt/situation_interview_room.json
                                                # 透传博弈论引擎（models/flow/checklist/pd/bayes/.../audit/selftest）
    python3 qixia.py doctor                     # 全包体检（文件齐备 + 双引擎自检 + 文档命令冒烟）
    python3 qixia.py pack                       # 生成交付压缩包 + sha256
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "INDEX.json"
PATTERN_CLI = ROOT / "methodology" / "scripts" / "pattern_cli.py"
GT_CLI = ROOT / "scripts" / "gt" / "qixia_gt.py"
VALIDATE = ROOT / "methodology" / "scripts" / "validate.py"
PATTERNS_INDEX = ROOT / "methodology" / "patterns.index.json"

PY = sys.executable or "python3"
VERSION = "1.0.0"


# ----------------------------------------------------------------------------- utils
def load_index() -> dict:
    with open(INDEX_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def load_patterns() -> dict:
    with open(PATTERNS_INDEX, encoding="utf-8") as fh:
        return json.load(fh)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def run(script: Path, args: list[str], capture: bool = True) -> tuple[int, str, str]:
    cmd = [PY, str(script), *args]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=capture, text=True)
    out, err = (proc.stdout or ""), (proc.stderr or "")
    if not capture:
        sys.stdout.write(out)
        sys.stderr.write(err)
    return proc.returncode, out, err


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def emit(obj, as_json: bool, human: str) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        print(human)


# ----------------------------------------------------------------------------- status
def cmd_status(args) -> int:
    idx = load_index()
    rows, missing = [], []
    for layer in idx["layers"]:
        for p in layer["paths"]:
            path = ROOT / p
            ok = path.exists()
            size = path.stat().st_size if ok else 0
            rows.append({"layer": layer["id"], "layer_name": layer["name"], "path": p,
                         "exists": ok, "bytes": size})
            if not ok:
                missing.append(p)
    totals = {
        "files_scanned": len(rows),
        "missing": len(missing),
        "patterns": idx.get("counts", {}).get("patterns"),
        "models": idx.get("counts", {}).get("models"),
        "gt_cases": idx.get("counts", {}).get("gt_cases"),
        "deep_cases": idx.get("counts", {}).get("deep_cases"),
        "chapter_cases": idx.get("counts", {}).get("chapter_cases"),
    }
    human = [f"齐夏 skills v{idx.get('version', VERSION)}  @ {ROOT}", ""]
    for layer in idx["layers"]:
        human.append(f"[{layer['id']}] {layer['name']} — {layer['role']}")
        for r in (x for x in rows if x["layer"] == layer["id"]):
            mark = "ok " if r["exists"] else "MISS"
            human.append(f"   {mark} {r['path']:<52} {r['bytes']:>8} B")
        human.append("")
    human.append("计数：" + "  ".join(f"{k}={v}" for k, v in totals.items()))
    if missing:
        human.append("缺失文件：" + ", ".join(missing))
    emit({"root": str(ROOT), "version": idx.get("version", VERSION),
          "layers": rows, "totals": totals, "missing": missing},
         args.json, "\n".join(human))
    return 0 if not missing else 1


# ----------------------------------------------------------------------------- route
def match_patterns(text: str) -> list[dict]:
    """委托给模式库 CLI，保持单一事实来源。"""
    rc, out, _ = run(PATTERN_CLI, ["match", text, "--json"])
    if rc != 0:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def apply_aliases(text: str, idx: dict, pats: list[dict]) -> list[dict]:
    """口语 → 模式 的补齐层：pattern_cli.match 只按触发词打分，日常说法常漏召。
    别名只在模式缺失时补位，且 score 记为 1.0 x 命中词数，hits 以 alias: 前缀标记，便于人工判断。"""
    have = {p["id"] for p in pats}
    low = text.lower()
    for rule in idx["routing"].get("pattern_aliases", []):
        if rule["pattern"] in have:
            continue
        hits = [w for w in rule["words"] if w.lower() in low]
        if not hits:
            continue
        pats.append({"id": rule["pattern"], "name": "", "score": float(len(hits)),
                     "hits": ["alias:" + h for h in hits], "source": "alias"})
        have.add(rule["pattern"])
    return pats


def fallback_patterns_from_models(idx: dict, models: list[dict]) -> list[dict]:
    """P 层全空时的最后兜底：用已命中的模型倒推方法（只给方向，score=0，source=model）。"""
    mapping = idx["routing"].get("model_pattern_fallback", {})
    out, seen = [], set()
    for m in models:
        pid = mapping.get(m["code"])
        if pid and pid not in seen:
            seen.add(pid)
            out.append({"id": pid, "name": "", "score": 0.0,
                        "hits": ["由 " + m["code"] + " 反查(" + m["name"] + ")"], "source": "model"})
    return out


def match_models(text: str, idx: dict) -> list[dict]:
    low = text.lower()
    scored = []
    for m in idx["routing"]["model_keywords"]:
        hits = [kw for kw in m["keywords"] if kw.lower() in low]
        if hits:
            scored.append({"code": m["code"], "name": m["name"], "solver": m["solver"],
                           "score": len(hits), "hits": hits,
                           "case": m.get("case"), "why": m.get("why", "")})
    scored.sort(key=lambda x: (-x["score"], x["code"]))
    return scored


def cmd_route(args) -> int:
    idx = load_index()
    text = args.text.strip()
    pats = apply_aliases(text, idx, match_patterns(text))
    models = match_models(text, idx)
    if not pats and models:
        pats = fallback_patterns_from_models(idx, models)
    # 补全模式的入口命令与 gt 案例
    by_id = {p["id"]: p for p in load_patterns()["patterns"]}
    for p in pats:
        meta = by_id.get(p["id"], {})
        if not p.get("name"):
            p["name"] = meta.get("name", "")
        p["file"] = f"methodology/{meta.get('file', '')}"
        p["risk"] = meta.get("risk")
        p["summary"] = meta.get("summary")
        p["gt_refs"] = meta.get("gt_refs", [])
        p["commands"] = [
            f"python3 qixia.py pattern show {p['id']}",
            f"python3 qixia.py pattern premortem {p['id']}",
            f"python3 qixia.py pattern check {p['id']}",
        ]
    pats.sort(key=lambda x: -x.get("score", 0))
    if len(pats) > args.top:
        pats = pats[: args.top]
    if len(models) > args.top:
        models = models[: args.top]
    # 模型合并：关键词命中的（source=keyword）优先，再追加主模式 gt_refs 反查的（source=pattern）
    by_code = {m["code"]: m for m in idx["routing"]["model_keywords"]}
    merged: list[dict] = []
    seen = set()
    for m in models:
        m["source"] = "keyword"
        merged.append(m)
        seen.add(m["code"])
    for p in pats:
        for ref in p.get("gt_refs", []):
            hit = re.match(r"g([0-9]+)", ref)
            code = "G" + hit.group(1) if hit else ""
            if code in by_code and code not in seen:
                seen.add(code)
                base = by_code[code]
                merged.append({"code": code, "name": base["name"], "solver": base["solver"],
                               "score": 0, "hits": ["来自 " + p["id"] + " 的 gt_refs"],
                               "case": base.get("case"), "why": base.get("why", ""),
                               "source": "pattern"})
    merged.sort(key=lambda x: (-x.get("score", 0), int(x["code"][1:])))
    models = merged[: max(args.top, 3)]
    pattern_derived = any(m["source"] == "pattern" for m in models)
    next_steps = [f"python3 qixia.py pattern eight"]
    next_steps += [c for p in pats for c in p["commands"][:1]]
    next_steps += [f"python3 qixia.py run {m['solver']} --file cases/gt/{m['case']}"
                   for m in models if m.get("case")]
    if args.text:
        next_steps.append(f"python3 qixia.py run audit --file <你的 situation.json>   # 先把局面写成 JSON")

    human = [f'情境：{text}', ""]
    human.append("方法（P，怎么打）：")
    if pats:
        for p in pats:
            human.append(f"  {p['id']} {p['name']}  (score={p.get('score')}, risk={p.get('risk')})")
            if p.get("summary"):
                human.append(f"      {p['summary']}")
            if p.get("hits"):
                human.append(f"      命中触发条件：{', '.join(p['hits'])}")
    else:
        human.append("  （无命中：先跑 `python3 qixia.py pattern eight` 做谋略八问，或补充更具体的情境描述）")
    human += ["", "模型（G，为什么成立/值不值）："]
    if models:
        for m in models:
            tag = "" if m.get("source") == "keyword" else " [pattern]"
            human.append(f"  {m['code']} {m['name']}  →  qixia.py run {m['solver']}"
                         f"   (score={m['score']}, 命中={', '.join(m['hits'])}){tag}")
    else:
        human.append("  （无命中：先跑 `python3 qixia.py run audit --file <situation.json>`，引擎会按关键词自动识别）")
    if pattern_derived:
        human.append("  ↑ 标 [pattern] 的条目由主模式的 gt_refs 反查得到：属于『该模式背后必查的模型』，与关键词命中同等重要。")
    human += ["", "下一步命令："] + [f"  {c}" for c in next_steps]
    human += ["", "说明：P 给方向与失败条件，G 给硬约束与数字；两者冲突时以 G 的判定为准。"]

    emit({"query": text, "patterns": pats, "models": models, "next": next_steps},
         args.json, "\n".join(human))
    return 0


# ----------------------------------------------------------------------------- passthrough
def cmd_pattern(args) -> int:
    if not args.argv:
        rc, out, err = run(PATTERN_CLI, ["--help"], capture=False)
        return rc
    rc, out, err = run(PATTERN_CLI, args.argv, capture=True)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return rc


def cmd_run(args) -> int:
    if not args.argv:
        rc, out, err = run(GT_CLI, ["--help"], capture=False)
        return rc
    rc, out, err = run(GT_CLI, args.argv, capture=True)
    sys.stdout.write(out)
    sys.stderr.write(err)
    return rc


def cmd_where(args) -> int:
    emit({"root": str(ROOT), "index": str(INDEX_FILE), "version": VERSION}, args.json, str(ROOT))
    return 0


# ----------------------------------------------------------------------------- doctor
DOC_PATH_RE = re.compile(
    r"(?<![\w/.-])((?:methodology|skills|scripts|cases|reports|knowledge|prompts)/[A-Za-z0-9_./-]+"
    r"|(?:SKILL|QUICKSTART|ROUTING|README|INDEX)\.(?:md|json)|qixia\.py)")


def check_doc_paths(docs: list[str]) -> list[str]:
    """入口层文档里引用的路径必须真实存在——防止文档与包体漂移（agent 最容易被坏链接卡住）。"""
    missing: list[str] = []
    for doc in docs:
        path = ROOT / doc
        if not path.exists():
            missing.append(doc)
            continue
        text = path.read_text(encoding="utf-8")
        for m in DOC_PATH_RE.finditer(text):
            cand = m.group(0).rstrip(".,;:)")
            nxt = text[m.end():m.end() + 1]
            # 跳过范围/通配/占位写法：G1–G12.md、01…05-*.md、<局名>.md 都不是真实路径
            if any(ch in cand for ch in "*<>{}") or nxt in ("\u2026", "\u2013", "\u2014", "/"):
                continue
            if not (ROOT / cand).exists():
                missing.append(f"{doc} -> {cand}")
    return missing


def cmd_doctor(args) -> int:
    idx = load_index()
    checks: list[dict] = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    add("python>=3.8", sys.version_info >= (3, 8), sys.version.split()[0])
    for name, path in idx["entrypoints"].items():
        p = ROOT / path
        add(f"entrypoint:{name}", p.exists(), path)
    for f in idx["verification"]["required_cases"]:
        add(f"case:{f}", (ROOT / "cases/gt" / f).exists(), f"cases/gt/{f}")
    for f in idx["verification"]["required_reports"]:
        add(f"report:{f}", (ROOT / "reports/gt" / f).exists(), f"reports/gt/{f}")

    rc, out, err = run(PATTERN_CLI, ["list"])
    add("pattern_cli:list", rc == 0 and "P1" in out, (out or err).strip().splitlines()[0] if (out or err) else "")

    rc, out, err = run(VALIDATE, [])
    add("validate.py", rc == 0 and "校验通过" in out, (out or err).strip().splitlines()[-1] if (out or err) else "")

    rc, out, err = run(GT_CLI, ["selftest"])
    tail = (out or err).strip().splitlines()[-1] if (out or err) else ""
    add("qixia_gt:selftest", rc == 0 and "0 failed" in (out or ""), tail)

    rc, out, err = run(GT_CLI, ["audit", "--file", "cases/gt/situation_interview_room.json", "--json"])
    ok = rc == 0
    if ok:
        try:
            ok = "identified" in json.loads(out)
        except json.JSONDecodeError:
            ok = False
    add("gt:audit(situation)", ok, "cases/gt/situation_interview_room.json")

    rc, out, err = run(GT_CLI, ["bluff", "--pot", "100", "--bet", "50"])
    add("gt:bluff(cli-args)", rc == 0, "pot=100 bet=50")

    rc, out, err = run(PATTERN_CLI, ["match", "只有口头规则还有个裁判", "--json"])
    add("pattern_cli:match(--json)", rc == 0 and out.strip().startswith("["), "json array")

    docs = ["SKILL.md", "QUICKSTART.md", "ROUTING.md", "README.md"] + \
           [rel(p) for p in sorted((ROOT / "prompts").glob("*.md"))]
    doc_missing = check_doc_paths(docs)
    add("docs:referenced-paths", not doc_missing,
        "全部存在" if not doc_missing else "缺失:" + ", ".join(doc_missing[:4]))

    # 提示项（不计入通过/失败）：包内 .pyc 由历次运行产生，pack 会自动排除
    pyc = [p for p in ROOT.rglob("*.pyc")]
    warnings = []
    if pyc:
        warnings.append(f"包内有 {len(pyc)} 个 .pyc（运行引擎时会再生成；pack 会自动排除，不影响交付）")

    ok_all = all(c["ok"] for c in checks)
    human = [f"体检结果：{'全部通过 ✅' if ok_all else '存在失败 ❌'}  ({sum(c['ok'] for c in checks)}/{len(checks)})"]
    for c in checks:
        human.append(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['check']:<34} {c['detail']}")
    for w in warnings:
        human.append(f"  [WARN] {w}")
    emit({"ok": ok_all, "checks": checks, "warnings": warnings}, args.json, "\n".join(human))
    return 0 if ok_all else 1


# ----------------------------------------------------------------------------- pack
def cmd_pack(args) -> int:
    out = Path(args.out).resolve() if args.out else ROOT.parent / f"qixia-skills-{VERSION}.zip"
    skip_dirs = {"__pycache__", ".git", ".pytest_cache"}
    skip_suffix = {".pyc", ".pyo", ".DS_Store", ".zip"}
    n = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(ROOT.rglob("*")):
            if path.is_dir() or any(part in skip_dirs for part in path.parts):
                continue
            if path.suffix in skip_suffix or path.name.startswith(".#"):
                continue
            zf.write(path, arcname=str(Path(ROOT.name) / path.relative_to(ROOT)))
            n += 1
    digest = sha256(out)
    info = {"zip": str(out), "entries": n, "bytes": out.stat().st_size, "sha256": digest,
            "verify": [f"unzip -l {out.name} | tail -1", f"sha256sum {out.name}",
                       f"unzip -q {out.name} -d /tmp/qv && python3 /tmp/qv/{ROOT.name}/qixia.py doctor"]}
    human = [f"已生成：{out}",
             f"文件数：{n}    大小：{out.stat().st_size / 1024:.1f} KiB",
             f"sha256：{digest}", "", "验收："] + [f"  {v}" for v in info["verify"]] + \
            ["", "正式交付请改用 `sh build_package.sh`（额外产出 PACKAGE.json / RELEASE / 解包全量自检）。"]
    emit(info, args.json, "\n".join(human))
    return 0


# ----------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="qixia.py",
        description="齐夏 skills 统一前台：status / where / ask / route / pattern / run / doctor / pack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python3 qixia.py status\n"
            "  python3 qixia.py ask \"对手比我强，正面打不过，只能设局\"\n"
            "  python3 qixia.py pattern show P4\n"
            "  python3 qixia.py run audit --file cases/gt/situation_jile_qianzhuang.json\n"
            "  python3 qixia.py doctor && python3 qixia.py pack\n"
        ),
    )
    p.add_argument("--version", action="version", version=f"qixia-skills {VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, fn, help_text in (
        ("status", cmd_status, "包里有什么、在哪（三层文件清单）"),
        ("where", cmd_where, "打印包根目录绝对路径"),
        ("doctor", cmd_doctor, "全包体检：文件齐备 + 双引擎自检 + 命令冒烟"),
    ):
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("--json", action="store_true")
        sp.set_defaults(func=fn)

    sp = sub.add_parser("route", help="情境 → 模式(P) + 模型(G) 联合路由")
    sp.add_argument("text")
    sp.add_argument("--top", type=int, default=3, help="每层最多返回几条（默认 3）")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_route)

    sp = sub.add_parser("ask", help="route 的人类可读别名")
    sp.add_argument("text")
    sp.add_argument("--top", type=int, default=3)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_route)

    sp = sub.add_parser("pattern", help="透传到 methodology/scripts/pattern_cli.py")
    sp.add_argument("argv", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_pattern)

    sp = sub.add_parser("run", help="透传到 scripts/gt/qixia_gt.py")
    sp.add_argument("argv", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("pack", help="生成交付压缩包并输出 sha256")
    sp.add_argument("-o", "--out")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_pack)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
