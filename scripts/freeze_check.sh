#!/usr/bin/env bash
# Submission FREEZE kapisi -- tek komut, 6 kontrol. Hepsi yesil olmadan submit YOK.
#
# Kullanim (WSL):
#   bash scripts/freeze_check.sh [gate_level_netlist.v]
# Netlist yolu verilmezse 4. kontrol SKIP olur (CI artifact'i indirilmeli).
#
# NOT: cocotb WSL venv'inde (~/.venvs/tt). Windows'ta make yok -> bu script WSL'de
# kosar. CI kontrolu (5) gh CLI ister ve Windows tarafindan da kosulabilir.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
VENV="$HOME/.venvs/tt"
NETLIST="${1:-}"
BRANCH="${BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)}"

pass=0; fail=0; skip=0
declare -a results

check() {  # check <ad> <durum: OK|FAIL|SKIP> [detay]
  local name="$1" status="$2" detail="${3:-}"
  case "$status" in
    OK)   pass=$((pass+1)); results+=("  ✅ $name  $detail") ;;
    SKIP) skip=$((skip+1)); results+=("  ⏭️  $name  $detail") ;;
    *)    fail=$((fail+1)); results+=("  ❌ $name  $detail") ;;
  esac
}

if [ -x "$VENV/bin/python" ]; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
else
  echo "UYARI: $VENV bulunamadi -- cocotb kontrolleri SKIP olacak"
fi

echo "=== 1/6 unit regresyon (33 test) ==="
if command -v make >/dev/null && [ -n "${VIRTUAL_ENV:-}" ]; then
  out=$(cd "$ROOT/test/unit" && bash run_all.sh 2>&1)
  line=$(echo "$out" | grep "UNIT TOTAL" || true)
  if echo "$out" | grep -q "^UNIT_OK"; then check "unit" OK "$line"; else
    check "unit" FAIL "$line"; echo "$out" | tail -12; fi
else
  check "unit" SKIP "make veya venv yok (WSL'de kos)"
fi

echo "=== 2/6 integration (TOP, kucuk param) ==="
if command -v make >/dev/null && [ -n "${VIRTUAL_ENV:-}" ]; then
  out=$(cd "$ROOT/test" && make -B TB_PARAMS="-Ptb.TRIALS=4 -Ptb.CLKS_PER_BIT=8 -Ptb.NCOARSE=2 -Ptb.NFINE=1" 2>&1)
  line=$(echo "$out" | grep -oE "TESTS=[0-9]+ PASS=[0-9]+ FAIL=[0-9]+ SKIP=[0-9]+" | tail -1)
  if ! grep -q failure "$ROOT/test/results.xml" 2>/dev/null && [ -n "$line" ]; then
    check "integration" OK "$line"
  else
    check "integration" FAIL "$line"; echo "$out" | tail -12
  fi
else
  check "integration" SKIP "make veya venv yok"
fi

echo "=== 3/6 host + scripts pytest ==="
py=$(command -v python3 || command -v python)
h=$(cd "$ROOT/host" && "$py" -m pytest -q 2>&1 | tail -1)
s=$(cd "$ROOT/scripts" && "$py" -m pytest -q 2>&1 | tail -1)
if echo "$h" | grep -q "passed" && ! echo "$h" | grep -q "failed" \
   && echo "$s" | grep -q "passed" && ! echo "$s" | grep -q "failed"; then
  check "pytest" OK "host: $h | scripts: $s"
else
  check "pytest" FAIL "host: $h | scripts: $s"
fi

echo "=== 4/6 netlist olcum aparati ==="
if [ -n "$NETLIST" ] && [ -f "$NETLIST" ]; then
  out=$("$py" "$ROOT/scripts/verify_netlist.py" "$NETLIST" 2>&1)
  if echo "$out" | grep -q "^NETLIST_OK"; then
    check "netlist" OK "$(echo "$out" | grep '^NETLIST_OK')"
  else
    check "netlist" FAIL "$(echo "$out" | grep -E '^NETLIST_FAIL|UPSIZE|Error' | head -3)"
  fi
else
  check "netlist" SKIP "netlist yolu verilmedi (gh run download ile indir)"
fi

echo "=== 5/6 CI (gds + precheck + gl_test) ==="
# WSL'de gh kurulu olmayabilir -> Windows kurulumunu (gh.exe) da ara.
GH=$(command -v gh 2>/dev/null || command -v gh.exe 2>/dev/null || \
     ls /mnt/c/Users/*/AppData/Local/Programs/gh/bin/gh.exe 2>/dev/null | head -1 || true)
shopt -s expand_aliases
if [ -n "$GH" ]; then
  gh() { "$GH" "$@"; }
fi
if [ -n "$GH" ]; then
  jobs=$(gh run list --branch "$BRANCH" --workflow gds --limit 1 \
           --json databaseId -q '.[0].databaseId' 2>/dev/null)
  if [ -n "$jobs" ]; then
    st=$(gh run view "$jobs" --json jobs -q '[.jobs[]|"\(.name)=\(.conclusion // .status)"]|join(" ")' 2>/dev/null)
    # viewer HARIC tutulur: Pages deploy edilemiyorsa duser, submission'i etkilemez.
    # "hala kosuyor" (bos conclusion / queued / in_progress) FAIL DEGIL -> SKIP:
    # yoksa devam eden bir job "kirmizi" gibi gorunup yanlis alarm verir.
    rest=$(echo "$st" | tr ' ' '\n' | grep -vE "^viewer=" || true)
    failed=$(echo "$rest" | grep -E "=(failure|cancelled|timed_out|action_required)$" || true)
    pending=$(echo "$rest" | grep -E "=(|queued|in_progress|waiting|pending|requested)$" || true)
    if [ -n "$failed" ]; then
      check "CI" FAIL "run $jobs: $(echo "$failed" | tr '\n' ' ')"
    elif [ -n "$pending" ]; then
      check "CI" SKIP "run $jobs: hala kosuyor -> $(echo "$pending" | tr '\n' ' ')"
    else
      check "CI" OK "run $jobs: $st"
    fi
  else
    check "CI" SKIP "gh run list bos (API arizasi olabilir)"
  fi
else
  check "CI" SKIP "gh CLI yok"
fi

echo "=== 6/6 pinout tutarliligi (RTL <-> info.yaml) ==="
if "$py" - "$ROOT" <<'PY' >/dev/null 2>&1
import re, sys, pathlib
root = pathlib.Path(sys.argv[1])
top = (root/"src/project.v").read_text(encoding="utf-8", errors="replace")
info = (root/"info.yaml").read_text(encoding="utf-8", errors="replace")
m = re.search(r"assign uio_oe\s*=\s*8'b([01]{8})", top)
assert m, "uio_oe sabit atama bulunamadi"
oe = m.group(1)[::-1]
for i, bit in enumerate(oe):
    doc = re.search(rf'uio\[{i}\]:\s*"([^"]*)"', info).group(1)
    if bit == "1":
        assert doc.strip(), f"uio[{i}] output ama info.yaml'da bos"
src_files = re.findall(r'^\s*-\s*"(\w+\.v)"', info, re.M)
for f in src_files:
    assert (root/"src"/f).exists(), f"info.yaml source_files: {f} YOK"
mk = (root/"test/Makefile").read_text(encoding="utf-8", errors="replace")
mk_files = set(re.findall(r"PROJECT_SOURCES\s*\+?=\s*(\w+\.v)", mk))
assert mk_files == set(src_files), f"info.yaml != test/Makefile: {mk_files ^ set(src_files)}"
PY
then check "pinout+sources" OK "uio_oe <-> info.yaml, source_files <-> Makefile"
else check "pinout+sources" FAIL "detay icin scripts/freeze_check.sh 6. blogunu elle kos"
fi

echo
echo "================ FREEZE RAPORU ================"
printf '%s\n' "${results[@]}"
echo "-----------------------------------------------"
echo "PASS=$pass  FAIL=$fail  SKIP=$skip"
if [ "$fail" -eq 0 ] && [ "$skip" -eq 0 ]; then
  echo "FREEZE_OK -- submission kapilari acik"
  exit 0
elif [ "$fail" -eq 0 ]; then
  echo "FREEZE_PARTIAL -- $skip kontrol kosulamadi, submit ONCESI tamamla"
  exit 2
else
  echo "FREEZE_FAIL -- $fail kontrol kirmizi, SUBMIT ETME"
  exit 1
fi
