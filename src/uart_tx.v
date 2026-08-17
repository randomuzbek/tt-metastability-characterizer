/*
 * uart_tx  --  8N1 UART transmitter (idle-high, start=0, 8 data LSB-first, stop=1)
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 */
`default_nettype none

module uart_tx #(
    parameter integer CLKS_PER_BIT = 217   // 25 MHz / 115200 ~= 217
) (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] data,     // send edge'inde latch'lenir
    input  wire       send,     // 1-cycle darbe: iletimi baslat
    output reg        tx,        // seri hat (idle high)
    output wire       busy       // iletim suruyor
);

  localparam [1:0] S_IDLE  = 2'd0,
                   S_START = 2'd1,
                   S_DATA  = 2'd2,
                   S_STOP  = 2'd3;

  reg  [1:0]  state;
  reg  [15:0] clk_cnt;     // bit-suresi sayaci (CLKS_PER_BIT'e kadar)
  reg  [2:0]  bit_idx;     // 0..7
  reg  [7:0]  shreg;       // gonderilen byte

  assign busy = (state != S_IDLE);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state   <= S_IDLE;
      tx      <= 1'b1;
      clk_cnt <= 16'd0;
      bit_idx <= 3'd0;
      shreg   <= 8'd0;
    end else begin
      case (state)
        S_IDLE: begin
          tx      <= 1'b1;
          clk_cnt <= 16'd0;
          bit_idx <= 3'd0;
          if (send) begin
            shreg <= data;
            state <= S_START;
          end
        end

        S_START: begin
          tx <= 1'b0;                          // start biti
          if (clk_cnt == CLKS_PER_BIT-1) begin
            clk_cnt <= 16'd0;
            state   <= S_DATA;
          end else begin
            clk_cnt <= clk_cnt + 16'd1;
          end
        end

        S_DATA: begin
          tx <= shreg[bit_idx];                // LSB-first
          if (clk_cnt == CLKS_PER_BIT-1) begin
            clk_cnt <= 16'd0;
            if (bit_idx == 3'd7) begin
              bit_idx <= 3'd0;
              state   <= S_STOP;
            end else begin
              bit_idx <= bit_idx + 3'd1;
            end
          end else begin
            clk_cnt <= clk_cnt + 16'd1;
          end
        end

        S_STOP: begin
          tx <= 1'b1;                          // stop biti
          if (clk_cnt == CLKS_PER_BIT-1) begin
            clk_cnt <= 16'd0;
            state   <= S_IDLE;
          end else begin
            clk_cnt <= clk_cnt + 16'd1;
          end
        end

        default: state <= S_IDLE;
      endcase
    end
  end

endmodule
