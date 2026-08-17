/*
 * lfsr  --  16-bit Galois LFSR test-veri ureteci
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * Maximal-length (period 65535) 16-bit Galois LFSR, poly 0xB400 (taps 16,14,13,11).
 * en=1 iken her clock yeni deger; bit_out = state LSB -> DUT/Ref FF'lerin
 * skewed-D test verisi (her trial'da yeni "yakalama"). seed reset'te yuklenir;
 * seed 0 verilse bile all-zero lock-up'a girmemek icin 16'h1'e zorlanir.
 */
`default_nettype none

module lfsr #(
    parameter integer WIDTH = 16        // poly 16-bit'e sabit; WIDTH bilgi amacli
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             en,         // 1: ilerlet, 0: dondur
    input  wire [WIDTH-1:0] seed,       // reset baslangic degeri
    output wire [WIDTH-1:0] value,      // mevcut state
    output wire             bit_out     // test-data biti (state LSB)
);

  localparam [15:0] POLY = 16'hB400;

  reg [15:0] state;

  // seed 0 ise nonzero'ya zorla (Galois LFSR all-zero'da kilitlenir)
  wire [15:0] seed_nz = (seed[15:0] == 16'h0) ? 16'h0001 : seed[15:0];

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      state <= seed_nz;
    else if (en)
      state <= (state[0]) ? ((state >> 1) ^ POLY) : (state >> 1);
  end

  assign value   = state;
  assign bit_out = state[0];

endmodule
