#!/bin/bash
# build-aegisos-rootfs.sh -- Build AegisOS Debian bookworm rootfs
# Creates: build/aegisos/linux-rootfs/
# Requires: mmdebstrap (run on Debian/Ubuntu GitHub Actions runner)

set -euo pipefail

ROOTFS="build/aegisos/linux-rootfs"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$REPO_DIR/VERSION"

if [ ! -f "$VERSION_FILE" ]; then
    echo "Version file not found: $VERSION_FILE" >&2
    exit 1
fi
AEGISOS_VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
if [[ ! "$AEGISOS_VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?(-[a-z0-9]+([.-][a-z0-9]+)*)?$ ]]; then
    echo "Invalid AegisOS version: $AEGISOS_VERSION" >&2
    exit 1
fi

echo "=== AegisOS Rootfs Builder ==="
echo "Target: $ROOTFS"

KEYRING_ARGS=()
if [ -f /usr/share/keyrings/debian-archive-keyring.gpg ]; then
    KEYRING_ARGS=(--keyring=/usr/share/keyrings/debian-archive-keyring.gpg)
fi

# Clean previous build
sudo rm -rf "$ROOTFS"
mkdir -p "$ROOTFS"

# Stage 1: Bootstrap Debian bookworm
echo "[1/6] Bootstrapping Debian bookworm base system..."
sudo mmdebstrap \
    --variant=minbase \
    "${KEYRING_ARGS[@]}" \
    --include="linux-image-amd64,initramfs-tools,systemd,systemd-sysv, \
bash,coreutils,util-linux,apt,dpkg,udev, \
sudo,passwd,adduser,locales,hostname, \
netbase,iproute2,iputils-ping,wget,curl,ca-certificates, \
openssh-server,openssh-client, \
ufw, \
auditd,apparmor,apparmor-utils,gpgv, \
python3,python3-pip, \
git,gcc,make,vim,htop, \
grub2-common,grub-pc-bin,grub-efi-amd64-bin, \
parted,dosfstools,rsync, \
network-manager,isc-dhcp-client, \
console-setup,kbd,less,nano,tree,file, \
live-boot,live-config" \
    bookworm \
    "$ROOTFS" \
    http://deb.debian.org/debian

echo "Rootfs bootstrapped: $(sudo du -sh "$ROOTFS" | cut -f1)"

# Stage 2: Directory structure
echo "[2/6] Creating AegisOS directory structure..."
sudo mkdir -p "$ROOTFS/etc/aegisos"
sudo mkdir -p "$ROOTFS/usr/local/lib/aegisos"
sudo mkdir -p "$ROOTFS/usr/local/libexec/aegisos"
sudo mkdir -p "$ROOTFS/usr/local/share/aegisos/models"
sudo mkdir -p "$ROOTFS/var/lib/aegisos"
sudo mkdir -p "$ROOTFS/var/log/aegisos"
sudo mkdir -p "$ROOTFS/run/aegisos"
sudo mkdir -p "$ROOTFS/etc/network"
sudo chroot "$ROOTFS" chown -R root:root \
    /var/lib/aegisos /var/log/aegisos /run/aegisos
sudo chroot "$ROOTFS" chmod 0700 \
    /var/lib/aegisos /var/log/aegisos /run/aegisos
sudo chroot "$ROOTFS" useradd --create-home --shell /bin/bash \
    --groups sudo aegis-live
echo "aegis-live:aegisos" | sudo chroot "$ROOTFS" chpasswd
sudo chroot "$ROOTFS" passwd --lock root
sudo tee "$ROOTFS/etc/sudoers.d/aegis-live" > /dev/null <<'EOF'
aegis-live ALL=(ALL:ALL) NOPASSWD: ALL
EOF
sudo chmod 440 "$ROOTFS/etc/sudoers.d/aegis-live"

# Stage 3: Copy agent framework
echo "[3/6] Installing AegisOS Agent Framework..."
for f in framework.py guardian.py plugins.py; do
    sudo cp "$REPO_DIR/$f" "$ROOTFS/usr/local/lib/aegisos/"
    case "$f" in
        framework.py|guardian.py) sudo chmod 755 "$ROOTFS/usr/local/lib/aegisos/$f" ;;
        *) sudo chmod 644 "$ROOTFS/usr/local/lib/aegisos/$f" ;;
    esac
done
echo '"""AegisOS Agent Framework"""' | sudo tee "$ROOTFS/usr/local/lib/aegisos/__init__.py" > /dev/null

# Stage 4: Local model
echo "[4/6] Installing bundled Qwen2.5 0.5B model..."
bash "$REPO_DIR/tools/install-local-model.sh" "$ROOTFS"

# Stage 5: Configuration
echo "[5/6] Writing configuration files..."

# ai-agent.conf
sudo tee "$ROOTFS/etc/aegisos/ai-agent.conf" > /dev/null << 'CONFEOF'
[api]
endpoint = http://127.0.0.1:8080/v1
model = qwen2.5-0.5b-instruct
key =
local_model_enabled = false

[agent]
tick_interval = 10
privilege_mode = root
CONFEOF

sudo tee "$ROOTFS/etc/aegisos/guardian.conf" > /dev/null << 'CONFEOF'
[guardian]
enabled = true
interval = 60
auto_execute_root = true
goals = Keep the system secure and stable. Monitor disk space, memory, and service health.
CONFEOF
echo "$AEGISOS_VERSION" | sudo tee "$ROOTFS/etc/aegisos/version" > /dev/null
echo "2" | sudo tee "$ROOTFS/etc/aegisos/config-schema" > /dev/null
sudo chroot "$ROOTFS" chown root:root /etc/aegisos/ai-agent.conf
sudo chroot "$ROOTFS" chown root:root /etc/aegisos/guardian.conf
sudo chmod 600 \
    "$ROOTFS/etc/aegisos/ai-agent.conf" \
    "$ROOTFS/etc/aegisos/guardian.conf"
sudo chmod 644 \
    "$ROOTFS/etc/aegisos/version" \
    "$ROOTFS/etc/aegisos/config-schema"

if [[ -n "${AEGISOS_RELEASE_PUBLIC_KEY:-}" ]]; then
    sudo install -Dm644 "$AEGISOS_RELEASE_PUBLIC_KEY" \
        "$ROOTFS/usr/share/keyrings/aegisos-release.gpg"
elif [[ -n "${AEGISOS_RELEASE_PUBLIC_KEY_B64:-}" ]]; then
    printf '%s' "$AEGISOS_RELEASE_PUBLIC_KEY_B64" | base64 -d | \
        sudo tee "$ROOTFS/usr/share/keyrings/aegisos-release.gpg" > /dev/null
    sudo chmod 644 "$ROOTFS/usr/share/keyrings/aegisos-release.gpg"
fi

sudo rm -f "$ROOTFS/etc/os-release"
sudo tee "$ROOTFS/etc/os-release" > /dev/null <<EOF
PRETTY_NAME="AegisOS $AEGISOS_VERSION"
NAME="AegisOS"
VERSION_ID="$AEGISOS_VERSION"
VERSION="$AEGISOS_VERSION (Developer Preview)"
VERSION_CODENAME=bookworm
ID=aegisos
ID_LIKE=debian
HOME_URL="https://github.com/lmenghao6-png/ai-native-kernel"
SUPPORT_URL="https://github.com/lmenghao6-png/ai-native-kernel/issues"
BUG_REPORT_URL="https://github.com/lmenghao6-png/ai-native-kernel/issues"
EOF
sudo chmod 644 "$ROOTFS/etc/os-release"

sudo tee "$ROOTFS/etc/network/interfaces" > /dev/null << 'EOF'
auto lo
iface lo inet loopback
EOF
sudo chmod 755 "$ROOTFS/etc/network"
sudo chmod 644 "$ROOTFS/etc/network/interfaces"

echo "aegisos" | sudo tee "$ROOTFS/etc/hostname" > /dev/null
sudo chmod 644 "$ROOTFS/etc/hostname"

# SSH: key-only authentication
sudo sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' "$ROOTFS/etc/ssh/sshd_config" 2>/dev/null || true
sudo sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/' "$ROOTFS/etc/ssh/sshd_config" 2>/dev/null || true
sudo chmod 600 "$ROOTFS"/etc/ssh/ssh_host_*_key 2>/dev/null || true
sudo chmod 644 "$ROOTFS"/etc/ssh/ssh_host_*_key.pub 2>/dev/null || true

# Firewall: default deny incoming traffic and allow key-only SSH access.
sudo chroot "$ROOTFS" ufw default deny incoming
sudo chroot "$ROOTFS" ufw default allow outgoing
sudo chroot "$ROOTFS" ufw allow 22/tcp
sudo sed -i 's/^ENABLED=.*/ENABLED=yes/' "$ROOTFS/etc/ufw/ufw.conf"

# Audit root AI execution and changes to its code or configuration.
sudo tee "$ROOTFS/etc/audit/rules.d/aegisos.rules" > /dev/null <<'EOF'
-w /usr/local/lib/aegisos/ -p wa -k aegisos_code
-w /etc/aegisos/ -p wa -k aegisos_config
-w /var/log/aegisos/root-actions.jsonl -p wa -k aegisos_root_actions
-w /etc/systemd/system/aegisosd.service -p wa -k aegisos_service
-w /etc/systemd/system/guardian.service -p wa -k aegisos_service
-w /etc/systemd/system/aegisos-model.service -p wa -k aegisos_service
EOF
sudo chmod 640 "$ROOTFS/etc/audit/rules.d/aegisos.rules"

sudo tee "$ROOTFS/etc/logrotate.d/aegisos" > /dev/null <<'EOF'
/var/log/aegisos/*.log /var/log/aegisos/*.jsonl {
    weekly
    rotate 12
    compress
    missingok
    notifempty
    create 0600 root root
}
EOF

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

   AI-Native Operating System @AEGISOS_VERSION@

   Type 'ai-console' for natural language interface.
   Type 'aegisctl status' for system overview.
   Offline model: Qwen2.5-0.5B-Instruct Q4_K_M
   Live login: aegis-live / aegisos
MOTDEOF
sudo sed -i "s/@AEGISOS_VERSION@/$AEGISOS_VERSION/g" "$ROOTFS/etc/motd"

printf 'AegisOS %s \\n \\l\n\n' "$AEGISOS_VERSION" | \
    sudo tee "$ROOTFS/etc/issue" > /dev/null
printf 'AegisOS %s\n' "$AEGISOS_VERSION" | \
    sudo tee "$ROOTFS/etc/issue.net" > /dev/null

# Remove dynamic MOTD scripts
sudo rm -f "$ROOTFS/etc/update-motd.d/"* 2>/dev/null || true

# Stage 6: Install CLI tools and systemd services
echo "[6/6] Installing CLI tools and systemd services..."
sudo python3 "$REPO_DIR/tools/install-agents.py" "$ROOTFS"
sudo chroot "$ROOTFS" systemctl set-default multi-user.target

echo ""
echo "=== Build complete ==="
echo "Rootfs: $ROOTFS"
sudo du -sh "$ROOTFS"
