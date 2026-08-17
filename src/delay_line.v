/*
 * delay_line  --  coarse+fine swept-tap dijital delay line (YAPISAL, KRITIK BLOK)
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * d_in'i kademeli geciktirir; tap_sel bir tap noktasini d_out'a yonlendirir.
 * Her segment = 1 coarse (dlymetal6s2s_1 ~87ps) + NFINE fine (buf_1 ~54ps);
 * hepsi NON-INVERTING (kullanici karari 2026-07-16) -> d_out polaritesi TUM
 * tap'lerde tutarli (inv olsaydi tap-parity ters cevirir = sahte mismatch bug).
 *
 * tap_sel = 0 .. NTAP-1 monoton artan gecikme (host kalibrasyonu ps'e cevirir,
 * docs/method.md). NTAP = NCOARSE*(NFINE+1)+1 (chain[0]=d_in dahil).
 *
 * ⚠️ YAPISAL: named-cell + (* keep *) + dly_ prefix (config RSZ_DONT_TOUCH_RX
 * "^dly_"). RTL-sim'de hucreler cells_sim.v ile 0 ps (assign X=A) -> d_out
 * KOMBINASYONEL d_in (see docs/method.md). GERCEK gecikme/setup-hold = GL-sim(SDF)+STA+silikon.
 *
 * NOT: NTAP/TAP_W tureilmis parametreler; NCOARSE/NFINE override et, digerlerine
 * DOKUNMA (kendiliginden turer).
 */
`default_nettype none

module delay_line #(
    parameter integer NCOARSE = 8,                         // coarse kademe sayisi
    parameter integer NFINE   = 4,                         // coarse basina fine buf
    parameter integer NTAP    = NCOARSE*(NFINE+1) + 1,     // toplam tap (chain[0] dahil)
    parameter integer TAP_W   = $clog2(NTAP)               // tap_sel genisligi
) (
    input  wire             d_in,
    input  wire [TAP_W-1:0] tap_sel,     // 0..NTAP-1
    output wire             d_out
);

  localparam integer NCELL = NCOARSE*(NFINE+1);   // toplam gecikme hucresi

  // chain[0]=d_in; her hucre bir sonraki node'u surer. keep -> optimize edilmez.
  (* keep = "true" *) wire [NTAP-1:0] chain;
  assign chain[0] = d_in;

  genvar s, f;
  generate
    for (s = 0; s < NCOARSE; s = s + 1) begin : dly_seg
      localparam integer BASE = s*(NFINE+1);      // segment giris index'i

      // coarse kademe: chain[BASE] -> chain[BASE+1]
      (* keep = "true" *) sky130_fd_sc_hd__dlymetal6s2s_1 dly_coarse (
          .X (chain[BASE+1]),
          .A (chain[BASE])
      );

      // NFINE fine buf: chain[BASE+1+f] -> chain[BASE+2+f]
      for (f = 0; f < NFINE; f = f + 1) begin : dly_fine
        (* keep = "true" *) sky130_fd_sc_hd__buf_1 dly_buf (
            .X (chain[BASE+2+f]),
            .A (chain[BASE+1+f])
        );
      end
    end
  endgenerate

  // Tap-MUX: secilen tap node'unu cikisa ver. Delay hucrelerini bypass ETMEZ
  // (chain keep'li). sweep_ctrl tap_sel'i 0..NTAP-1 araliginda uretir.
  assign d_out = chain[tap_sel];

  // NCELL referansi (unused-warning'siz); NTAP=NCELL+1.
  wire _unused = &{1'b0, (NCELL == NTAP-1)};

endmodule
