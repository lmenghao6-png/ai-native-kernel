# AegisOS Makefile
# Builds: Bastion kernel (with VFS/initramfs/ELF) + user programs + cpio archive

CC=clang
LD=ld.lld
TARGET=x86_64-unknown-none-elf

KERNEL_DIR=kernel
SRC_DIR=$(KERNEL_DIR)/src
INC_DIR=$(KERNEL_DIR)/include
BUILD_DIR=build
OBJ_DIR=$(BUILD_DIR)/obj
DIST_DIR=$(BUILD_DIR)/dist
FAT_DIR=$(BUILD_DIR)/fatroot

KERNEL_ELF=$(BUILD_DIR)/aikernel.elf
LIMINE_DIR=third_party/limine

CFLAGS=--target=$(TARGET) -std=gnu11 -Wall -Wextra \
	-ffreestanding -fno-stack-protector -fno-stack-check -fno-lto -fno-pic \
	-ffunction-sections -fdata-sections -m64 -march=x86-64 -mabi=sysv \
	-mno-80387 -mno-mmx -mno-sse -mno-sse2 -mno-red-zone -mcmodel=kernel \
	-I$(INC_DIR)

SFLAGS=--target=$(TARGET) -m64 -march=x86-64 -mabi=sysv -mno-red-zone -I$(INC_DIR)

LDFLAGS=-m elf_x86_64 -nostdlib -static -z max-page-size=0x1000 --gc-sections -T $(KERNEL_DIR)/linker.ld

# User program
USER_DIR=user
USER_BUILD=$(BUILD_DIR)/user
USER_CFLAGS=--target=$(TARGET) -std=gnu11 -ffreestanding -nostdlib -fPIC \
	-static -m64 -march=x86-64 -mabi=sysv -mno-red-zone -fno-stack-protector \
	-Os -Wall -Wextra

# Initramfs
INITRAMFS_CPIO=$(BUILD_DIR)/initramfs.cpio
INITRAMFS_OBJ=$(OBJ_DIR)/initramfs.cpio.o

C_SRCS=$(shell find $(SRC_DIR) -name '*.c')
S_SRCS=$(shell find $(SRC_DIR) -name '*.S')
C_OBJS=$(patsubst $(SRC_DIR)/%.c,$(OBJ_DIR)/%.c.o,$(C_SRCS))
S_OBJS=$(patsubst $(SRC_DIR)/%.S,$(OBJ_DIR)/%.S.o,$(S_SRCS))
ALL_OBJS=$(C_OBJS) $(S_OBJS) $(INITRAMFS_OBJ)

.PHONY: all clean dist fat qemu user

all: $(KERNEL_ELF)

user: $(USER_BUILD)/hello.elf

$(USER_BUILD)/hello.elf: $(USER_DIR)/hello.c
	@mkdir -p $(USER_BUILD)
	$(CC) $(USER_CFLAGS) -Wl,-e_start -o $@ $<
	strip $@

$(INITRAMFS_CPIO): $(USER_BUILD)/hello.elf
	@mkdir -p $(BUILD_DIR)
	@rm -rf /tmp/initramfs_staging
	@mkdir -p /tmp/initramfs_staging/bin
	@cp $< /tmp/initramfs_staging/bin/hello
	@cd /tmp/initramfs_staging && find . | cpio -o -H newc > $@ 2>/dev/null
	@rm -rf /tmp/initramfs_staging

$(INITRAMFS_OBJ): $(INITRAMFS_CPIO)
	@mkdir -p $(dir $@)
	$(LD) -m elf_x86_64 -r -b binary -o $@ $<

$(OBJ_DIR)/%.c.o: $(SRC_DIR)/%.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(OBJ_DIR)/%.S.o: $(SRC_DIR)/%.S
	@mkdir -p $(dir $@)
	$(CC) $(SFLAGS) -c $< -o $@

$(KERNEL_ELF): $(ALL_OBJS) $(KERNEL_DIR)/linker.ld
	$(LD) $(LDFLAGS) $(ALL_OBJS) -o $@

limine:
	@if [ ! -d "$(LIMINE_DIR)" ]; then \
		git clone --branch=v11.x-binary --depth=1 https://github.com/Limine-Bootloader/Limine.git $(LIMINE_DIR); \
	fi

dist: $(KERNEL_ELF) limine
	@mkdir -p $(DIST_DIR)/boot $(DIST_DIR)/EFI/BOOT
	cp $(KERNEL_ELF) $(DIST_DIR)/boot/
	cp kernel/limine.conf $(DIST_DIR)/
	cp $(LIMINE_DIR)/BOOTX64.EFI $(DIST_DIR)/EFI/BOOT/ 2>/dev/null || true
	cp $(LIMINE_DIR)/BOOTIA32.EFI $(DIST_DIR)/EFI/BOOT/ 2>/dev/null || true

fat: dist
	@mkdir -p $(FAT_DIR)/boot $(FAT_DIR)/EFI/BOOT
	cp $(KERNEL_ELF) $(FAT_DIR)/boot/
	cp kernel/limine.conf $(FAT_DIR)/
	cp $(LIMINE_DIR)/BOOTX64.EFI $(FAT_DIR)/EFI/BOOT/ 2>/dev/null || true
	cp $(LIMINE_DIR)/BOOTIA32.EFI $(FAT_DIR)/EFI/BOOT/ 2>/dev/null || true

OVMF ?= /usr/share/ovmf/OVMF.fd
AEGISOS_IMAGE ?= $(BUILD_DIR)/aegisos/image/aegisos-alpha-uefi.raw

qemu-aegisos:
	qemu-system-x86_64 -machine q35 -m 2G -no-reboot \
		-nographic -serial mon:stdio \
		-nic user,model=e1000e \
		-drive if=pflash,format=raw,readonly=on,file=$(OVMF) \
		-drive format=raw,file=$(AEGISOS_IMAGE)

aegisos-image:
	bash tools/build-aegisos-rootfs.sh
	bash tools/build-aegisos-image.sh

qemu: fat
	qemu-system-x86_64 -machine pc,graphics=off -bios $(OVMF) -m 256M -no-reboot \
		-nographic -serial mon:stdio \
		-drive file=fat:rw:$(FAT_DIR)

qemu-debug: fat
	qemu-system-x86_64 -machine pc -bios $(OVMF) -m 256M -no-reboot -d cpu_reset,int \
		-nographic -serial mon:stdio \
		-drive file=fat:rw:$(FAT_DIR)

run: qemu

clean:
	rm -rf $(BUILD_DIR)
