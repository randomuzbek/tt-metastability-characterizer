# Per-blok RTL unit testi (cocotb, modul dogrudan TOPLEVEL).
# Kullanim:  make BLK=uart_tx
# Gerekirse ek kaynak:  make BLK=foo EXTRA="bar baz"
# NOT: param adi BLK -- 'MODULE' cocotb'nin rezerve degiskeni (test python modulu).
SIM            ?= icarus
TOPLEVEL_LANG  ?= verilog
SRC_DIR         = $(PWD)/../../src
BLK            ?= uart_tx

SIM_BUILD       = sim_build/$(BLK)
VERILOG_SOURCES = $(SRC_DIR)/$(BLK).v $(addprefix $(SRC_DIR)/,$(addsuffix .v,$(EXTRA)))
# SIM-ONLY yardimci kaynak(lar), test/unit/'dan (or. named-cell functional stub).
# SENTEZ'e GIRMEZ -- info.yaml source_files'a EKLENMEZ. Kullanim: SIMLIB=cells_sim
SIMLIB         ?=
VERILOG_SOURCES += $(addprefix $(PWD)/,$(addsuffix .v,$(SIMLIB)))
TOPLEVEL        = $(BLK)
COCOTB_TEST_MODULES = test_$(BLK)

include $(shell cocotb-config --makefiles)/Makefile.sim
