#!/usr/bin/env python3
import os, sys
ROOTFS = sys.argv[1] if len(sys.argv) > 1 else 'build/aegisos/linux-rootfs'

def W(p, c, m=0o644):
    f = os.path.join(ROOTFS, p.lstrip('/'))
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, 'w') as fh: fh.write(c)
    os.chmod(f, m)

print('Installing AegisOS CLI tools and services...')
W('/usr/local/bin/aegisctl', '''#!/bin/bash
case "${1:-}" in
    status)
        echo "AegisOS 0.3-beta | Kernel $(uname -r)"
        systemctl is-active aegisosd 2>/dev/null && echo "aegisosd: running" || echo "aegisosd: stopped"
        systemctl is-active guardian 2>/dev/null && echo "guardian: running" || echo "guardian: stopped"
        ;;
    doctor)
        for svc in aegisosd guardian ssh; do
            systemctl is-active "$svc" 2>/dev/null && echo "[OK] $svc" || echo "[!!] $svc"
        done
        df -h / | awk 'NR==2{print "Disk: " $5 " used"}'
        free -h | awk '/Mem:/{print "Memory: " $3 "/" $2}'
        ;;
    logs) journalctl -u aegisosd -u guardian --no-pager -n "${2:-50}" -f ;;
    update) sudo apt update && sudo apt upgrade -y ;;
    *) echo "Usage: aegisctl {status|doctor|logs|update}" ;;
esac
''', 0o755)
W('/usr/local/bin/ai-console', '''#!/usr/bin/env python3
import json, os, subprocess, sys
CONFIG='/etc/aegisos/ai-agent.conf'
MODEL='/usr/local/share/aegisos/models/qwen2.5-0.5b-q4_k_m.gguf'
LLAMA='/usr/local/libexec/aegisos/llama-cli'
def key():
    if not os.path.exists(CONFIG): return ''
    for l in open(CONFIG):
        if l.startswith('key=') or l.startswith('key ='):
            return l.split('=',1)[1].strip()
    return ''
def cloud(p):
    import urllib.request
    b = json.dumps({'model':'deepseek-chat','messages':[{'role':'user','content':p}],'temperature':0.7,'max_tokens':1024}).encode()
    r = urllib.request.Request('https://api.deepseek.com/v1/chat/completions',data=b,headers={'Content-Type':'application/json','Authorization':f'Bearer {key()}'},method='POST')
    return json.loads(urllib.request.urlopen(r,timeout=60).read())['choices'][0]['message']['content']
def local(p):
    m = '<|im_start|>user\\n'+p+'<|im_end|>\\n<|im_start|>assistant\\n'
    return subprocess.run([LLAMA,'-m',MODEL,'-p',m,'-n','256','--temp','0.7','--no-display-prompt','--log-disable'],capture_output=True,text=True,timeout=60).stdout.strip()
if len(sys.argv)>1:
    p=' '.join(sys.argv[1:])
    try:
        if key(): print(cloud(p))
        elif os.path.exists(MODEL): print(local(p))
        else: print('No AI backend. Configure API key.')
    except Exception as e: print(f'Error: {e}')
else:
    print('AegisOS AI Console v0.3-beta')
    while True:
        try: c=input('aegis> ').strip()
        except (EOFError,KeyboardInterrupt): break
        if c in ('/exit','/quit'): break
        if c=='/help': print('/status /doctor /help /exit'); continue
        try:
            if key(): print(cloud(c))
            elif os.path.exists(MODEL): print(local(c))
            else: print('No AI configured.')
        except Exception as e: print(f'Error: {e}')
''', 0o755)
W('/usr/local/bin/aegisos-install', '''#!/bin/bash
set -e
clear
echo '=== AegisOS 0.3-beta Installer ==='
echo 'WARNING: This will ERASE the target disk!'
echo ''
lsblk -d -o NAME,SIZE,MODEL 2>/dev/null | grep -v loop
echo ''
read -p 'Target disk (e.g. sda): ' D
D="/dev/$D"
[ -b "$D" ] || { echo "Invalid disk"; exit 1; }
read -p 'Erase ALL data on '$D'? (yes/no): ' C
[ "$C" = "yes" ] || { echo Cancelled; exit 0; }
parted -s "$D" mklabel gpt
parted -s "$D" mkpart primary fat32 1MiB 513MiB
parted -s "$D" set 1 esp on
parted -s "$D" mkpart primary ext4 513MiB 100%
echo 'Formatting...'
mkfs.fat -F32 "${D}1"
mkfs.ext4 -F "${D}2"
echo 'Mounting...'
mount "${D}2" /mnt
mkdir -p /mnt/boot/efi
mount "${D}1" /mnt/boot/efi
echo 'Copying system...'
rsync -a --exclude=/proc --exclude=/sys --exclude=/dev --exclude=/run --exclude=/tmp --exclude=/mnt --exclude=/live --exclude=/cdrom / /mnt/
for d in proc sys dev run tmp; do mkdir -p /mnt/$d; done
echo 'Installing GRUB...'
mount --bind /dev /mnt/dev
mount --bind /proc /mnt/proc
mount --bind /sys /mnt/sys
chroot /mnt grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=AegisOS --recheck
chroot /mnt grub-install --target=i386-pc "$D" 2>/dev/null || true
chroot /mnt update-grub
echo aegisos > /mnt/etc/hostname
chroot /mnt systemctl enable aegisosd guardian ssh ufw 2>/dev/null || true
umount /mnt/boot/efi /mnt/dev /mnt/proc /mnt/sys /mnt 2>/dev/null || true
echo 'Done! Remove media and reboot.'
''', 0o755)
W('/etc/systemd/system/aegisosd.service', '[Unit]\nDescription=AegisOS Agent Daemon\nAfter=network.target\n\n[Service]\nType=simple\nExecStart=/usr/local/lib/aegisos/framework.py\nWorkingDirectory=/usr/local/lib/aegisos\nRestart=always\nRestartSec=10\nEnvironment=PYTHONUNBUFFERED=1\n\n[Install]\nWantedBy=multi-user.target\n')
W('/etc/systemd/system/guardian.service', '[Unit]\nDescription=Aegis Guardian Monitor\nAfter=network.target\n\n[Service]\nType=simple\nExecStart=/usr/local/lib/aegisos/guardian.py\nRestart=always\nRestartSec=30\nEnvironment=PYTHONUNBUFFERED=1\n\n[Install]\nWantedBy=multi-user.target\n')
W('/etc/systemd/system/aegisos-installer.service', '[Unit]\nDescription=AegisOS Installer\nAfter=multi-user.target\nConflicts=rescue.service\n\n[Service]\nType=idle\nExecStart=/usr/local/bin/aegisos-install\nStandardInput=tty\nStandardOutput=tty\nTTYPath=/dev/tty1\n\n[Install]\nWantedBy=multi-user.target\n')
wants = os.path.join(ROOTFS, 'etc/systemd/system/multi-user.target.wants')
os.makedirs(wants, exist_ok=True)
for svc in ['aegisosd.service', 'guardian.service']:
    dst = os.path.join(wants, svc)
    if not os.path.lexists(dst):
        os.symlink('/etc/systemd/system/' + svc, dst)

print('Done.')