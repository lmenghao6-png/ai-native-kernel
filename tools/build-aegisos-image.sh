#!/bin/bash
# Build the AegisOS squashfs and bootable ISO from an existing rootfs.

set -euo pipefail

ROOTFS="${ROOTFS:-build/aegisos/linux-rootfs}"
BUILD_DIR="${BUILD_DIR:-build/aegisos}"
VERSION_FILE="${VERSION_FILE:-VERSION}"
ISO_DIR="$BUILD_DIR/iso"
IMAGE_DIR="$BUILD_DIR/image"
SQUASHFS="$BUILD_DIR/aegisos-root.squashfs"
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || printf '0')}"
export SOURCE_DATE_EPOCH

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
${SUDO[@]} rm -f \
    "$SQUASHFS" "$ISO" \
    "$IMAGE_DIR/SHA256SUMS" \
    "$IMAGE_DIR/release-manifest.json"
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

${SUDO[@]} mksquashfs "$ROOTFS" "$SQUASHFS" \
    -comp xz -b 256K -noappend -no-xattrs \
    -mkfs-time "$SOURCE_DATE_EPOCH" -all-time "$SOURCE_DATE_EPOCH"
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
(
    cd "$IMAGE_DIR"
    sha256sum "$(basename "$ISO")" > SHA256SUMS
)
python3 - "$ISO" "$IMAGE_DIR/release-manifest.json" \
    "$AEGISOS_VERSION" "$SOURCE_DATE_EPOCH" <<'PY'
import hashlib
import json
import os
import sys

iso, manifest, version, source_date_epoch = sys.argv[1:]
digest = hashlib.sha256()
with open(iso, "rb") as handle:
    for block in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(block)
with open(manifest, "w") as handle:
    json.dump(
        {
            "format": 1,
            "product": "AegisOS",
            "version": version,
            "architecture": "amd64",
            "image": os.path.basename(iso),
            "size": os.path.getsize(iso),
            "sha256": digest.hexdigest(),
            "source_date_epoch": int(source_date_epoch),
        },
        handle,
        indent=2,
        sort_keys=True,
    )
    handle.write("\n")
PY
chmod 644 "$IMAGE_DIR/SHA256SUMS" "$IMAGE_DIR/release-manifest.json"
ls -lh "$ISO"
