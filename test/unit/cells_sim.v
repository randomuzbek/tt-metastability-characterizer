/*
 * cells_sim.v  --  sky130_fd_sc_hd hucrelerinin SIM-ONLY functional modelleri
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * ⚠️ SADECE SIMULASYON ICIN. Bunlar gercek foundry hucrelerinin yerine gecen
 * davranissal (functional) test-double'lardir; GERCEK gecikme/setup-hold YOK
 * (docs/method.md: RTL sim timing gostermez). SENTEZ'e GIRMEZ -- info.yaml
 * source_files'a EKLEME. Sentezde bu isimler foundry liberty'den (LibreLane
 * blackbox always-on) gercek hucrelere cozulur; RTL'deki named-cell
 * instantiation aynen silikona gider.
 *
 * PDK WSL'de kurulu OLMADIGI icin (PDK_ROOT bos) RTL-sim'de gercek
 * $(PDK_ROOT)/.../verilog/sky130_fd_sc_hd.v yerine bu minimal stub kullanilir.
 * Port ADLARIYLA baglaniyoruz (positional degil) -> port sirasi onemsiz.
 * Guc pinleri (VPWR/VGND/VPB/VNB) RTL-sim'de baglanmaz -> stub'larda YOK.
 */
`timescale 1ns / 1ps
`default_nettype none

// Pozitif-kenar D flip-flop, tek cikis Q (1x drive)
module sky130_fd_sc_hd__dfxtp_1 (
    output reg Q,
    input  wire CLK,
    input  wire D
);
  always @(posedge CLK) Q <= D;
endmodule

// Ayni fonksiyon, 2x drive (fiziksel olarak farkli hucre -> farkli timing)
module sky130_fd_sc_hd__dfxtp_2 (
    output reg Q,
    input  wire CLK,
    input  wire D
);
  always @(posedge CLK) Q <= D;
endmodule

// Async reset'li (active-low RESET_B) pozitif-kenar D flip-flop
module sky130_fd_sc_hd__dfrtp_1 (
    output reg Q,
    input  wire CLK,
    input  wire D,
    input  wire RESET_B
);
  always @(posedge CLK or negedge RESET_B)
    if (!RESET_B) Q <= 1'b0;
    else          Q <= D;
endmodule

// Scan-enable'li D flip-flop: SCE=1 iken SCD, aksi halde D
module sky130_fd_sc_hd__sdfxtp_1 (
    output reg Q,
    input  wire CLK,
    input  wire D,
    input  wire SCD,
    input  wire SCE
);
  always @(posedge CLK) Q <= SCE ? SCD : D;
endmodule

// -------- delay-line hucreleri (non-inverting; sim'de 0 ps, silikonda gecikme) --------

// Non-inverting buffer (fine adim ~54 ps silikonda). Port: X=cikis, A=giris.
module sky130_fd_sc_hd__buf_1 (
    output wire X,
    input  wire A
);
  assign X = A;
endmodule

// Inverter 1x (clock inverter / genel). 0 ps sim (ring DEGIL -> gecikmesiz).
// Port: Y=cikis, A=giris.
module sky130_fd_sc_hd__inv_1 (
    output wire Y,
    input  wire A
);
  assign Y = ~A;
endmodule

// Metal-delay hucresi (coarse adim ~87 ps silikonda), non-inverting. X=cikis A=giris.
module sky130_fd_sc_hd__dlymetal6s2s_1 (
    output wire X,
    input  wire A
);
  assign X = A;
endmodule

// -------- ring-oscillator hucreleri --------
// ⚠️ Bunlar #1 sim-gecikmeli (digerleri 0 ps!). Sebep: ring_osc kombinasyonel
// feedback loop'u sim'de osile OLMAK icin gecikme SART (0-delay loop = iverilog
// settle/X). Bu bir OLCUM degil, ring'in FONKSIYONEL davranisi (osile ediyor mu).
// Gercek frekans silikon/GL isi (see docs/method.md). nand2_4/inv_4 SADECE ring_osc'ta kullanilir.
module sky130_fd_sc_hd__inv_4 (
    output wire Y,
    input  wire A
);
  assign #1 Y = ~A;
endmodule

module sky130_fd_sc_hd__nand2_4 (
    output wire Y,
    input  wire A,
    input  wire B
);
  assign #1 Y = ~(A & B);
endmodule
