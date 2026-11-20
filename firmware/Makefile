TARGET  := shunt
BUILD   := build
SRCS    := $(wildcard src/*.c)
OBJS    := $(SRCS:src/%.c=$(BUILD)/%.o)

CC      := arm-none-eabi-gcc
OBJCOPY := arm-none-eabi-objcopy
SIZE    := arm-none-eabi-size

CFLAGS  := -mcpu=cortex-m0 -mthumb -Os -g3 -std=c11 -Wall -Wextra \
           -ffunction-sections -fdata-sections -ffreestanding $(EXTRA_CFLAGS)
LDFLAGS := -mcpu=cortex-m0 -mthumb -nostdlib -nostartfiles -T stm32f031k6.ld \
           -Wl,--gc-sections -Wl,-Map=$(BUILD)/$(TARGET).map -lgcc

all: $(BUILD)/$(TARGET).bin
	@$(SIZE) $(BUILD)/$(TARGET).elf

$(BUILD)/%.o: src/%.c $(wildcard src/*.h) | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/$(TARGET).elf: $(OBJS) stm32f031k6.ld
	$(CC) $(OBJS) $(LDFLAGS) -o $@

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary $< $@

$(BUILD):
	mkdir -p $@

# Flash over the Nucleo's ST-LINK (stlink-tools). "make flash-openocd" if you prefer OpenOCD.
flash: $(BUILD)/$(TARGET).bin
	st-flash --reset write $< 0x08000000

flash-openocd: $(BUILD)/$(TARGET).elf
	openocd -f interface/stlink.cfg -f target/stm32f0x.cfg \
	        -c "program $< verify reset exit"

# Serial terminal on the ST-LINK virtual COM port (Ctrl-A Ctrl-X to quit picocom)
monitor:
	picocom -b 115200 --imap lfcrlf $(or $(PORT),/dev/ttyACM0)

clean:
	rm -rf $(BUILD)

.PHONY: all flash flash-openocd monitor clean
