/*
 * dut_ff_bank  --  4 cesit named-cell DUT FF + referans FF (YAPISAL)
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * Tum DUT FF'ler AYNI skewed-D'yi (d_dut) AYNI CLK'de ornekler; referans FF
 * erken/guvenli D'yi (d_ref) ornekler -> altin referans (detector burada
 * karsilastirir). 4 DUT ayni MANTIKSAL fonksiyonu (plain DFF) tasir; tek fark
 * FIZIKSEL hucre (drive/ic yapi) -> within-die timing mismatch'i bu olcer
 * (docs/method.md).
 *
 * ⚠️ YAPISAL: named-cell structural instantiation + (* keep *) = sentez-savunmasi
 * (Yosys plain-DFF'e cikarim/optimize ETMESIN). RTL-sim'de bu hucreler
 * cells_sim.v functional stub'lari ile derlenir (0 ps, sadece registering);
 * GERCEK timing/setup-hold = GL-sim(SDF)+STA+silikon (docs/method.md).
 *
 * Ozel pinler plain-DFF olacak sekilde tie-off: dfrtp RESET_B=rst_n (temiz
 * init), sdfxtp SCE=0/SCD=0 (scan kapali) -> 4 DUT olcum sirasinda ozdes.
 */
`default_nettype none

module dut_ff_bank (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       d_dut,     // skewed data -> tum DUT FF'ler
    input  wire       d_ref,     // erken/guvenli data -> referans FF
    output wire [3:0] dut_q,     // 4 DUT cesidinin cikisi
    output wire       ref_q      // altin referans
);

  // 4 cesit DUT FF: hepsi d_dut'u clk'de ornekler. Named-cell + keep.
  (* keep = "true" *) sky130_fd_sc_hd__dfxtp_1  ff_dfxtp1 (
      .Q (dut_q[0]), .CLK (clk), .D (d_dut));

  (* keep = "true" *) sky130_fd_sc_hd__dfxtp_2  ff_dfxtp2 (
      .Q (dut_q[1]), .CLK (clk), .D (d_dut));

  (* keep = "true" *) sky130_fd_sc_hd__dfrtp_1  ff_dfrtp1 (
      .Q (dut_q[2]), .CLK (clk), .D (d_dut), .RESET_B (rst_n));

  (* keep = "true" *) sky130_fd_sc_hd__sdfxtp_1 ff_sdfxtp1 (
      .Q (dut_q[3]), .CLK (clk), .D (d_dut), .SCD (1'b0), .SCE (1'b0));

  // Referans FF (plain dfxtp_1): erken tap, skew'suz -> DUT ile karsilastirilir.
  (* keep = "true" *) sky130_fd_sc_hd__dfxtp_1  ff_ref (
      .Q (ref_q), .CLK (clk), .D (d_ref));

endmodule
