/*
 * ring_osc  --  std-cell ring oscillator (ASENKRON veri/clock kaynagi, YAPISAL)
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * 3-stage inverting ring (nand2 + 2×inv, kombinasyonel feedback) + ripple
 * divider. clk_out = main clock'a ASENKRON, serbest-kosan -> metastability
 * olcumu icin gerekli async veri (MTBF = e^(Ts/tau)/(Tw·Fc·Fd), Fd = async
 * veri frekansi; senkron LFSR bunu uretemez). Emsal: htfab/cell-tester (TT05,
 * silikon-kanitli). Bkz. docs/method.md.
 *
 * gate=1: osile eder; gate=0: nand ile sabitlenir (durur). div: divider tap
 * secer (0=en hizli .. 7=÷256) -> Fd araligi.
 *
 * ⚠️ YAPISAL + KOMBINASYONEL LOOP: ring hucreleri named-cell + (* keep *);
 * SENTEZDE loop STA'dan MUAF tutulmali (set_disable_timing/false_path) ve
 * opt_clean silmemeli (keep). RTL-sim'de ring cells_sim'de #1 gecikmeli osile
 * eder; GERCEK frekans = silikon/GL (see docs/method.md). Divider normal mantik (keep gerekmez).
 */
`default_nettype none

module ring_osc (
    input  wire       rst_n,
    input  wire       gate,       // 1: osile et, 0: durdur
    input  wire [2:0] div,        // divider tap: 0=en hizli .. 7=en yavas
    output wire       clk_out     // bolunmus async clock
);

  // 3-stage inverting ring: nand2(feedback, gate) + inv + inv.
  // gate=0 -> nand cikisi 1'e sabitlenir -> osilasyon durur (osc=0).
  (* keep = "true" *) wire n0, n1, osc;

  (* keep = "true" *) sky130_fd_sc_hd__nand2_4 u_ro_nand (
      .Y (n0), .A (osc), .B (gate));
  (* keep = "true" *) sky130_fd_sc_hd__inv_4  u_ro_inv0 (
      .Y (n1), .A (n0));
  (* keep = "true" *) sky130_fd_sc_hd__inv_4  u_ro_inv1 (
      .Y (osc), .A (n1));

  // Ripple divider: osc'u 2^(div+1)'e boler; clk_out = counter[div].
  reg [7:0] counter;
  always @(posedge osc or negedge rst_n) begin
    if (!rst_n) counter <= 8'd0;
    else        counter <= counter + 8'd1;
  end

  assign clk_out = counter[div];

endmodule
