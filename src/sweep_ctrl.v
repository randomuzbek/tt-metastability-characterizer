/*
 * sweep_ctrl  --  swept-skew olcum cekirdegi (FSM + trial/fail counter)
 * Copyright (c) 2026 randomuzbek
 * SPDX-License-Identifier: Apache-2.0
 *
 * Her tap noktasi icin TRIALS deneme kosar; sample_fail=1 olan denemeleri
 * sayar. Tap'in denemeleri bitince 'emit' 1 cycle yukselir ve o cycle'da
 * tap / fail_count / trial_count gecerlidir. Son tap'te 'done'.
 * NOT: sample_fail gercek tasarimda XOR(DUT.Q, Ref.Q); burada disaridan.
 */
`default_nettype none

module sweep_ctrl #(
    parameter integer TAP_COUNT = 4,    // toplam tap noktasi (top gercek deger verir)
    parameter integer TRIALS    = 8     // tap basina deneme
) (
    input  wire                        clk,
    input  wire                        rst_n,
    input  wire                        start,        // 1-cycle darbe
    input  wire                        sample_fail,  // per-trial: DUT != Ref
    input  wire                        stall,        // 1: sayaclari dondur (back-pressure)
    output reg  [$clog2(TAP_COUNT)-1:0] tap,
    output reg  [31:0]                 fail_count,   // gecerli: emit=1 cycle'inda
    output reg  [31:0]                 trial_count,  // gecerli: emit=1 cycle'inda
    output wire                        emit,          // 1-cycle: kayit hazir
    output reg                         busy,
    output reg                         done
);

  localparam S_IDLE = 1'b0,
             S_RUN   = 1'b1;

  reg state;

  // Kombinasyonel emit: tap'in son denemesi tamamlandiginda, sayaclar
  // henuz resetlenmeden yuksek. (Registered olsaydi reset ile carpisirdi.)
  assign emit = busy & (trial_count == TRIALS);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state       <= S_IDLE;
      tap         <= {$clog2(TAP_COUNT){1'b0}};
      fail_count  <= 32'd0;
      trial_count <= 32'd0;
      busy        <= 1'b0;
      done        <= 1'b0;
    end else begin
      case (state)
        S_IDLE: begin
          busy <= 1'b0;
          if (start) begin
            state       <= S_RUN;
            busy        <= 1'b1;
            done        <= 1'b0;
            tap         <= {$clog2(TAP_COUNT){1'b0}};
            fail_count  <= 32'd0;
            trial_count <= 32'd0;
          end
        end

        S_RUN: begin
          // stall=1 iken tum ilerleme donar (uart_packet.busy back-pressure).
          // Boylece emit tam da uart idle iken (stall=0) tek cycle yukselir ->
          // uart temiz latch'ler; iletim boyunca sweep bekler, kayit dusmez.
          if (!stall) begin
            if (trial_count == TRIALS) begin
              // tap tamam: emit (kombinasyonel) su an yuksek
              if (tap == TAP_COUNT-1) begin
                state <= S_IDLE;
                busy  <= 1'b0;
                done  <= 1'b1;
              end else begin
                tap         <= tap + 1'b1;
                trial_count <= 32'd0;
                fail_count  <= 32'd0;
              end
            end else begin
              trial_count <= trial_count + 32'd1;
              fail_count  <= fail_count + {31'b0, sample_fail};
            end
          end
        end

        default: state <= S_IDLE;
      endcase
    end
  end

endmodule
