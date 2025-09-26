/*
 * Copyright (c) 2024 Kevin Patel
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral(
    input wire clock, //system clock (10Mhz)
    input wire rst_n, //system reset
    input wire sclk_in, //SPI clock (async)
    input wire ncs_in, //SPI CS
    input wire copi_in, //SPI Controller In, Peripheral Out
    output  reg [7:0] en_reg_out_7_0, //reg 0x00
    output  reg [7:0] en_reg_out_15_8, //reg 0x01
    output  reg [7:0] en_reg_pwm_7_0, //reg 0x02
    output  reg [7:0] en_reg_pwm_15_8, //reg 0x03
    output  reg [7:0] pwm_duty_cycle //reg 0x04
);

//Synchronizer Signals
reg sclk_sync1, sclk_sync2;
reg ncs_sync1, ncs_sync2;
reg copi_sync1, copi_sync2;

//2 Cycle Synchronizer
always @(posedge clock) begin
    //First Synchronizer
    sclk_sync1 <= sclk_in;
    ncs_sync1 <= ncs_in;
    copi_sync1 <= copi_in; 

    //Second Synchronizer
    sclk_sync2 <= sclk_sync1;
    ncs_sync2 <= ncs_sync1;
    copi_sync2 <= copi_sync1;
end

//Detect Rising Edge for SCLK
wire sclk_rising_detect = (sclk_sync1 & ~sclk_sync2);

//Bit Counter and Shift Register
reg [15:0] shift_reg;
reg [4:0] bit_count; //11111 - decimal for 31. Can count up to 31 but we only need 16

always @(posedge clock or negedge rst_n) begin
    if(!rst_n) begin
        //Reset state
        shift_reg <= 0;
        bit_count <= 0;
        en_reg_out_7_0 <= 0;
        en_reg_out_15_8 <= 0;
        en_reg_pwm_7_0 <= 0;
        en_reg_pwm_15_8 <= 0;
        pwm_duty_cycle <= 0;
    end else if (ncs_sync2 == 0) begin //transaction is active
        if(sclk_rising_detect) begin
            shift_reg <= {shift_reg[14:0], copi_sync2}; //every time we detect the rising edge shift in a bit and +1 to counter
            bit_count <= bit_count + 1;
        end
    end else begin
        if(bit_count == 16) begin //transaction complete logic
            if(shift_reg[15] == 1) begin //if write transaction
                case(shift_reg[14:8]) //decode the address
                    7'h00: en_reg_out_7_0  <= shift_reg[7:0];
                    7'h01: en_reg_out_15_8 <= shift_reg[7:0];
                    7'h02: en_reg_pwm_7_0  <= shift_reg[7:0];
                    7'h03: en_reg_pwm_15_8 <= shift_reg[7:0];
                    7'h04: pwm_duty_cycle  <= shift_reg[7:0];
                    default: begin end
                endcase
            end
        end
        bit_count <= 0;
        shift_reg <= 0;
    end
end
endmodule




