#!/usr/bin/env bash
# Tum unit bloklarini sirayla kosar ve tek satir ozet basar.
# Kullanim (WSL):  source ~/.venvs/tt/bin/activate && ./run_all.sh
# NOT: dongu icinde degisken adi BLK -- MSYS2/Windows bash'te $blk bosalma tuzagi
# yasandigi icin bloklar acik listeyle ve set -u ile kosuluyor.
set -uo pipefail
cd "$(dirname "$0")"

# "blok:SIMLIB" -- yapisal bloklar named-cell stub'lari (cells_sim) ister.
BLOCKS=(
  "uart_tx:"
  "sweep_ctrl:"
  "detector:"
  "lfsr:"
  "uart_packet:uart_tx"
  "dut_ff_bank:cells_sim"
  "delay_line:cells_sim"
  "ring_osc:cells_sim"
  "metastable_witness:"
  "witness_bank:cells_sim"
)

total=0; passed=0; failed=0; fail_list=()
for entry in "${BLOCKS[@]}"; do
  blk="${entry%%:*}"; extra="${entry#*:}"
  args=("BLK=$blk")
  case "$blk" in
    uart_packet) args+=("EXTRA=$extra") ;;
    *) [ -n "$extra" ] && args+=("SIMLIB=$extra") ;;
  esac
  out=$(make -B "${args[@]}" 2>&1)
  line=$(echo "$out" | grep -oE "TESTS=[0-9]+ PASS=[0-9]+ FAIL=[0-9]+" | tail -1)
  if [ -z "$line" ]; then
    echo "  $blk: KOSMADI (derleme/altyapi hatasi)"
    echo "$out" | tail -5 | sed 's/^/      /'
    failed=$((failed + 1)); fail_list+=("$blk(no-run)"); continue
  fi
  t=$(echo "$line" | sed -E 's/TESTS=([0-9]+).*/\1/')
  p=$(echo "$line" | sed -E 's/.*PASS=([0-9]+).*/\1/')
  f=$(echo "$line" | sed -E 's/.*FAIL=([0-9]+)/\1/')
  total=$((total + t)); passed=$((passed + p)); failed=$((failed + f))
  [ "$f" -ne 0 ] && fail_list+=("$blk")
  printf "  %-20s TESTS=%s PASS=%s FAIL=%s\n" "$blk" "$t" "$p" "$f"
done

echo "----"
echo "UNIT TOTAL: TESTS=$total PASS=$passed FAIL=$failed"
if [ "$failed" -eq 0 ] && [ "$total" -gt 0 ]; then
  echo "UNIT_OK"
else
  echo "UNIT_FAIL: ${fail_list[*]:-?}"
  exit 1
fi
