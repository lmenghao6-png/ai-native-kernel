#!/usr/bin/env python3
"""Aegis Guardian — proactive AI system monitor and autonomous agent.

Runs as a daemon. Periodically samples system state, evaluates it through
the AI model, and takes autonomous action when safe and appropriate.

Architecture:
  system state → LLM analysis → decision (ignore/suggest/auto-act)
  
Standing orders (goals) are configured in /etc/aegisos/guardian.conf
"""

import json, os, subprocess, sys, time, urllib.request, urllib.error
from collections import deque
from pathlib import Path

CONFIG_PATH = "/etc/aegisos/guardian.conf"
AGENT_CONFIG = "/etc/aegisos/ai-agent.conf"
STATE_FILE = "/var/lib/aegisos/guardian_state.json"
LOG_FILE = "/var/log/aegisos/guardian.log"
PID_FILE = "/run/aegisos/guardian.pid"

INTERVAL = int(os.environ.get("GUARDIAN_INTERVAL", "60"))
MAX_HISTORY = 20  # How many past events to keep for context

GUARDIAN_SYSTEM_PROMPT = """You are the Guardian, an autonomous AI monitoring an AegisOS system.
You have root access. Your job is to observe, detect issues, and take proactive action.

You receive a system state snapshot periodically. For each snapshot, you must:
1. Assess if anything needs attention
2. Decide on an action level:
   - IGNORE: nothing to do
   - SUGGEST: recommend action to user (output suggestion only)
   - SAFE_AUTO: take safe action automatically (reading files, checking services)
   - NEEDS_CONFIRM: important action that needs user approval

Safe auto-actions:
- Reading system state (ps, df, free, journalctl, systemctl status)
- Restarting a crashed service
- Cleaning temp files older than 7 days  
- Updating package lists (apt update)

Needs-confirm actions:
- Installing/removing packages
- Modifying system configuration
- Killing processes
- Network/firewall changes
- Disk operations (mount, fsck)

Current goals: {goals}

System: {hostname}, kernel {kernel}, {os}, uptime {uptime}
Memory: {memory}
Disk: {disk}
Load: {load}
Top CPU processes: {top_processes}
Recent log anomalies: {log_anomalies}

Output format:
ACTION: IGNORE|SUGGEST|SAFE_AUTO|NEEDS_CONFIRM
REASON: <brief explanation of what you detected>
COMMANDS: <bash commands if SAFE_AUTO or NEEDS_CONFIRM, one per line after ```bash>
DETAIL: <detailed analysis for user>"""


def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"guardian: {msg}", flush=True)


def load_config():
    config = {
        "enabled": True,
        "interval": 60,
        "auto_execute_safe": True,
        "goals": "Keep the system secure and stable. Monitor disk space, memory, and service health.",
        "api": {"endpoint": "", "model": "", "key": ""},
    }
    # Load agent config first for API settings
    for path in [AGENT_CONFIG, os.path.expanduser("~/.config/aegisos/ai-agent.conf")]:
        try:
            with open(path) as f:
                section = None
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith(";"):
                        continue
                    if line.startswith("[") and line.endswith("]"):
                        section = line[1:-1]
                        continue
                    if "=" in line and section == "api":
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip()
                        if k in config["api"]:
                            config["api"][k] = v
        except (FileNotFoundError, PermissionError):
            continue
    
    config["api"]["key"] = config["api"]["key"] or os.environ.get("OPENAI_API_KEY", "")
    
    # Load guardian-specific config
    try:
        with open(CONFIG_PATH) as f:
            section = None
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1]
                    continue
                if "=" in line and section:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k in config:
                        if k == "auto_execute_safe":
                            config[k] = v.lower() in ("true", "yes", "1")
                        elif k == "interval":
                            config[k] = int(v)
                        else:
                            config[k] = v
    except FileNotFoundError:
        pass
    
    return config


def get_system_snapshot():
    """Gather current system state."""
    snapshot = {}
    
    # Host info
    import platform
    snapshot["hostname"] = platform.node()
    snapshot["kernel"] = platform.release()
    snapshot["os"] = " ".join(platform.freedesktop_os_release().get("PRETTY_NAME", "AegisOS").split())
    
    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_secs = float(f.read().split()[0])
            d = int(uptime_secs // 86400)
            h = int((uptime_secs % 86400) // 3600)
            m = int((uptime_secs % 3600) // 60)
            snapshot["uptime"] = f"{d}d {h}h {m}m"
    except Exception:
        snapshot["uptime"] = "unknown"
    
    # Memory
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                if ":" in line:
                    k, v = line.split(":", 1)
                    mem[k.strip()] = v.strip()
            snapshot["memory"] = f"total={mem.get('MemTotal','?')} avail={mem.get('MemAvailable','?')}"
    except Exception:
        snapshot["memory"] = "unavailable"
    
    # Disk
    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=10)
        snapshot["disk"] = r.stdout.strip().split("\n")[-1] if r.stdout else "unavailable"
    except Exception:
        snapshot["disk"] = "unavailable"
    
    # Load
    try:
        with open("/proc/loadavg") as f:
            snapshot["load"] = f.read().strip()
    except Exception:
        snapshot["load"] = "unavailable"
    
    # Top processes by CPU
    try:
        r = subprocess.run(
            ["ps", "aux", "--sort=-%cpu", "--no-headers"],
            capture_output=True, text=True, timeout=10
        )
        top = r.stdout.strip().split("\n")[:5]
        snapshot["top_processes"] = "\n".join(top) if top else "none"
    except Exception:
        snapshot["top_processes"] = "unavailable"
    
    # Recent log anomalies (errors/warnings from journal)
    try:
        r = subprocess.run(
            ["journalctl", "-p", "3", "-n", "10", "--no-pager"],
            capture_output=True, text=True, timeout=10
        )
        snapshot["log_anomalies"] = r.stdout.strip()[-500:] if r.stdout else "none"
    except Exception:
        snapshot["log_anomalies"] = "none"
    
    return snapshot


def call_llm(config, messages):
    """Call LLM - use cloud if available, local model as fallback."""
    if config["api"]["key"]:
        return call_cloud_llm(config, messages)
    else:
        return call_local_llm(messages)


def call_cloud_llm(config, messages):
    endpoint = config["api"]["endpoint"].rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"
    
    body = json.dumps({
        "model": config["api"]["model"],
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
    }).encode()
    
    req = urllib.request.Request(
        endpoint, data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api']['key']}",
        },
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())["choices"][0]["message"]["content"]
    except Exception as e:
        log(f"cloud LLM error: {e}")
        return None


def call_local_llm(messages):
    model = "/usr/local/share/aegisos/models/qwen2.5-0.5b-q4_k_m.gguf"
    llama = "/usr/local/libexec/aegisos/llama-cli"
    
    if not os.path.exists(model) or not os.path.exists(llama):
        return None
    
    prompt = ""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            prompt += f"<|im_start|>system\n{content}<|im_end|>\n"
        elif role == "user":
            prompt += f"<|im_start|>user\n{content}<|im_end|>\n"
        elif role == "assistant":
            prompt += f"<|im_start|>assistant\n{content}<|im_end|>\n"
    prompt += "<|im_start|>assistant\n"
    
    try:
        r = subprocess.run(
            [llama, "-m", model, "-p", prompt,
             "-n", "512", "--temp", "0.2", "--log-disable", "--no-display-prompt"],
            capture_output=True, text=True, timeout=60
        )
        output = r.stdout.strip()
        for stop in ["<|im_end|>", "<|im_start|>"]:
            if stop in output:
                output = output.split(stop)[0]
        return output.strip() or None
    except Exception as e:
        log(f"local LLM error: {e}")
        return None


def parse_action(response):
    """Parse LLM response into structured action."""
    if not response:
        return {"action": "IGNORE", "reason": "LLM unavailable", "commands": [], "detail": ""}
    
    action = "IGNORE"
    reason = ""
    commands = []
    detail = ""
    
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("ACTION:"):
            action = line.replace("ACTION:", "").strip()
        elif line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()
        elif line.startswith("DETAIL:"):
            detail = line.replace("DETAIL:", "").strip()
    
    # Extract commands from ```bash blocks
    import re
    for match in re.finditer(r"```(?:bash)?\n(.*?)```", response, re.DOTALL):
        for cmd in match.group(1).strip().split("\n"):
            cmd = cmd.strip()
            if cmd and not cmd.startswith("#"):
                commands.append(cmd)
    
    return {
        "action": action,
        "reason": reason,
        "commands": commands,
        "detail": detail,
        "raw_response": response,
    }


def is_safe_command(cmd):
    """Check if a command is safe to auto-execute."""
    cmd_name = cmd.strip().split()[0] if cmd.strip() else ""
    safe_cmds = {
        "ls", "cat", "df", "du", "ps", "free", "uname", "uptime",
        "dmesg", "journalctl", "systemctl", "stat", "file", "which",
        "whereis", "echo", "printenv", "id", "pwd", "date",
        "lscpu", "lsblk", "lspci", "lsusb", "ip", "ss", "ping",
        "head", "tail", "wc", "find", "grep", "who", "w", "hostname",
    }
    return cmd_name in safe_cmds


def execute_commands(commands, auto_execute_safe):
    """Execute commands, respecting safety settings."""
    results = []
    for cmd in commands:
        safe = is_safe_command(cmd)
        
        if not safe and not auto_execute_safe:
            log(f"SKIP (needs confirm): {cmd[:80]}")
            results.append({"command": cmd, "executed": False, "reason": "needs_confirm"})
            continue
        
        try:
            r = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True, text=True, timeout=30
            )
            status = "OK" if r.returncode == 0 else f"FAIL({r.returncode})"
            log(f"EXEC [{status}] {cmd[:80]}")
            results.append({
                "command": cmd, "executed": True,
                "exit_code": r.returncode,
                "stdout": r.stdout[:200],
                "stderr": r.stderr[:200],
            })
        except Exception as e:
            log(f"EXEC [ERR] {cmd[:80]}: {e}")
            results.append({"command": cmd, "executed": False, "error": str(e)})
    
    return results


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(list(state), f, ensure_ascii=False, indent=2)


def load_state():
    try:
        with open(STATE_FILE) as f:
            return deque(json.load(f), maxlen=MAX_HISTORY)
    except (FileNotFoundError, json.JSONDecodeError):
        return deque(maxlen=MAX_HISTORY)


def run_cycle(config, history):
    """One monitoring + analysis + action cycle."""
    snapshot = get_system_snapshot()
    prompt = GUARDIAN_SYSTEM_PROMPT.format(
        goals=config["goals"],
        **snapshot
    )
    
    messages = [{"role": "system", "content": prompt}]
    
    # Add recent history for context
    recent = list(history)[-3:]  # Last 3 events
    for event in recent:
        messages.append({"role": "assistant", "content": f"Previous action: {event.get('action', '?')} - {event.get('reason', '?')}"})
    
    messages.append({"role": "user", "content": "Analyze this system state snapshot and decide what action to take."})
    
    response = call_llm(config, messages)
    
    if not response:
        log("LLM unavailable, skipping cycle")
        return
    
    parsed = parse_action(response)
    
    if parsed["action"] == "IGNORE":
        log(f"IGNORE: {parsed.get('reason', 'system nominal')}")
    elif parsed["action"] == "SUGGEST":
        log(f"SUGGEST: {parsed.get('reason', '')}")
        if parsed.get("detail"):
            log(f"  Detail: {parsed['detail'][:200]}")
    elif parsed["action"] == "SAFE_AUTO":
        log(f"SAFE_AUTO: {parsed.get('reason', '')}")
        if parsed["commands"]:
            execute_commands(parsed["commands"], config["auto_execute_safe"])
    elif parsed["action"] == "NEEDS_CONFIRM":
        log(f"NEEDS_CONFIRM: {parsed.get('reason', '')}")
        log(f"  Commands pending: {len(parsed['commands'])}")
        for cmd in parsed["commands"]:
            log(f"    - {cmd[:100]}")
    
    history.append({
        "timestamp": time.time(),
        "action": parsed["action"],
        "reason": parsed.get("reason", ""),
        "snapshot_summary": f"load={snapshot.get('load','?')} mem={snapshot.get('memory','?')[:50]}",
    })
    save_state(history)


def main():
    log("Guardian starting...")
    
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    
    config = load_config()
    if not config["enabled"]:
        log("Guardian disabled in config, exiting")
        return
    
    history = load_state()
    log(f"Loaded {len(history)} historical events")
    log(f"Interval: {config['interval']}s, Goals: {config['goals'][:80]}...")
    
    while True:
        try:
            run_cycle(config, history)
        except Exception as e:
            log(f"Cycle error: {e}")
        
        time.sleep(config["interval"])


if __name__ == "__main__":
    main()
