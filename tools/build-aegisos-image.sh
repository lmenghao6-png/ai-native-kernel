#!/bin/bash
# Build the AegisOS squashfs and bootable ISO from an existing rootfs.

set -euo pipefail

ROOTFS="${ROOTFS:-build/aegisos/linux-rootfs}"
BUILD_DIR="${BUILD_DIR:-build/aegisos}"
VERSION_FILE="${VERSION_FILE:-VERSION}"
ISO_DIR="$BUILD_DIR/iso"
IMAGE_DIR="$BUILD_DIR/image"
SQUASHFS="$BUILD_DIR/aegisos-root.squashfs"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Version file not found: $VERSION_FILE" >&2
    exit 1
fi
AEGISOS_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
if [[ ! "$AEGISOS_VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?(-[a-z0-9]+([.-][a-z0-9]+)*)?$ ]]; then
    echo "Invalid AegisOS version: $AEGISOS_VERSION" >&2
    exit 1
fi
ISO="$IMAGE_DIR/aegisos-$AEGISOS_VERSION.iso"

if [ "$(id -u)" -eq 0 ]; then
    SUDO=()
else
    SUDO=(sudo)
fi

if [ ! -d "$ROOTFS" ]; then
    echo "Rootfs not found: $ROOTFS" >&2
    echo "Run: sudo bash tools/build-aegisos-rootfs.sh" >&2
    exit 1
fi

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

need_cmd mksquashfs
need_cmd grub-mkrescue
need_cmd mformat

${SUDO[@]} rm -rf "$ISO_DIR"
${SUDO[@]} rm -f "$SQUASHFS" "$ISO"
${SUDO[@]} mkdir -p "$ISO_DIR/boot/grub" "$ISO_DIR/live" "$IMAGE_DIR"
${SUDO[@]} chown "$(id -u):$(id -g)" "$BUILD_DIR"
${SUDO[@]} chown -R "$(id -u):$(id -g)" "$ISO_DIR" "$IMAGE_DIR"

kernel_image="$(find "$ROOTFS/boot" -maxdepth 1 -type f -name 'vmlinuz-*' | sort | tail -n 1)"
initrd_image="$(find "$ROOTFS/boot" -maxdepth 1 -type f -name 'initrd.img-*' | sort | tail -n 1)"

if [ -z "$kernel_image" ]; then
    echo "No kernel image found in $ROOTFS/boot" >&2
    exit 1
fi

if [ -z "$initrd_image" ] && [ -f "$ROOTFS/initrd.img" ]; then
    initrd_image="$ROOTFS/initrd.img"
fi

if [ -z "$initrd_image" ]; then
    echo "No initrd image found in $ROOTFS/boot or $ROOTFS/initrd.img" >&2
    exit 1
fi

${SUDO[@]} mksquashfs "$ROOTFS" "$SQUASHFS" -comp xz -b 256K -noappend -no-xattrs
cp "$kernel_image" "$ISO_DIR/boot/vmlinuz"
cp "$initrd_image" "$ISO_DIR/boot/initrd.img"
${SUDO[@]} cp "$SQUASHFS" "$ISO_DIR/live/filesystem.squashfs"

cat > "$ISO_DIR/boot/grub/grub.cfg" << EOF
set default=0
set timeout=5

menuentry "AegisOS $AEGISOS_VERSION (Live)" {
    linux /boot/vmlinuz boot=live components console=ttyS0,115200 systemd.show_status=1
    initrd /boot/initrd.img
}

menuentry "Install AegisOS to Disk" {
    linux /boot/vmlinuz boot=live components console=ttyS0,115200 systemd.show_status=1 systemd.unit=aegisos-installer.service
    initrd /boot/initrd.img
}
EOF

grub-mkrescue -o "$ISO" "$ISO_DIR" -- -volid AEGISOS
${SUDO[@]} chown -R "$(id -u):$(id -g)" "$SQUASHFS" "$ISO_DIR" "$IMAGE_DIR"
chmod 644 "$SQUASHFS" "$ISO"
ls -lh "$ISO"
