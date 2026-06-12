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
        systemctl is-active aegisos-model 2>/dev/null && echo "local model: running" || echo "local model: stopped"
        systemctl is-active aegisosd 2>/dev/null && echo "root AI: running" || echo "root AI: stopped"
        systemctl is-active guardian 2>/dev/null && echo "guardian: running" || echo "guardian: stopped"
        test -e /etc/aegisos/agent-disabled && echo "emergency stop: engaged" || echo "emergency stop: clear"
        ;;
    doctor)
        for svc in aegisos-model aegisosd guardian ssh auditd; do
            systemctl is-active "$svc" 2>/dev/null && echo "[OK] $svc" || echo "[!!] $svc"
        done
        curl -fsS --max-time 3 http://127.0.0.1:8080/health >/dev/null 2>&1 &&
            echo "[OK] local model endpoint" || echo "[!!] local model endpoint"
        test "$(systemctl show -p User --value aegisosd)" = "" &&
            echo "[OK] root AI identity" || echo "[!!] root AI identity"
        df -h / | awk 'NR==2{print "Disk: " $5 " used"}'
        free -h | awk '/Mem:/{print "Memory: " $3 "/" $2}'
        ;;
    logs) journalctl -u aegisos-model -u aegisosd -u guardian --no-pager -n "${2:-50}" -f ;;
    root-audit) sudo tail -n "${2:-50}" /var/log/aegisos/root-actions.jsonl ;;
    update)
        shift
        test $# -ge 1 || { echo "Usage: aegisctl update MANIFEST [SIGNATURE]" >&2; exit 2; }
        if test $# -ge 2; then
            sudo aegis-update apply "$1" --signature "$2"
        else
            sudo aegis-update apply "$1"
        fi
        ;;
    rollback) sudo aegis-update rollback ;;
    ai-stop)
        sudo install -m 600 /dev/null /etc/aegisos/agent-disabled
        sudo systemctl stop aegisosd guardian aegisos-model
        echo "AI emergency stop engaged."
        ;;
    ai-start)
        sudo rm -f /etc/aegisos/agent-disabled
        sudo systemctl start aegisos-model aegisosd guardian
        echo "AI emergency stop cleared."
        ;;
    *) echo "Usage: aegisctl {status|doctor|logs|root-audit|update|rollback|ai-stop|ai-start}" ;;
esac
'''.replace('@VERSION@', VERSION), 0o755)
W('/usr/local/bin/ai-console', '''#!/usr/bin/env python3
import configparser, json, os, subprocess, sys
from urllib.parse import urlparse
CONFIG=os.environ.get('AEGISOS_AI_CONFIG','/etc/aegisos/ai-agent.conf')
MODEL=os.environ.get('AEGISOS_MODEL','/usr/local/share/aegisos/models/qwen2.5-0.5b-q4_k_m.gguf')
LLAMA=os.environ.get('AEGISOS_LLAMA','/usr/local/libexec/aegisos/llama-cli')
DEFAULT_ENDPOINT='http://127.0.0.1:8080/v1'
def settings():
    c=configparser.ConfigParser()
    c.read(CONFIG)
    api=c['api'] if c.has_section('api') else {}
    return {
        'endpoint':api.get('endpoint',DEFAULT_ENDPOINT).rstrip('/'),
        'model':api.get('model','qwen2.5-0.5b-instruct'),
        'key':api.get('key',''),
        'local_enabled':api.get('local_model_enabled','true').lower() in ('true','yes','1'),
    }
def cloud_available(s):
    return bool(s['key']) or urlparse(s['endpoint']).hostname in ('localhost','127.0.0.1','::1')
def cloud(p,s):
    import urllib.request
    endpoint=s['endpoint']
    if not endpoint.endswith('/chat/completions'): endpoint += '/chat/completions'
    b=json.dumps({'model':s['model'],'messages':[{'role':'user','content':p}],'temperature':0.7,'max_tokens':1024}).encode()
    headers={'Content-Type':'application/json'}
    if s['key']: headers['Authorization']='Bearer '+s['key']
    r=urllib.request.Request(endpoint,data=b,headers=headers,method='POST')
    return json.loads(urllib.request.urlopen(r,timeout=60).read())['choices'][0]['message']['content']
def local(p):
    m = '<|im_start|>user\\n'+p+'<|im_end|>\\n<|im_start|>assistant\\n'
    return subprocess.run([LLAMA,'-m',MODEL,'-p',m,'-n','256','--temp','0.7','--single-turn','--simple-io','--no-conversation','--no-display-prompt','--log-disable'],capture_output=True,text=True,timeout=60).stdout.strip()
def ask(p):
    s=settings()
    if cloud_available(s):
        try: return cloud(p,s)
        except Exception:
            if not (s['local_enabled'] and os.path.exists(MODEL) and os.access(LLAMA,os.X_OK)): raise
    if s['local_enabled'] and os.path.exists(MODEL) and os.access(LLAMA,os.X_OK): return local(p)
    return 'No AI backend. Configure an API key, a local endpoint, or a local model.'
if len(sys.argv)>1:
    p=' '.join(sys.argv[1:])
    try: print(ask(p))
    except Exception as e: print('Error: '+str(e))
else:
    print('AegisOS AI Console @VERSION@')
    while True:
        try: c=input('aegis> ').strip()
        except (EOFError,KeyboardInterrupt): break
        if c in ('/exit','/quit'): break
        if c=='/help': print('/status /doctor /help /exit'); continue
        if not c: continue
        try: print(ask(c))
        except Exception as e: print('Error: '+str(e))
'''.replace('@VERSION@', VERSION), 0o755)
with open(os.path.join(SCRIPT_DIR, 'aegisos-install.sh')) as installer:
    W('/usr/local/bin/aegisos-install', installer.read(), 0o755)
for source, destination, mode in (
    ('aegis-update.py', '/usr/local/bin/aegis-update', 0o755),
    ('aegis-uninstall.sh', '/usr/local/sbin/aegis-uninstall', 0o755),
):
    with open(os.path.join(SCRIPT_DIR, source)) as handle:
        W(destination, handle.read(), mode)
root_service = '''UMask=0077
Environment=PYTHONUNBUFFERED=1
'''
W('/etc/systemd/system/aegisos-model.service', '''[Unit]
Description=AegisOS Bundled Local Model
After=network.target
Before=aegisosd.service guardian.service
ConditionPathExists=/usr/local/share/aegisos/models/qwen2.5-0.5b-q4_k_m.gguf
ConditionPathExists=!/etc/aegisos/agent-disabled

[Service]
Type=simple
Environment=LD_LIBRARY_PATH=/usr/local/libexec/aegisos/llama-b9603
WorkingDirectory=/usr/local/libexec/aegisos/llama-b9603
ExecStart=/usr/local/libexec/aegisos/llama-b9603/llama-server --model /usr/local/share/aegisos/models/qwen2.5-0.5b-q4_k_m.gguf --alias qwen2.5-0.5b-instruct --host 127.0.0.1 --port 8080 --ctx-size 2048 --parallel 2 --no-ui --log-disable
Restart=on-failure
RestartSec=10
DynamicUser=yes
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
LockPersonality=yes
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6

[Install]
WantedBy=multi-user.target
''')
W('/etc/systemd/system/aegisosd.service', f'''[Unit]
Description=AegisOS Root AI Agent
Wants=aegisos-model.service
After=network.target aegisos-model.service
ConditionPathExists=!/etc/aegisos/agent-disabled

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/lib/aegisos/framework.py
WorkingDirectory=/usr/local/lib/aegisos
Restart=on-failure
RestartSec=10
{root_service}
[Install]
WantedBy=multi-user.target
''')
W('/etc/systemd/system/guardian.service', f'''[Unit]
Description=Aegis Root Guardian Monitor
Wants=aegisos-model.service
After=network.target aegisos-model.service
ConditionPathExists=!/etc/aegisos/agent-disabled

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/lib/aegisos/guardian.py
WorkingDirectory=/usr/local/lib/aegisos
Restart=on-failure
RestartSec=30
{root_service}
[Install]
WantedBy=multi-user.target
''')
W('/usr/lib/tmpfiles.d/aegisos.conf', '''d /run/aegisos 0700 root root -
d /var/lib/aegisos 0700 root root -
d /var/log/aegisos 0700 root root -
f /var/log/aegisos/root-actions.jsonl 0600 root root -
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
for svc in ['aegisos-model.service', 'aegisosd.service', 'guardian.service']:
    dst = os.path.join(wants, svc)
    if not os.path.lexists(dst):
        os.symlink('/etc/systemd/system/' + svc, dst)

print('Done.')
