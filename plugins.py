"""
AegisOS Agent Framework - Core Plugins

Sensors: disk, process, memory, logs, network
Actors: bash, systemd, apt
"""

import subprocess, os, time

# These will be imported by the framework's plugin system
# They register themselves via the @sensor and @actor decorators

from framework import Sensor, Actor, sensor, actor


# ─── Sensors ────────────────────────────────────────

@sensor
class DiskSensor(Sensor):
    name = "disk"
    interval = 120
    
    def observe(self):
        try:
            r = subprocess.run(["df", "-h", "/", "/tmp", "/var"], capture_output=True, text=True, timeout=10)
            lines = r.stdout.strip().split("\n")
            
            # Get inode usage too
            r2 = subprocess.run(["df", "-i", "/"], capture_output=True, text=True, timeout=10)
            inode_line = r2.stdout.strip().split("\n")[-1] if r2.stdout else ""
            
            used_pct = 0
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 5:
                    pct = parts[4].replace("%", "")
                    try:
                        pct_val = int(pct)
                        if pct_val > used_pct:
                            used_pct = pct_val
                    except ValueError:
                        pass
            
            return {
                "mounts": lines,
                "inodes": inode_line,
                "max_usage_pct": used_pct,
                "alert": used_pct > 90,
            }
        except Exception as e:
            return {"error": str(e)}


@sensor
class ProcessSensor(Sensor):
    name = "process"
    interval = 30
    
    def observe(self):
        try:
            r = subprocess.run(
                ["ps", "aux", "--sort=-%cpu", "--no-headers"],
                capture_output=True, text=True, timeout=10
            )
            top = r.stdout.strip().split("\n")[:10]
            
            # Count total processes
            total = len(subprocess.run(
                ["ps", "-e", "--no-headers"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip().split("\n"))
            
            # Check for zombie processes
            zombies = 0
            high_cpu = []
            for line in top:
                parts = line.split()
                if len(parts) >= 11:
                    try:
                        cpu = float(parts[2])
                        mem = float(parts[3])
                        if parts[7] == "Z":
                            zombies += 1
                        if cpu > 80:
                            high_cpu.append({"pid": parts[1], "cpu": cpu, "cmd": " ".join(parts[10:])[:60]})
                    except (ValueError, IndexError):
                        pass
            
            return {
                "total_processes": total,
                "zombies": zombies,
                "high_cpu": high_cpu,
                "top_by_cpu": [l[:120] for l in top[:5]],
                "alert": len(high_cpu) > 0 or zombies > 10,
            }
        except Exception as e:
            return {"error": str(e)}


@sensor
class MemorySensor(Sensor):
    name = "memory"
    interval = 60
    
    def observe(self):
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        mem[k.strip()] = v.strip()
            
            total = int(mem.get("MemTotal", "0").split()[0])
            available = int(mem.get("MemAvailable", "0").split()[0])
            free = int(mem.get("MemFree", "0").split()[0])
            swap_total = int(mem.get("SwapTotal", "0").split()[0])
            swap_free = int(mem.get("SwapFree", "0").split()[0])
            
            used_pct = round((total - available) / total * 100, 1) if total > 0 else 0
            swap_pct = round((swap_total - swap_free) / swap_total * 100, 1) if swap_total > 0 else 0
            
            return {
                "total_mb": total // 1024,
                "available_mb": available // 1024,
                "used_pct": used_pct,
                "swap_total_mb": swap_total // 1024,
                "swap_used_pct": swap_pct,
                "alert": used_pct > 90 or swap_pct > 50,
            }
        except Exception as e:
            return {"error": str(e)}


@sensor
class LogSensor(Sensor):
    name = "logs"
    interval = 120
    
    def observe(self):
        try:
            # Critical/warning level logs
            r = subprocess.run(
                ["journalctl", "-p", "3", "-n", "20", "--no-pager", "-o", "short-iso"],
                capture_output=True, text=True, timeout=10
            )
            
            errors = []
            warnings = 0
            for line in r.stdout.strip().split("\n"):
                if line.strip():
                    if "error" in line.lower() or "fail" in line.lower() or "critical" in line.lower():
                        errors.append(line[:200])
                    else:
                        warnings += 1
            
            # Failed SSH logins
            r2 = subprocess.run(
                ["journalctl", "-u", "ssh", "--no-pager", "-n", "5", "-o", "short-iso"],
                capture_output=True, text=True, timeout=10
            )
            ssh_fails = 0
            for line in r2.stdout.strip().split("\n"):
                if "Failed password" in line or "authentication failure" in line.lower():
                    ssh_fails += 1
            
            return {
                "recent_errors": len(errors),
                "recent_warnings": warnings,
                "ssh_failed_logins": ssh_fails,
                "sample_errors": errors[:3],
                "alert": len(errors) > 5 or ssh_fails > 3,
            }
        except Exception as e:
            return {"error": str(e)}


@sensor
class NetworkSensor(Sensor):
    name = "network"
    interval = 60
    
    def observe(self):
        try:
            # Listening ports
            r = subprocess.run(
                ["ss", "-tlnp", "--no-header"],
                capture_output=True, text=True, timeout=10
            )
            ports = []
            for line in r.stdout.strip().split("\n"):
                parts = line.split()
                if len(parts) >= 4:
                    addr = parts[3]
                    if ":" in addr:
                        port = addr.split(":")[-1]
                        proc = parts[-1] if len(parts) > 4 else "?"
                        ports.append(f"{port}/{proc}")
            
            # Network interfaces
            r2 = subprocess.run(
                ["ip", "-br", "addr"],
                capture_output=True, text=True, timeout=10
            )
            interfaces = [l[:100] for l in r2.stdout.strip().split("\n") if l.strip()]
            
            return {
                "listening_ports": ports,
                "interfaces": interfaces,
                "new_ports_since_boot": len(ports),
            }
        except Exception as e:
            return {"error": str(e)}


# ─── Actors ─────────────────────────────────────────

@actor
class BashActor(Actor):
    name = "bash"
    
    def capabilities(self):
        return [
            {
                "name": "run_command",
                "description": "Execute a bash command",
                "parameters": {"cmd": "string"},
                "risk": "varies",
            },
            {
                "name": "read_file",
                "description": "Read file contents",
                "parameters": {"path": "string", "lines": "int (optional)"},
                "risk": "low",
            },
            {
                "name": "write_file",
                "description": "Write content to a file",
                "parameters": {"path": "string", "content": "string"},
                "risk": "medium",
            },
            {
                "name": "check_command_exists",
                "description": "Check if a command is available",
                "parameters": {"command": "string"},
                "risk": "low",
            },
        ]
    
    def execute(self, action_name, params):
        if action_name == "run_command":
            cmd = params.get("cmd", "")
            if not cmd:
                return {"success": False, "error": "no command provided"}
            try:
                r = subprocess.run(
                    ["bash", "-c", cmd],
                    capture_output=True, text=True, timeout=30
                )
                return {
                    "success": r.returncode == 0,
                    "exit_code": r.returncode,
                    "stdout": r.stdout[:1000],
                    "stderr": r.stderr[:500],
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "timed out"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        elif action_name == "read_file":
            path = params.get("path", "")
            lines = params.get("lines", 50)
            try:
                with open(path) as f:
                    content = "".join(f.readlines()[:lines])
                return {"success": True, "content": content}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        elif action_name == "write_file":
            path = params.get("path", "")
            content = params.get("content", "")
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    f.write(content)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        elif action_name == "check_command_exists":
            cmd = params.get("command", "")
            exists = subprocess.run(["which", cmd], capture_output=True).returncode == 0
            return {"success": True, "exists": exists}
        
        return {"success": False, "error": f"unknown action: {action_name}"}


@actor
class SystemdActor(Actor):
    name = "systemd"
    
    def capabilities(self):
        return [
            {
                "name": "service_status",
                "description": "Check service status",
                "parameters": {"service": "string"},
                "risk": "low",
            },
            {
                "name": "restart_service",
                "description": "Restart a service",
                "parameters": {"service": "string"},
                "risk": "medium",
            },
            {
                "name": "start_service",
                "description": "Start a service",
                "parameters": {"service": "string"},
                "risk": "low",
            },
            {
                "name": "stop_service",
                "description": "Stop a service",
                "parameters": {"service": "string"},
                "risk": "medium",
            },
            {
                "name": "list_failed",
                "description": "List failed systemd units",
                "parameters": {},
                "risk": "low",
            },
        ]
    
    def execute(self, action_name, params):
        service = params.get("service", "")
        
        try:
            if action_name == "service_status":
                r = subprocess.run(
                    ["systemctl", "status", service, "--no-pager", "-l"],
                    capture_output=True, text=True, timeout=10
                )
                return {"success": True, "status": r.stdout[:500]}
            
            elif action_name == "restart_service":
                r = subprocess.run(
                    ["systemctl", "restart", service],
                    capture_output=True, text=True, timeout=30
                )
                return {"success": r.returncode == 0, "output": r.stdout[:200] + r.stderr[:200]}
            
            elif action_name == "start_service":
                r = subprocess.run(
                    ["systemctl", "start", service],
                    capture_output=True, text=True, timeout=30
                )
                return {"success": r.returncode == 0, "output": r.stdout[:200]}
            
            elif action_name == "stop_service":
                r = subprocess.run(
                    ["systemctl", "stop", service],
                    capture_output=True, text=True, timeout=30
                )
                return {"success": r.returncode == 0, "output": r.stdout[:200]}
            
            elif action_name == "list_failed":
                r = subprocess.run(
                    ["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"],
                    capture_output=True, text=True, timeout=10
                )
                failed = [l.split()[0] for l in r.stdout.strip().split("\n") if l.strip()]
                return {"success": True, "failed_units": failed, "count": len(failed)}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        return {"success": False, "error": f"unknown action: {action_name}"}


@actor
class AptActor(Actor):
    name = "apt"
    
    def capabilities(self):
        return [
            {
                "name": "update_packages",
                "description": "Update package lists (apt update)",
                "parameters": {},
                "risk": "low",
            },
            {
                "name": "list_upgradable",
                "description": "List upgradable packages",
                "parameters": {},
                "risk": "low",
            },
            {
                "name": "install_package",
                "description": "Install a package",
                "parameters": {"package": "string"},
                "risk": "medium",
            },
        ]
    
    def execute(self, action_name, params):
        try:
            if action_name == "update_packages":
                r = subprocess.run(
                    ["apt", "update", "-qq"],
                    capture_output=True, text=True, timeout=60
                )
                return {"success": r.returncode == 0, "output": r.stderr[:200]}
            
            elif action_name == "list_upgradable":
                r = subprocess.run(
                    ["apt", "list", "--upgradable", "-qq"],
                    capture_output=True, text=True, timeout=30
                )
                packages = [l.split("/")[0] for l in r.stdout.strip().split("\n") if l.strip()]
                return {"success": True, "count": len(packages), "packages": packages[:20]}
            
            elif action_name == "install_package":
                pkg = params.get("package", "")
                r = subprocess.run(
                    ["apt", "install", "-y", "-qq", pkg],
                    capture_output=True, text=True, timeout=120
                )
                return {"success": r.returncode == 0, "output": r.stderr[:200]}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
        
        return {"success": False, "error": f"unknown action: {action_name}"}
