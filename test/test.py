# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray
from cocotb.result import TestFailure


async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")

async def wait_for_edge(dut, value: int, timeout=1000000):
    elapsed = 0

    while((dut.uo_out.value.integer & 1) != value):
        await Timer(100, units="ns")
        elapsed = elapsed + 100
        if(elapsed >= timeout):
            raise cocotb.result.TestFailure(f"Timeout waiting for {value}")
    return cocotb.utils.get_sim_time(units="ns")

@cocotb.test()
async def test_pwm_freq(dut):
    # Write your test here
    dut._log.info("Start PWM Frequency Test")

    clock = Clock(dut.clk, 100, units="ns") # start clockm 10Mhz
    cocotb.start_soon(clock.start())

    # Reset
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    await send_spi_transaction(dut, 1, 0x00, 0x01)  # global enable
    await send_spi_transaction(dut, 1, 0x02, 0x01)  # enable PWM module
    await send_spi_transaction(dut, 1, 0x04, 0x80)  # 50% duty

    await ClockCycles(dut.clk, 10000) # give time for PWM to start

    t1 = await wait_for_edge(dut, 1, timeout=100000000)
    await wait_for_edge(dut, 0, timeout=1000000)
    t2 = await wait_for_edge(dut, 1, timeout=100000000)

    period = t2-t1 # period is from two rising edges
    if period == 0:
        raise TestFailure("No period measured")
    frequency = (1e9 / period)
    dut._log.info(f"Measured frequency: {frequency:.2f} Hz")
    if (2900 <= frequency <= 3100):
        dut._log.info("PASS: Freq. within ±1% of 3kHz")
    else:
        dut._log.error("FAIL: Freq. out of range")
        raise cocotb.result.TestFailure("Expected ~3kHz frequency")


@cocotb.test()
async def test_pwm_duty(dut):
    # Write your test here
    dut._log.info("Start PWM Duty Cycle Test")

    clock = Clock(dut.clk, 100, units="ns") # start clockm 10Mhz
    cocotb.start_soon(clock.start())

    # Reset
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


    # Case #1 (0% duty cycle)
    await send_spi_transaction(dut, 1, 0x00, 0x01)  # global enable
    await send_spi_transaction(dut, 1, 0x02, 0x01)  # enable PWM module
    await send_spi_transaction(dut, 1, 0x04, 0x00)  # 50% duty

    all_low = True
    for _ in range(1000):
        await ClockCycles(dut.clk, 1)
        if((dut.uo_out.value.integer & 1) != 0):
            all_low = False
            break
    
    if (all_low):
        dut._log.info("CASE1 (0%): PASS, signal stayed low")
    else:
        dut._log.error("CASE1 (0%): FAIL, signal went high")
        raise cocotb.result.TestFailure("Expected always low at 0% duty")
    
    # Case #2 (50% duty cycle)
    await send_spi_transaction(dut, 1, 0x04, 0x80)

    t_rise1 = await wait_for_edge(dut, 1)
    t_fall = await wait_for_edge(dut, 0)
    t_rise2 = await wait_for_edge(dut, 1)

    period = t_rise2 - t_rise1
    high_time = t_fall - t_rise1
    duty = high_time / period
    duty *= 100

    if 45 <= duty <= 55:
        dut._log.info(f"CASE2 (50%): PASS, {duty:.2f}%")
    else:
        dut._log.error(f"CASE2 (50%): FAIL, {duty:.2f}%")
        raise cocotb.result.TestFailure("Expected ~50% duty")

    # Case #3 (100% duty cycle)
    await send_spi_transaction(dut, 1, 0x04, 0xFF)

    all_high = True
    for _ in range(1000):
        await ClockCycles(dut.clk, 1)
        if((dut.uo_out.value.integer & 1) != 1):
            all_high = False
            break

    if (all_high):
        dut._log.info("CASE3 (100%): PASS, signal stayed high")
    else:
        dut._log.error("CASE3 (100%): FAIL, signal went low")
        raise cocotb.result.TestFailure("Expected always high at 100% duty")
