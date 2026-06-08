#!/bin/bash
# build-aegisos-rootfs.sh -- Build AegisOS Debian bookworm rootfs
# Creates: build/aegisos/linux-rootfs/
# Requires: mmdebstrap (run on Debian/Ubuntu GitHub Actions runner)

set -euo pipefail

ROOTFS="build/aegisos/linux-rootfs"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== AegisOS Rootfs Builder ==="
echo "Target: $ROOTFS"

# Clean previous build
sudo rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"

# Stage 1: Bootstrap Debian bookworm
echo "[1/5] Bootstrapping Debian bookworm base system..."
sudo mmdebstrap \
    --variant=minbase \
    --include="linux-image-amd64,initramfs-tools,systemd,systemd-sysv, \
bash,coreutils,util-linux,apt,dpkg,udev, \
sudo,passwd,adduser,locales,hostname, \
netbase,iproute2,iputils-ping,wget,curl,ca-certificates, \
openssh-server,openssh-client, \
ufw, \
python3,python3-pip, \
git,gcc,make,vim,htop, \
grub-pc-bin,grub-efi-amd64-bin, \
network-manager,isc-dhcp-client, \
console-setup,kbd,less,nano,tree,file" \
    bookworm \
    "$ROOTFS" \
    http://deb.debian.org/debian

echo "Rootfs bootstrapped: $(sudo du -sh "$ROOTFS" | cut -f1)"

# Stage 2: Directory structure
echo "[2/5] Creating AegisOS directory structure..."
sudo mkdir -p "$ROOTFS/etc/aegisos"
sudo mkdir -p "$ROOTFS/usr/local/lib/aegisos"
sudo mkdir -p "$ROOTFS/usr/local/libexec/aegisos"
sudo mkdir -p "$ROOTFS/usr/local/share/aegisos/models"
sudo mkdir -p "$ROOTFS/var/lib/aegisos"
sudo mkdir -p "$ROOTFS/var/log/aegisos"
sudo mkdir -p "$ROOTFS/run/aegisos"

# Stage 3: Copy agent framework
echo "[3/5] Installing AegisOS Agent Framework..."
for f in framework.py guardian.py plugins.py; do
    sudo cp "$REPO_DIR/$f" "$ROOTFS/usr/local/lib/aegisos/"
    sudo chmod 644 "$ROOTFS/usr/local/lib/aegisos/$f"
done
echo '"""AegisOS Agent Framework"""' | sudo tee "$ROOTFS/usr/local/lib/aegisos/__init__.py" > /dev/null

# Stage 4: Configuration
echo "[4/5] Writing configuration files..."

# ai-agent.conf
sudo tee "$ROOTFS/etc/aegisos/ai-agent.conf" > /dev/null << 'CONFEOF'
[api]
endpoint = https://api.deepseek.com/v1
model = deepseek-chat
key =
local_model_enabled = true

[agent]
tick_interval = 10

[guardian]
enabled = true
interval = 60
auto_execute_safe = true
goals = Keep the system secure and stable. Monitor disk space, memory, and service health.
CONFEOF

# Set root password (for live system convenience)
echo "root:aegisos" | sudo chroot "$ROOTFS" chpasswd 2>/dev/null || true

# SSH: key-only authentication
sudo sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' "$ROOTFS/etc/ssh/sshd_config" 2>/dev/null || true
sudo sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' "$ROOTFS/etc/ssh/sshd_config" 2>/dev/null || true

# MOTD banner
sudo tee "$ROOTFS/etc/motd" > /dev/null << 'MOTDEOF'

  ___                 _      ___  ____
 / _ \               (_)    / _ \/ ___|
/ /_\ \  __ _  ___ _  ___ | | | \___ \
|  _  | / _` |/ _ \ |/ _ \| | | |___) |
| | | || (_| |  __/ | (_) | |_| |____/
\_| |_/ \__, |\___|_|\___/ \___/
         __/ |
        |___/

   AI-Native Operating System v0.3-beta

   Type 'ai-console' for natural language interface.
   Type 'aegisctl status' for system overview.
MOTDEOF

# Remove dynamic MOTD scripts
sudo rm -f "$ROOTFS/etc/update-motd.d/"* 2>/dev/null || true

# Stage 5: Install CLI tools and systemd services
echo "[5/5] Installing CLI tools and systemd services..."
python3 "$REPO_DIR/tools/install-agents.py" "$ROOTFS"

echo ""
echo "=== Build complete ==="
echo "Rootfs: $ROOTFS"
sudo du -sh "$ROOTFS"
