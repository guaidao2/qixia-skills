#!/bin/sh
# 批量跑 cases/gt/manifest.json 里的全部案例，输出到 reports/gt/
# 契约：每个 case 必须落盘一份非空报告；失败写 reports/gt/<case>.err 并以非 0 退出。
set -e
DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$DIR"
# 解释器：优先 $PYTHON，其次 python3 / python（Windows 上通常只有 python）
# 注意：Windows 的 python3 可能只是 Microsoft Store 占位符，必须实跑一次探测
PYBIN=${PYTHON:-}
if [ -z "$PYBIN" ]; then
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
      PYBIN=$cand
      break
    fi
  done
fi
if [ -z "$PYBIN" ]; then
  echo "找不到可用的 python3 / python；可用 PYTHON=<解释器路径> 指定" >&2
  exit 127
fi
"$PYBIN" - "$@" <<'PY'
import json, subprocess, sys, os
man = json.load(open("cases/gt/manifest.json", encoding="utf-8"))
only = sys.argv[1:] if len(sys.argv) > 1 else None
fail = 0
ran = 0
for fname, cmd in man.items():
    if only and not any(o in fname for o in only):
        continue
    ran += 1
    base = fname[:-5]
    out = f"reports/gt/{base}.md"
    err = f"reports/gt/{base}.err"
    r = subprocess.run([sys.executable, "scripts/gt/qixia_gt.py", cmd, "--file", f"cases/gt/{fname}", "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        open(err, "w", encoding="utf-8", newline="\n").write(r.stderr)
        print(f"FAIL {fname}: {r.stderr.strip()[:300]}")
        fail += 1
        continue
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        # 兜底：solver 未写 --out 时用 stdout 落盘，保证「每个 case 一份报告」
        if r.stdout.strip():
            open(out, "w", encoding="utf-8", newline="\n").write(r.stdout)
        else:
            open(err, "w", encoding="utf-8", newline="\n").write("empty report\n")
            print(f"FAIL {fname}: 报告为空")
            fail += 1
            continue
    if os.path.exists(err):
        os.remove(err)          # 清掉历史失败留下的过期 stderr
    print(f"OK   {fname} -> {out}")
print(f"\n{ran} cases, {fail} failed")
sys.exit(1 if fail else 0)
PY
