#!/usr/bin/env python3
import os
import sys

ROOTFS = sys.argv[1] if len(sys.argv) > 1 else 'build/aegisos/linux-rootfs'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
with open(os.path.join(REPO_DIR, 'VERSION')) as version_file:
    VERSION = version_file.read().strip()

def W(p, c, m=0o644):
    f = os.path.join(ROOTFS, p.lstrip('/'))
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, 'w') as fh: fh.write(c)
    os.chmod(f, m)

print('Installing AegisOS CLI tools and services...')
W('/usr/local/bin/aegisctl', '''#!/bin/bash
case "${1:-}" in
    status)
        echo "AegisOS @VERSION@ | Kernel $(uname -r)"
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
'''.replace('@VERSION@', VERSION), 0o755)
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
    r = urllib.request.Request('https://api.deepseek.com/v1/chat/completions',data=b,headers={'Content-Type':'application/json','Authorization':'Bearer '+key()},method='POST')
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
    except Exception as e: print('Error: '+str(e))
else:
    print('AegisOS AI Console @VERSION@')
    while True:
        try: c=input('aegis> ').strip()
        except (EOFError,KeyboardInterrupt): break
        if c in ('/exit','/quit'): break
        if c=='/help': print('/status /doctor /help /exit'); continue
        try:
            if key(): print(cloud(c))
            elif os.path.exists(MODEL): print(local(c))
            else: print('No AI configured.')
        except Exception as e: print('Error: '+str(e))
'''.replace('@VERSION@', VERSION), 0o755)
with open(os.path.join(SCRIPT_DIR, 'aegisos-install.sh')) as installer:
    W('/usr/local/bin/aegisos-install', installer.read(), 0o755)
service_hardening = '''User=aegis
Group=aegis
SupplementaryGroups=adm systemd-journal
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
CapabilityBoundingSet=
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ReadWritePaths=/var/lib/aegisos /var/log/aegisos /run/aegisos
'''
W('/etc/systemd/system/aegisosd.service', f'''[Unit]
Description=AegisOS Agent Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/lib/aegisos/framework.py
WorkingDirectory=/usr/local/lib/aegisos
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
{service_hardening}
[Install]
WantedBy=multi-user.target
''')
W('/etc/systemd/system/guardian.service', f'''[Unit]
Description=Aegis Guardian Monitor
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/lib/aegisos/guardian.py
WorkingDirectory=/usr/local/lib/aegisos
Restart=always
RestartSec=30
Environment=PYTHONUNBUFFERED=1
{service_hardening}
[Install]
WantedBy=multi-user.target
''')
W('/usr/lib/tmpfiles.d/aegisos.conf', '''d /run/aegisos 0750 aegis aegis -
d /var/lib/aegisos 0750 aegis aegis -
d /var/log/aegisos 0750 aegis aegis -
''')
W('/etc/systemd/system/aegisos-installer.service', '''[Unit]
Description=AegisOS Installer
After=live-config.service
Wants=live-config.service
Conflicts=getty@tty1.service serial-getty@ttyS0.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/aegisos-install
StandardInput=tty-force
StandardOutput=tty
StandardError=tty
TTYPath=/dev/console
''')
wants = os.path.join(ROOTFS, 'etc/systemd/system/multi-user.target.wants')
os.makedirs(wants, exist_ok=True)
for svc in ['aegisosd.service', 'guardian.service']:
    dst = os.path.join(wants, svc)
    if not os.path.lexists(dst):
        os.symlink('/etc/systemd/system/' + svc, dst)

print('Done.')
