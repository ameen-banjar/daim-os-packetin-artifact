CC ?= cc
CFLAGS ?= -std=c11 -Wall -Wextra -Wpedantic -Werror -O2
CPPFLAGS ?= -Iinclude -I../vendor/DAIM-OS-v1.0.0
LDLIBS ?= -lpthread

BUILD := build
PIC_BUILD := $(BUILD)/pic
CORE_OBJ := $(BUILD)/daim_core.o
MOCK_OBJ := $(BUILD)/mock_switch_adapter.o
OVS_OBJ := $(BUILD)/ovs_switch_adapter.o
LEARNING_OBJ := $(BUILD)/daim_learning_app.o
PIC_CORE_OBJ := $(PIC_BUILD)/daim_core.o
PIC_OVS_OBJ := $(PIC_BUILD)/ovs_switch_adapter.o
PIC_LEARNING_OBJ := $(PIC_BUILD)/daim_learning_app.o
TESTS := $(BUILD)/test_core $(BUILD)/test_adapters $(BUILD)/test_concurrency $(BUILD)/test_learning_app
TOOLS := $(BUILD)/daim_ovs_flow
SHARED_LIB := $(BUILD)/libdaim_core.so

.PHONY: all check clean

all: $(TESTS) $(TOOLS) $(SHARED_LIB)

check: $(TESTS)
	$(BUILD)/test_core
	$(BUILD)/test_adapters
	$(BUILD)/test_concurrency
	$(BUILD)/test_learning_app

$(BUILD):
	mkdir -p $(BUILD)

$(PIC_BUILD):
	mkdir -p $(PIC_BUILD)

$(CORE_OBJ): src/daim_core.c include/daim_core.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(MOCK_OBJ): src/mock_switch_adapter.c include/daim_switch_adapter.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(OVS_OBJ): src/ovs_switch_adapter.c include/ovs_switch_adapter.h include/daim_switch_adapter.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(LEARNING_OBJ): src/daim_learning_app.c include/daim_learning_app.h include/daim_core.h include/daim_switch_adapter.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(PIC_CORE_OBJ): src/daim_core.c include/daim_core.h | $(PIC_BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -c $< -o $@

$(PIC_OVS_OBJ): src/ovs_switch_adapter.c include/ovs_switch_adapter.h include/daim_switch_adapter.h | $(PIC_BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -c $< -o $@

$(PIC_LEARNING_OBJ): src/daim_learning_app.c include/daim_learning_app.h include/daim_core.h include/daim_switch_adapter.h | $(PIC_BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -c $< -o $@

$(BUILD)/test_core: tests/test_core.c $(CORE_OBJ)
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ $(LDLIBS) -o $@

$(BUILD)/test_adapters: tests/test_adapters.c $(MOCK_OBJ) $(OVS_OBJ)
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ $(LDLIBS) -o $@

$(BUILD)/test_concurrency: tests/test_concurrency.c $(CORE_OBJ)
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ $(LDLIBS) -o $@

$(BUILD)/test_learning_app: tests/test_learning_app.c $(LEARNING_OBJ) $(CORE_OBJ) $(MOCK_OBJ)
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ $(LDLIBS) -o $@

$(BUILD)/daim_ovs_flow: tools/daim_ovs_flow.c $(OVS_OBJ)
	$(CC) $(CPPFLAGS) $(CFLAGS) $^ $(LDLIBS) -o $@

$(SHARED_LIB): $(PIC_CORE_OBJ) $(PIC_OVS_OBJ) $(PIC_LEARNING_OBJ)
	$(CC) -shared -fPIC $^ $(LDLIBS) -o $@

clean:
	rm -f $(BUILD)/*.o $(PIC_BUILD)/*.o $(TESTS) $(TOOLS) $(SHARED_LIB)
