/*
 * witness_bank  --  DUT.Q dual-sample metastability witness FF'leri (YAPISAL)
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * Her DUT FF ciktisini (dut_q[i]) iki fazda ornekler (Beer/Ginosar ISCAS 2011):
 *   q_a = inverse-clk (negedge clk) ornegi
 *   q_b = GECIKMELI inverse-clk ornegi (keep'd buffer -> silikonda gec-cozulme)
 * Silikonda q_b'nin clock'u q_a'dan biraz gecikmeli -> DUT.Q hala metastable
 * coyuluyorsa q_a ve q_b FARKLI okur -> metastable event (metastable_witness XOR).
 *
 * ⚠️ RTL-sim'de clock-gecikme buffer'i 0 ps (see docs/method.md) -> q_a ve q_b AYNI negedge'de
 * ornekler -> HER ZAMAN esit -> sim'de event YOK (dogru; async veri sahte-event
 * uretmez). Gercek gec-cozulme yakalama = silikon/GL. Named-cell + (* keep *).
 *
 * NOT: inverse-clock (negedge) sampling ikinci bir clock kenari yaratir -> STA/CTS
 * hardening'de yonetilecek (Beer'in kanonik yontemi).
 */
`default_nettype none

module witness_bank #(
    parameter integer NDUT = 4
) (
    input  wire            clk,
    input  wire            rst_n,      // (dfxtp reset'siz; init ilk negedge'de)
    input  wire [NDUT-1:0] dut_q,      // DUT FF bank ciktilari
    output wire [NDUT-1:0] q_a,        // negedge ornek
    output wire [NDUT-1:0] q_b         // gecikmeli-negedge ornek
);

  // Inverse clock (negedge sampling) + gecikmeli kopyasi (silikonda gec-cozulme).
  (* keep = "true" *) wire clk_n;
  (* keep = "true" *) wire clk_n_dly;
  (* keep = "true" *) sky130_fd_sc_hd__inv_1 u_clkinv (.Y (clk_n), .A (clk));
  (* keep = "true" *) sky130_fd_sc_hd__buf_1 u_clkdly (.X (clk_n_dly), .A (clk_n));

  // Her DUT icin iki witness FF: q_a (clk_n) + q_b (clk_n_dly). posedge clk_n =
  // negedge clk. Sim'de clk_n_dly==clk_n (0 ps) -> q_a==q_b.
  genvar i;
  generate
    for (i = 0; i < NDUT; i = i + 1) begin : wff
      (* keep = "true" *) sky130_fd_sc_hd__dfxtp_1 ff_a (
          .Q (q_a[i]), .CLK (clk_n),     .D (dut_q[i]));
      (* keep = "true" *) sky130_fd_sc_hd__dfxtp_1 ff_b (
          .Q (q_b[i]), .CLK (clk_n_dly), .D (dut_q[i]));
    end
  endgenerate

  wire _unused = &{rst_n, 1'b0};

endmodule
