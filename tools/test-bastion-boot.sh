#!/bin/bash

set -euo pipefail

OVMF="${OVMF:-/usr/share/ovmf/OVMF.fd}"
FAT_DIR="${FAT_DIR:-build/fatroot}"
BOOT_LOG="${BOOT_LOG:-build/bastion-boot.log}"

command -v qemu-system-x86_64 >/dev/null
test -f "$OVMF"
test -d "$FAT_DIR"

set +e
timeout 20 qemu-system-x86_64 -machine pc,graphics=off \
    -bios "$OVMF" -m 256M -no-reboot \
    -nographic -serial mon:stdio \
    -drive format=raw,file=fat:rw:"$FAT_DIR" >"$BOOT_LOG" 2>&1
qemu_status=$?
set -e

test "$qemu_status" -eq 0 -o "$qemu_status" -eq 124
grep -q "\[pmm\] usable pages:" "$BOOT_LOG"
grep -q "\[vmm\] init done" "$BOOT_LOG"
grep -q "\[vfs\] initialized" "$BOOT_LOG"
grep -q "\[initramfs\] mounted 2 entries" "$BOOT_LOG"
grep -q "\[FILE\] hello" "$BOOT_LOG"
grep -q "\[elf\] loaded /bin/hello entry=0x0000000000401000" "$BOOT_LOG"
grep -q "\[task\] entering ring3" "$BOOT_LOG"
grep -q "Hello from Bastion!" "$BOOT_LOG"
grep -q "\[task\] user process exited status=0" "$BOOT_LOG"
! grep -q "failed to allocate CR3" "$BOOT_LOG"
! grep -q "\[boot\] missing required Limine responses" "$BOOT_LOG"

echo "Bastion boot test passed"
