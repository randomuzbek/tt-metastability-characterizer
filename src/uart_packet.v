/*
 * uart_packet  --  olcum kaydini 14-byte cerceve olarak UART'tan serilestir
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * 'emit' 1-cycle darbesinde {mode, tap, fail_count, trial_count, die_id}
 * latch'lenir; ardindan asagidaki 14-byte cerceve icteki uart_tx (8N1) ile
 * seri gonderilir. Iletim boyunca 'busy' yuksek.
 *
 * Cerceve (little-endian; checksum sync DAHIL onceki tum byte'lari kapsar):
 *   [0]    0xA5 sync
 *   [1]    {7'b0, mode}
 *   [2..3] tap          (LE, 16-bit)
 *   [4..7] fail_count   (LE, 32-bit)
 *   [8..11]trial_count  (LE, 32-bit)
 *   [12]   die_id
 *   [13]   checksum = XOR(byte[0..12])   -> host: XOR(tum 14 byte)==0
 *
 * Wire-format karari 2026-07-16 (kullanici): 14-byte, tap 2-byte, LE,
 * checksum tum frame. Taslak spec'teki 13-vs-14 byte tutarsizligi burada cozuldu.
 */
`default_nettype none

module uart_packet #(
    parameter integer CLKS_PER_BIT = 217   // 25 MHz / 115200 ~= 217; uart_tx'e gecer
) (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        emit,          // 1-cycle: alanlari latch'le + gonderimi baslat
    input  wire        mode,          // 0: shmoo, 1: MTBF
    input  wire [15:0] tap,           // gecerli tap kodu (emit cycle'inda)
    input  wire [31:0] fail_count,
    input  wire [31:0] trial_count,
    input  wire [7:0]  die_id,
    output wire        tx,            // UART seri hat (uo_out[0]'a)
    output wire        busy           // cerceve gonderiliyor
);

  localparam [1:0] S_IDLE       = 2'd0,
                   S_LOAD       = 2'd1,   // send=1 (bu byte)
                   S_WAIT_START = 2'd2,   // uart_tx busy yukselene kadar
                   S_WAIT_DONE  = 2'd3;   // byte bitene kadar

  localparam [7:0] SYNC = 8'hA5;

  reg  [1:0]  state;
  reg  [3:0]  byte_idx;      // 0..13

  // Latch'lenen alanlar (emit cycle'inda)
  reg         r_mode;
  reg  [15:0] r_tap;
  reg  [31:0] r_fail;
  reg  [31:0] r_trial;
  reg  [7:0]  r_die;
  reg  [7:0]  r_chk;

  // Byte secici (kombinasyonel): gecerli byte_idx -> gonderilecek byte
  reg  [7:0]  tx_data;
  always @(*) begin
    case (byte_idx)
      4'd0:  tx_data = SYNC;
      4'd1:  tx_data = {7'b0, r_mode};
      4'd2:  tx_data = r_tap[7:0];
      4'd3:  tx_data = r_tap[15:8];
      4'd4:  tx_data = r_fail[7:0];
      4'd5:  tx_data = r_fail[15:8];
      4'd6:  tx_data = r_fail[23:16];
      4'd7:  tx_data = r_fail[31:24];
      4'd8:  tx_data = r_trial[7:0];
      4'd9:  tx_data = r_trial[15:8];
      4'd10: tx_data = r_trial[23:16];
      4'd11: tx_data = r_trial[31:24];
      4'd12: tx_data = r_die;
      4'd13: tx_data = r_chk;
      default: tx_data = 8'h00;
    endcase
  end

  wire tx_busy;
  wire tx_send = (state == S_LOAD);

  assign busy = (state != S_IDLE);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state    <= S_IDLE;
      byte_idx <= 4'd0;
      r_mode   <= 1'b0;
      r_tap    <= 16'd0;
      r_fail   <= 32'd0;
      r_trial  <= 32'd0;
      r_die    <= 8'd0;
      r_chk    <= 8'd0;
    end else begin
      case (state)
        S_IDLE: begin
          if (emit) begin
            r_mode  <= mode;
            r_tap   <= tap;
            r_fail  <= fail_count;
            r_trial <= trial_count;
            r_die   <= die_id;
            // checksum = XOR(byte[0..12]) latch aninda
            r_chk   <= SYNC
                       ^ {7'b0, mode}
                       ^ tap[7:0] ^ tap[15:8]
                       ^ fail_count[7:0] ^ fail_count[15:8]
                       ^ fail_count[23:16] ^ fail_count[31:24]
                       ^ trial_count[7:0] ^ trial_count[15:8]
                       ^ trial_count[23:16] ^ trial_count[31:24]
                       ^ die_id;
            byte_idx <= 4'd0;
            state    <= S_LOAD;
          end
        end

        S_LOAD: begin
          // tx_send bu cycle 1 (kombinasyonel). uart_tx bir sonraki kenarda
          // data'yi latch'ler ve S_START'a gecer.
          state <= S_WAIT_START;
        end

        S_WAIT_START: begin
          if (tx_busy) state <= S_WAIT_DONE;   // uart_tx gonderime basladi
        end

        S_WAIT_DONE: begin
          if (!tx_busy) begin                  // byte tamam
            if (byte_idx == 4'd13) begin
              state <= S_IDLE;                  // son byte -> bitti
            end else begin
              byte_idx <= byte_idx + 4'd1;
              state    <= S_LOAD;
            end
          end
        end

        default: state <= S_IDLE;
      endcase
    end
  end

  uart_tx #(
      .CLKS_PER_BIT (CLKS_PER_BIT)
  ) u_tx (
      .clk   (clk),
      .rst_n (rst_n),
      .data  (tx_data),
      .send  (tx_send),
      .tx    (tx),
      .busy  (tx_busy)
  );

endmodule
