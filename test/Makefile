# Makefile
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
# Sentez'e giden tum kaynaklar (info.yaml source_files ile AYNI olmali).
PROJECT_SOURCES  = project.v
PROJECT_SOURCES += uart_tx.v
PROJECT_SOURCES += uart_packet.v
PROJECT_SOURCES += sweep_ctrl.v
PROJECT_SOURCES += delay_line.v
PROJECT_SOURCES += dut_ff_bank.v
PROJECT_SOURCES += witness_bank.v
PROJECT_SOURCES += metastable_witness.v
PROJECT_SOURCES += ring_osc.v

# Integration testi hiz override (kucuk param). += -> COMPILE_ARGS clobber olmaz,
# cocotb timescale cmds.f korunur. Or: TB_PARAMS="-Ptb.TRIALS=4 -Ptb.CLKS_PER_BIT=8"
TB_PARAMS ?=
COMPILE_ARGS += $(TB_PARAMS)

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))
# SIM-ONLY named-cell functional stub'lari (delay/FF). SENTEZ'e GIRMEZ
# (info.yaml source_files'ta YOK); GL akisi gercek PDK modellerini kullanir.
VERILOG_SOURCES += $(PWD)/unit/cells_sim.v

else

# Gate level simulation:
SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DUSE_POWER_PINS
COMPILE_ARGS    += -DSIM
COMPILE_ARGS    += -DUNIT_DELAY=\#1
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/primitives.v
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
