/*
 * Silicon Characterization Instrument  --  tt_um_randomuzbek_charinst
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * TOP wiring (v1, TOPOLOJI A -- ring-osc async data + dual-sample witness).
 * Karar: docs/method.md (senkron LFSR OLCEMEZ ->
 * metastability ASENKRON veri ister: MTBF=e^(Ts/tau)/(Tw·Fc·Fd), Fd=async).
 *
 *   ring_osc(÷N) -> ro_data (async ÷2 toggle) -> delay_line(fine offset=tap)
 *     -> dut_ff_bank.d_dut (MAIN clk ornekler) -> dut_q
 *   dut_q -> witness_bank (dual-sample q_a/q_b) -> metastable_witness(dut_sel)
 *     -> sweep_ctrl.sample_fail (metastable event = gec-cozulme)
 *   sweep_ctrl -> uart_packet(-> uart_tx) -> uo_out[0]
 *   back-pressure: sweep_ctrl.stall = uart_packet.busy (kayit dusmez).
 *
 * ⚠️ RTL-sim = kontrol mantigi + wiring; named-cell (ring/delay/FF/witness) 0 ps
 * (cells_sim; ring hucreleri #1 osilasyon icin). GERCEK metastability/tau/W/Fd +
 * setup-hold = GL-sim(SDF)+STA+silikon (see docs/method.md). LFSR/detector bloklari artik WIRE
 * DEGIL (Topoloji A async; leaf+unit test korunuyor, v2/alternatif icin).
 *
 * v1 PIN KARARLARI (info.yaml):
 *   ui_in[4:2] = ro_div  (ring divider -> Fd sec; repurpose dwell_sel)
 *   ui_in[6:5] = dut_sel (olculen DUT cesidi)
 *   ui_in[1]   = mode    (paket alani; MTBF-mod davranisi v2)
 *   ui_in[7]   = ext_data (1: dis veri uio[0], 0: ic ring async veri)
 *   uio[1]     = ro_clk OUT (Fd monitoru -- silikonda frekans sayaci baglanir)
 */
`default_nettype none

module tt_um_randomuzbek_charinst #(
    parameter integer TRIALS       = 256,    // tap basina deneme (dwell)
    parameter integer NCOARSE      = 8,      // delay-line coarse kademe
    parameter integer NFINE        = 4,      // coarse basina fine buf
    parameter integer CLKS_PER_BIT = 217,    // 25 MHz / 115200
    parameter [7:0]   DIE_ID       = 8'h5A   // v1 placeholder self-ID (v1 placeholder)
) (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (1=output)
    input  wire       ena,      // design powered (ignore)
    input  wire       clk,      // system + DUT sampling clock (25 MHz)
    input  wire       rst_n     // async reset, active-low
);

  localparam integer NTAP  = NCOARSE*(NFINE+1) + 1;   // delay_line ile ayni
  localparam integer TAP_W = $clog2(NTAP);

  // ---- pin haritasi (v1) ----
  wire       start_i    = ui_in[0];
  wire       mode_i     = ui_in[1];
  wire [2:0] ro_div_i   = ui_in[4:2];    // ring divider (Fd sec)
  wire [1:0] dut_sel_i  = ui_in[6:5];    // olculen DUT cesidi
  wire       ext_data_i = ui_in[7];      // 1: dis veri (uio[0]), 0: ic ring

  // ---- ring oscillator: ASENKRON veri kaynagi (Fd) ----
  // ro_gate: reset'te 0, reset kalktiktan 1 cycle sonra 1. Bu 0->1 GECISI ring'i
  // kick'ler. Neden dogrudan rst_n DEGIL: u_ro_nand dont_touch oldugu icin B pini
  // rst_n agina baglaninca OpenROAD reset agacini buffer'layamiyor
  // (RSZ-0085 -> RSZ-3006 FATAL, kosu 32019839027). Registered gate bu bagi keser.
  // Sabit 1'b1 de OLMAZ: gecis olmadan sim/GL'de ring X'te kilitlenir (osc=X ->
  // divider saymaz -> asenkron veri HIC akmaz, sessizce olu enstruman).
  reg ro_gate;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) ro_gate <= 1'b0;
    else        ro_gate <= 1'b1;
  end

  wire ro_clk;
  ring_osc u_ro (
      .rst_n   (rst_n),
      .gate    (ro_gate),      // 0->1 gecisi osilasyonu kick'ler (yukari bkz.)
      .div     (ro_div_i),
      .clk_out (ro_clk)
  );

  // async ÷2 veri: ro_clk domain'inde toggle -> main clk'ye uncorrelated gecisler
  reg ro_data;
  always @(posedge ro_clk or negedge rst_n) begin
    if (!rst_n) ro_data <= 1'b0;
    else        ro_data <= ~ro_data;
  end

  wire test_data = ext_data_i ? uio_in[0] : ro_data;

  // ---- delay line: aperture icinde ince offset (tap-swept) ----
  wire [TAP_W-1:0] tap;
  wire             d_dut_skewed;
  delay_line #(
      .NCOARSE (NCOARSE),
      .NFINE   (NFINE)
  ) u_delay (
      .d_in    (test_data),
      .tap_sel (tap),
      .d_out   (d_dut_skewed)
  );

  // ---- DUT FF bank: async veriyi MAIN clk ile ornekler (metastable olabilir) ----
  wire [3:0] dut_q;
  wire       ref_q_unused;
  dut_ff_bank u_ffbank (
      .clk   (clk),
      .rst_n (rst_n),
      .d_dut (d_dut_skewed),
      .d_ref (1'b0),           // Topoloji A'da Ref kullanilmiyor (witness birincil)
      .dut_q (dut_q),
      .ref_q (ref_q_unused)
  );

  // ---- witness: DUT.Q'yu iki fazda ornekle (gec-cozulme yakala) ----
  wire [3:0] q_a, q_b;
  witness_bank #(.NDUT(4)) u_wit (
      .clk   (clk),
      .rst_n (rst_n),
      .dut_q (dut_q),
      .q_a   (q_a),
      .q_b   (q_b)
  );

  // ---- metastable event dedektoru ----
  wire       sample_fail;
  wire [3:0] meta;
  metastable_witness #(.NDUT(4)) u_meta (
      .q_early     (q_a),
      .q_late      (q_b),
      .dut_sel     (dut_sel_i),
      .meta        (meta),
      .sample_fail (sample_fail)
  );

  // ---- sweep controller (back-pressure: stall = paket busy) ----
  wire [31:0] fail_count, trial_count;
  wire        emit, sweep_busy, sweep_done;
  wire        pkt_busy;
  sweep_ctrl #(
      .TAP_COUNT (NTAP),
      .TRIALS    (TRIALS)
  ) u_sweep (
      .clk         (clk),
      .rst_n       (rst_n),
      .start       (start_i),
      .sample_fail (sample_fail),
      .stall       (pkt_busy),
      .tap         (tap),
      .fail_count  (fail_count),
      .trial_count (trial_count),
      .emit        (emit),
      .busy        (sweep_busy),
      .done        (sweep_done)
  );

  // ---- UART packetizer (icinde uart_tx) ----
  wire [15:0] tap_wide = {{(16-TAP_W){1'b0}}, tap};
  wire        uart_tx_line;
  uart_packet #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_pkt (
      .clk         (clk),
      .rst_n       (rst_n),
      .emit        (emit),
      .mode        (mode_i),
      .tap         (tap_wide),
      .fail_count  (fail_count),
      .trial_count (trial_count),
      .die_id      (DIE_ID),
      .tx          (uart_tx_line),
      .busy        (pkt_busy)
  );

  // ---- heartbeat ----
  reg [23:0] hb_cnt;
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) hb_cnt <= 24'd0;
    else        hb_cnt <= hb_cnt + 24'd1;
  end

  // ---- cikis haritasi ----
  assign uo_out[0]   = uart_tx_line;   // UART TX (8N1)
  assign uo_out[1]   = sweep_busy;
  assign uo_out[2]   = sweep_done;
  assign uo_out[3]   = hb_cnt[23];     // heartbeat
  assign uo_out[7:4] = tap_wide[3:0];  // canli tap (debug)

  // uio[1] = bolunmus ring clock = Fd MONITORU. MTBF=e^(Ts/tau)/(Tw·Fc·Fd)
  // icinde Fd VAR; silikonda olculemezse W/absolute MTBF cikarilamaz (tau egimden
  // gelir, etkilenmez). Alan maliyeti ~0 (mevcut ro_clk net'i pine baglanir).
  // uio[0] = ext_data girisi (ui_in[7]=1 iken) -> input kalir.
  assign uio_out = {6'b0, ro_clk, 1'b0};
  assign uio_oe  = 8'b00000010;        // yalniz uio[1] output

  // Kullanilmayan tuket (ena, ref_q, meta[3:0] debug, uio[7:1]).
  wire _unused = &{ena, ref_q_unused, meta, uio_in[7:1], 1'b0};

endmodule
