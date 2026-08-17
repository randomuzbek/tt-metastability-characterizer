/*
 * metastable_witness  --  dual-sample metastability event dedektoru
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * DUT.Q iki farkli fazda ornekleniyor: q_early (ana clock kenari) ve q_late
 * (geciktirilmis/ters kenar). Ikisi ANLASMAZSA DUT FF ornekleme aninda hala
 * metastable coyuluyordu (gec-cozulme) -> event. dut_sel bu sweep'te olculen
 * DUT cesidinin event bitini sweep_ctrl.sample_fail'e verir.
 *
 * Emsal: Beer/Ginosar/Priel/Dobkin/Kolodny ISCAS 2011 (delayed-clk + inverse-clk
 * ornekle, XOR). Bkz. docs/method.md.
 *
 * Kombinasyonel karsilastirma; q_early/q_late ureten witness FF'ler yapisal
 * (top'ta). RTL-sim'de DUT.Q hep 0/1 -> event=0 (timing GL/silikon; bkz. docs/method.md).
 */
`default_nettype none

module metastable_witness #(
    parameter integer NDUT = 4
) (
    input  wire [NDUT-1:0]          q_early,     // ana kenar ornegi
    input  wire [NDUT-1:0]          q_late,      // gecikmeli/ters kenar ornegi
    input  wire [$clog2(NDUT)-1:0]  dut_sel,     // bu sweep'te olculen DUT
    output wire [NDUT-1:0]          meta,        // per-DUT metastable event (witness/debug)
    output wire                     sample_fail  // secili DUT event -> sweep_ctrl
);

  assign meta        = q_early ^ q_late;   // anlasmazlik = gec-cozulme
  assign sample_fail = meta[dut_sel];

endmodule
