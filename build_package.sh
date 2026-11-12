#!/usr/bin/env bash
# 齐夏 skills · 唯一打包入口
#
#   sh build_package.sh                  # 预检 + 写清单 + 打包 + 解包自检（完整流程）
#   sh build_package.sh --skip-repro     # 跳过耗时的可复现性比对
#   OUT=/tmp/rel sh build_package.sh     # 指定输出目录（默认 ../dist）
#
# 产物（默认 ../dist/）：
#   qixia-skills-<ver>.tar.gz / .zip      完整包（不含 __pycache__ / *.pyc）
#   qixia-skills-<ver>.sha256             两个压缩包的 sha256（可 sha256sum -c）
#   RELEASE-<ver>.md                      版本 / 大小 / 哈希 / 文件数 / 自检结果
#   verify-<ver>.log                      解包自检的完整输出（审计用）
#
# 确定性：固定 mtime、归零属主、名字排序、gzip -n ⇒ 同内容重复打包得到同一 sha256。
set -euo pipefail

NAME=qixia-skills
SELF=$0
ROOT=$(cd "$(dirname "$SELF")" && pwd)
VERSION=$(tr -d '[:space:]' < "$ROOT/VERSION")
PARENT=$(cd "$ROOT/.." && pwd)
OUT=${OUT:-$PARENT/dist}
STAMP=202611110000.00          # 固定时间戳（形成可复现的 mtime）
EPOCH=1762819200               # 与上一行对应的 UTC epoch
SKIP_REPRO=0

# 解释器：优先 $PYTHON，其次 python3 / python（Windows 的 python3 可能只是
# Microsoft Store 占位符，所以必须实跑一次探测；Windows 上通常只有 python）
PY=${PYTHON:-}
if [ -z "$PY" ]; then
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys" >/dev/null 2>&1; then
      PY=$cand
      break
    fi
  done
fi
if [ -z "$PY" ]; then echo "找不到可用的 python3 / python；可用 PYTHON=<解释器路径> 指定" >&2; exit 127; fi

for arg in "$@"; do
  case "$arg" in
    --skip-repro) SKIP_REPRO=1 ;;
    -h|--help) sed -n '2,20p' "$SELF"; exit 0 ;;
    *) echo "未知参数: $arg（可用: --skip-repro / --help）" >&2; exit 2 ;;
  esac
done

mkdir -p "$OUT"
LOG="$OUT/verify-$VERSION.log"
: > "$LOG"
RELEASE="$OUT/RELEASE-$VERSION.md"
TGZ="$OUT/$NAME-$VERSION.tar.gz"
ZIP="$OUT/$NAME-$VERSION.zip"
SUMS="$OUT/$NAME-$VERSION.sha256"

say() { printf '%s\n' "$*" | tee -a "$LOG"; }
die() { say "打包失败 ❌  $*"; exit 1; }
step() { say ""; say "════════ $* ════════"; }

say "齐夏 skills 打包 v$VERSION"
say "包根: $ROOT"
say "输出: $OUT"

# ------------------------------------------------------------------ 0. 清理
step "0. 清理构建垃圾（__pycache__ / *.pyc / 历史 .err）"
find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -type f -name '*.pyc' -delete
find "$ROOT" -type f -name '*.err' -empty -delete
say "已清理；剩余 pyc 数: $(find "$ROOT" -name '*.pyc' | wc -l)"

# ------------------------------------------------------------------ 1. 预检
step "1. 全包验收（check_package.py）"
if [ "$SKIP_REPRO" = "1" ]; then
  "$PY" "$ROOT/scripts/check_package.py" --write-manifest "$ROOT/PACKAGE.json" 2>&1 | tee -a "$LOG" || die "预检未通过"
else
  "$PY" "$ROOT/scripts/check_package.py" --repro --write-manifest "$ROOT/PACKAGE.json" 2>&1 | tee -a "$LOG" || die "预检未通过"
fi
FILES=$("$PY" -c "import json;print(json.load(open('$ROOT/PACKAGE.json'))['file_count'])")

# 预检会 import 引擎、复跑案例，可能重新生成 __pycache__：打包前再清一次
find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$ROOT" -type f -name '*.pyc' -delete
say "预检后清理字节码；剩余 pyc 数: $(find "$ROOT" -name '*.pyc' | wc -l)"

# ------------------------------------------------------------------ 2. 固定时间戳
step "2. 归一化文件时间戳（可复现打包）"
find "$ROOT" -exec touch -t "$STAMP" {} +
say "全部文件 mtime = $STAMP"

# ------------------------------------------------------------------ 3. 打包
step "3. 生成 tar.gz 与 zip"
rm -f "$TGZ" "$ZIP"
( cd "$PARENT" && tar --sort=name --mtime="@$EPOCH" --owner=0 --group=0 --numeric-owner \
      --format=gnu --exclude='*/__pycache__' --exclude='*.pyc' \
      --exclude='*/.git' --exclude='*/.git/*' \
      -cf - "$NAME" | gzip -n -9 > "$TGZ" )
# zip：显式给出「排序后的条目清单」而不是让 zip -r 走目录读取顺序，
# 否则同内容在不同目录（例如解包副本）下会得到不同字节序 ⇒ 不同 sha256
( cd "$PARENT" && find "$NAME" \( -type d -o -type f \) \
      ! -path '*/__pycache__*' ! -name '*.pyc' \
      ! -path '*/.git*' \
    | LC_ALL=C sort | zip -X -q "$ZIP" -@ )
say "tar.gz: $(du -h "$TGZ" | cut -f1)  $(basename "$TGZ")"
say "zip   : $(du -h "$ZIP" | cut -f1)  $(basename "$ZIP")"

# 内容卫生：不得含字节码、绝对路径或 .cairn 内部状态
BAD=$(tar tzf "$TGZ" | grep -E '__pycache__|\.pyc$|^/|\.cairn/|\.git(/|$)' || true)
[ -z "$BAD" ] || die "压缩包含非法条目: $BAD"
CLEAN=$(tar tzf "$TGZ" | wc -l)
say "tar 条目数: $CLEAN（无 pyc / .git / 绝对路径 / .cairn）"

# ------------------------------------------------------------------ 4. 哈希
step "4. 计算 sha256"
( cd "$OUT" && sha256sum "$NAME-$VERSION.tar.gz" "$NAME-$VERSION.zip" > "$SUMS" )
cat "$SUMS" | tee -a "$LOG"
TAR_SHA=$(awk '/\.tar\.gz$/{print $1}' "$SUMS")
ZIP_SHA=$(awk '/\.zip$/{print $1}' "$SUMS")

# ------------------------------------------------------------------ 5. 解包自检
step "5. 解包自检（在临时目录中重跑全部验收）"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
tar xzf "$TGZ" -C "$TMP"
[ -d "$TMP/$NAME" ] || die "解包后没有 $NAME 目录"
say "解包到: $TMP/$NAME"

ORIG_PWD=$(pwd)
cd "$TMP/$NAME" || die "无法进入解包目录"
VF=0
add() { VF=$((VF + 1)); }
CHECKS=""

runcheck() {  # $1=标签 $2...=命令
  label=$1; shift
  add
  say ""
  say "—— $label ——"
  if "$@" >>"$LOG" 2>&1; then
    say "[PASS] $label"
    CHECKS="$CHECKS\n| $label | PASS |"
  else
    say "[FAIL] $label"
    CHECKS="$CHECKS\n| $label | **FAIL** |"
    return 1
  fi
}

runcheck "清单校验（逐文件 sha256）" "$PY" scripts/check_package.py --verify-manifest PACKAGE.json || die "解包后清单校验失败"
runcheck "博弈论引擎自检（selftest）" "$PY" scripts/gt/qixia_gt.py selftest || die "selftest 失败"
runcheck "模式库自校验（validate.py）" "$PY" methodology/scripts/validate.py || die "模式库校验失败"
runcheck "20 个案例复跑（run_cases.sh）" sh scripts/gt/run_cases.sh || die "案例复跑失败"
runcheck "agent 入口体检（qixia.py doctor）" "$PY" qixia.py doctor || die "doctor 失败"
runcheck "zip 完整性（unzip -t）" unzip -t "$ZIP" || die "zip 损坏"
cd "$ORIG_PWD" || die "无法返回原目录"

# 复跑后报告必须与清单逐字节一致（可复现性）
if diff -r "$TMP/$NAME/reports/gt" "$ROOT/reports/gt" >/dev/null 2>&1; then
  add; say ""; say "[PASS] 解包内复跑的报告与源包逐字节一致"; CHECKS="$CHECKS\n| 报告逐字节一致 | PASS |"
else
  add; say ""; say "[FAIL] 解包内复跑的报告与源包不一致"; CHECKS="$CHECKS\n| 报告逐字节一致 | **FAIL** |"; die "报告不可复现"
fi

# ------------------------------------------------------------------ 6. RELEASE
step "6. 写发布记录"
{
  printf '# 齐夏 skills v%s · 发布记录\n\n' "$VERSION"
  printf '| 项 | 值 |\n|---|---|\n'
  printf '| 版本 | %s |\n' "$VERSION"
  printf '| 构建时间 | %s |\n' "$(date -u '+%Y-%m-%d %H:%M:%SZ')"
  printf '| 构建脚本 | `build_package.sh`（确定性：固定 mtime / 归零属主 / 名字排序 / gzip -n） |\n'
  printf '| 包内文件数 | %s（见 `PACKAGE.json` 的 `files[]`） |\n' "$FILES"
  printf '| tar 条目数 | %s |\n' "$CLEAN"
  printf '| tar.gz 大小 | %s B |\n' "$(stat -c %s "$TGZ")"
  printf '| zip 大小 | %s B |\n' "$(stat -c %s "$ZIP")"
  printf '| tar.gz sha256 | `%s` |\n' "$TAR_SHA"
  printf '| zip sha256 | `%s` |\n\n' "$ZIP_SHA"
  printf '## 解包自检（在临时目录解包后重跑）\n\n| 检查 | 结果 |\n|---|---|'
  printf '%b' "$CHECKS"
  printf '\n\n完整命令输出: `%s`（相对本文件）\n\n' "$(basename "$LOG")"
  printf '## 复核命令\n\n```bash\nsha256sum -c %s\ntar xzf %s && cd %s\npython3 scripts/check_package.py --repro --verify-manifest PACKAGE.json\n```\n' \
    "$(basename "$SUMS")" "$(basename "$TGZ")" "$NAME"
} > "$RELEASE"
say "已写: $RELEASE"
say "已写: $LOG"

step "完成"
say "打包成功 ✅"
say "  $TGZ"
say "  $ZIP"
say "  $SUMS"
say "  $RELEASE"
