BUILD_DIR ?= build
AEGISOS_IMAGE ?= $(BUILD_DIR)/aegisos/image/aegisos-$(shell tr -d '[:space:]' < VERSION).iso
OVMF ?= /usr/share/ovmf/OVMF.fd

.PHONY: all image qemu test test-python test-iso test-install clean

all: test-python

image:
	bash tools/build-aegisos-rootfs.sh
	bash tools/build-aegisos-image.sh

qemu:
	qemu-system-x86_64 -machine q35 -m 2G -no-reboot \
		-nographic -serial mon:stdio \
		-nic user,model=e1000e \
		-drive if=pflash,format=raw,readonly=on,file=$(OVMF) \
		-cdrom $(AEGISOS_IMAGE)

test: test-python

test-python:
	python3 -m unittest discover -s tests -v

test-iso:
	expect tools/test-aegisos-iso.exp

test-install:
	expect tools/test-aegisos-install.exp

clean:
	rm -rf $(BUILD_DIR)
