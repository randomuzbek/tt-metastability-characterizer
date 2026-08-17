/*
 * detector  --  DUT/Ref mismatch dedektoru (XOR)
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * Kombinasyonel: her DUT FF ciktisini (dut_q[i]) Ref FF ciktisi (ref_q) ile
 * XOR'lar -> mismatch[i]. dut_sel ile bu sweep'te karakterize edilen DUT'in
 * mismatch biti sample_fail olarak sweep_ctrl'e verilir.
 * NOT: dut_q/ref_q gercekte skewed-D/CLK ile ornekleyen named-cell FF'lerden
 * gelir; bu blok yalniz karsilastirma mantigi. Timing GL-sim/STA/silikonda.
 */
`default_nettype none

module detector #(
    parameter integer NDUT = 4      // DUT FF cesidi sayisi (top gercek deger verir)
) (
    input  wire [NDUT-1:0]          dut_q,        // DUT FF bank ciktilari
    input  wire                     ref_q,        // altin referans FF ciktisi
    input  wire [$clog2(NDUT)-1:0]  dut_sel,      // bu sweep'te olculen DUT
    output wire [NDUT-1:0]          mismatch,     // per-DUT XOR (witness/debug)
    output wire                     sample_fail   // secili DUT mismatch -> sweep_ctrl
);

  assign mismatch    = dut_q ^ {NDUT{ref_q}};
  assign sample_fail = mismatch[dut_sel];

endmodule
