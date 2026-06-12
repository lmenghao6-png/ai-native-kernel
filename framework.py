#!/usr/bin/env python3
"""
AegisOS Agent Framework — plugin-based autonomous AI runtime.

Models plug into this framework. The framework handles:
- Sensor plugins: gather system state
- Actor plugins: execute actions
- Memory: persistent context (SQLite)
- Goals: long-term objectives
- Planner: LLM-backed decision engine

Any OpenAI-compatible model can plug in as the planner.
Sensors and actors are self-registering plugins.
"""

import json, os, subprocess, sys, time, importlib, inspect
from urllib.parse import urlparse
from pathlib import Path
from abc import ABC, abstractmethod
from collections import deque
from typing import Any, Callable

# ─── Plugin Base ──────────────────────────────────────

class Sensor(ABC):
    """Plugins that gather observations from the system."""
    name: str = ""
    interval: int = 60  # seconds between polls
    
    @abstractmethod
    def observe(self) -> dict:
        """Return structured observation data."""
        ...

class Actor(ABC):
    """Plugins that execute actions on the system."""
    name: str = ""
    
    @abstractmethod
    def capabilities(self) -> list[dict]:
        """Return list of {name, description, parameters, risk} actions."""
        ...
    
    @abstractmethod
    def execute(self, action_name: str, params: dict) -> dict:
        """Execute an action. Return {success, output, error}."""
        ...

# ─── Plugin Registry ──────────────────────────────────

class PluginRegistry:
    _sensors: dict[str, type[Sensor]] = {}
    _actors: dict[str, type[Actor]] = {}
    _sensor_instances: dict[str, Sensor] = {}
    _actor_instances: dict[str, Actor] = {}
    
    @classmethod
    def register_sensor(cls, sensor_cls: type[Sensor]):
        cls._sensors[sensor_cls.name] = sensor_cls
    
    @classmethod
    def register_actor(cls, actor_cls: type[Actor]):
        cls._actors[actor_cls.name] = actor_cls
    
    @classmethod
    def get_sensor(cls, name: str) -> Sensor | None:
        if name not in cls._sensor_instances:
            if name not in cls._sensors:
                return None
            cls._sensor_instances[name] = cls._sensors[name]()
        return cls._sensor_instances[name]
    
    @classmethod
    def get_actor(cls, name: str) -> Actor | None:
        if name not in cls._actor_instances:
            if name not in cls._actors:
                return None
            cls._actor_instances[name] = cls._actors[name]()
        return cls._actor_instances[name]
    
    @classmethod
    def list_sensors(cls) -> list[str]:
        return list(cls._sensors.keys())
    
    @classmethod
    def list_actors(cls) -> list[str]:
        return list(cls._actors.keys())
    
    @classmethod
    def all_actor_capabilities(cls) -> list[dict]:
        caps = []
        for name in cls._actors:
            actor = cls.get_actor(name)
            if actor:
                for cap in actor.capabilities():
                    cap["actor"] = name
                    caps.append(cap)
        return caps

# Decorators for easy registration
def sensor(cls):
    PluginRegistry.register_sensor(cls)
    return cls

def actor(cls):
    PluginRegistry.register_actor(cls)
    return cls

# ─── Memory ───────────────────────────────────────────

class AgentMemory:
    def __init__(self, db_path: str = "/var/lib/aegisos/agent_memory.db"):
        import sqlite3
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()
    
    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                sensor TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                params TEXT NOT NULL,
                result TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created REAL NOT NULL,
                goal TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                completed REAL
            );
            CREATE TABLE IF NOT EXISTS context (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_obs_time ON observations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_act_time ON actions(timestamp);
        """)
        self.conn.commit()
    
    def record_observation(self, sensor: str, data: dict):
        self.conn.execute(
            "INSERT INTO observations (timestamp, sensor, data) VALUES (?, ?, ?)",
            (time.time(), sensor, json.dumps(data, ensure_ascii=False))
        )
        self.conn.commit()
    
    def record_action(self, actor: str, action: str, params: dict, result: dict):
        self.conn.execute(
            "INSERT INTO actions (timestamp, actor, action, params, result) VALUES (?, ?, ?, ?, ?)",
            (time.time(), actor, action, json.dumps(params), json.dumps(result))
        )
        self.conn.commit()
    
    def recent_observations(self, seconds: int = 300) -> list[dict]:
        cutoff = time.time() - seconds
        rows = self.conn.execute(
            "SELECT sensor, data, timestamp FROM observations WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 50",
            (cutoff,)
        ).fetchall()
        return [{"sensor": r[0], "data": json.loads(r[1]), "timestamp": r[2]} for r in rows]
    
    def recent_actions(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT actor, action, params, result, timestamp FROM actions ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"actor": r[0], "action": r[1], "params": json.loads(r[2]), "result": json.loads(r[3]), "timestamp": r[4]} for r in rows]
    
    def add_goal(self, goal: str):
        self.conn.execute(
            "INSERT INTO goals (created, goal) VALUES (?, ?)",
            (time.time(), goal)
        )
        self.conn.commit()
    
    def active_goals(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT goal FROM goals WHERE status = 'active' ORDER BY created"
        ).fetchall()
        return [r[0] for r in rows]
    
    def complete_goal(self, goal_id: int):
        self.conn.execute(
            "UPDATE goals SET status = 'completed', completed = ? WHERE id = ?",
            (time.time(), goal_id)
        )
        self.conn.commit()
    
    def set_context(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO context (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()
    
    def get_context(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM context WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

# ─── Planner ──────────────────────────────────────────

class Planner(ABC):
    @abstractmethod
    def decide(self, observations: list[dict], goals: list[str], history: list[dict], capabilities: list[dict]) -> dict:
        """Given current state, decide what to do next.
        Returns: {action: str, params: dict, reasoning: str, risk: str}
        """
        ...


class LLMPlanner(Planner):
    """OpenAI-compatible LLM as the decision engine."""
    
    SYSTEM_PROMPT = """You are an autonomous AI operator. Based on sensor observations and goals, decide what action to take.

Available actions:
{capabilities}

Active goals:
{goals}

Recent observations:
{observations}

Recent action history:
{history}

Respond with a JSON decision:
{{
  "action": "<action_name>",
  "actor": "<actor_name>", 
  "params": {{}},
  "reasoning": "<why you chose this>",
  "risk": "low|medium|high"
}}

OR if nothing to do:
{{
  "action": "wait",
  "reasoning": "system nominal"
}}
"""
    
    def __init__(self, endpoint: str = None, model: str = None, key: str = None):
        self.endpoint = endpoint or os.environ.get("AI_ENDPOINT", "https://api.deepseek.com/v1")
        self.model = model or os.environ.get("AI_MODEL", "deepseek-chat")
        self.key = key or os.environ.get("OPENAI_API_KEY", "")
        self.local_model_enabled = True
        self.local_model = os.environ.get(
            "AI_LOCAL_MODEL",
            "/usr/local/share/aegisos/models/qwen2.5-0.5b-q4_k_m.gguf",
        )
        self.llama_cli = os.environ.get(
            "AI_LLAMA_CLI",
            "/usr/local/libexec/aegisos/llama-cli",
        )
        
        # Load from config
        for path in ["/etc/aegisos/ai-agent.conf", os.path.expanduser("~/.config/aegisos/ai-agent.conf")]:
            try:
                with open(path) as f:
                    section = None
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or line.startswith(";"): continue
                        if line.startswith("[") and line.endswith("]"): section = line[1:-1]; continue
                        if "=" in line and section == "api":
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip()
                            if k == "endpoint": self.endpoint = v
                            elif k == "model": self.model = v
                            elif k == "key" and v: self.key = v
                            elif k == "local_model_enabled":
                                self.local_model_enabled = v.lower() in ("true", "yes", "1")
            except FileNotFoundError:
                pass

    def _cloud_available(self) -> bool:
        if self.key:
            return True
        try:
            hostname = urlparse(self.endpoint).hostname
        except ValueError:
            return False
        return hostname in ("localhost", "127.0.0.1", "::1")

    def _local_available(self) -> bool:
        return (
            self.local_model_enabled
            and os.path.isfile(self.local_model)
            and os.access(self.llama_cli, os.X_OK)
        )

    def _call_local(self, messages: list[dict]) -> str | None:
        prompt = ""
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"

        try:
            result = subprocess.run(
                [
                    self.llama_cli,
                    "-m",
                    self.local_model,
                    "-p",
                    prompt,
                    "-n",
                    "512",
                    "--temp",
                    "0.3",
                    "--log-disable",
                    "--no-display-prompt",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        if result.returncode != 0:
            return None
        text = result.stdout.strip()
        for stop in ("<|im_end|>", "<|im_start|>"):
            if stop in text:
                text = text.split(stop, 1)[0]
        return text.strip() or None

    @staticmethod
    def _parse_decision(text: str | None) -> dict | None:
        if not text:
            return None
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return None
        try:
            decision = json.loads(match.group())
        except json.JSONDecodeError:
            return None
        return decision if isinstance(decision, dict) else None
    
    def decide(self, observations, goals, history, capabilities) -> dict:
        if not self.endpoint.endswith("/chat/completions"):
            endpoint = self.endpoint.rstrip("/") + "/chat/completions"
        else:
            endpoint = self.endpoint
        
        caps_text = json.dumps(capabilities, indent=2, ensure_ascii=False)
        obs_text = json.dumps(observations[-5:], indent=2, ensure_ascii=False)
        hist_text = json.dumps(history[-3:], indent=2, ensure_ascii=False)
        goals_text = "\n".join(f"- {g}" for g in goals) if goals else "No active goals"
        
        prompt = self.SYSTEM_PROMPT.format(
            capabilities=caps_text,
            goals=goals_text,
            observations=obs_text,
            history=hist_text,
        )
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Analyze and decide the next action."},
        ]
        
        cloud_error = None
        if self._cloud_available():
            try:
                import urllib.request, urllib.error
                body = json.dumps({
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 512,
                }).encode()

                headers = {"Content-Type": "application/json"}
                if self.key:
                    headers["Authorization"] = f"Bearer {self.key}"
                req = urllib.request.Request(
                    endpoint,
                    data=body,
                    headers=headers,
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read())
                    text = result["choices"][0]["message"]["content"]
                decision = self._parse_decision(text)
                if decision:
                    return decision
                cloud_error = "could not parse LLM response"
            except Exception as e:
                cloud_error = str(e)

        if self._local_available():
            decision = self._parse_decision(self._call_local(messages))
            if decision:
                return decision
            return {"action": "wait", "reasoning": "could not parse local LLM response"}

        if cloud_error:
            return {"action": "wait", "reasoning": f"LLM error: {cloud_error}"}
        return {"action": "wait", "reasoning": "no AI backend configured"}

# ─── Runtime ──────────────────────────────────────────

ROOT_AUDIT_LOG = os.environ.get(
    "AEGISOS_ROOT_AUDIT_LOG",
    "/var/log/aegisos/root-actions.jsonl",
)


def root_capabilities() -> list[dict]:
    """Return every registered action available to the root AI runtime."""
    return [
        {**capability, "execution": "root"}
        for capability in PluginRegistry.all_actor_capabilities()
    ]


def audit_root_action(event: str, actor: str, action: str, payload: dict):
    """Append a durable action event for auditd and journal collection."""
    record = {
        "timestamp": time.time(),
        "event": event,
        "actor": actor,
        "action": action,
        "payload": payload,
    }
    encoded = json.dumps(record, ensure_ascii=True, sort_keys=True)
    print(f"[agent-root-audit] {encoded}", flush=True)
    try:
        parent = os.path.dirname(ROOT_AUDIT_LOG)
        if parent:
            os.makedirs(parent, mode=0o750, exist_ok=True)
        descriptor = os.open(
            ROOT_AUDIT_LOG,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY,
            0o600,
        )
        try:
            os.write(descriptor, (encoded + "\n").encode())
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        print(f"[agent-root-audit] write failed: {error}", flush=True)


class AgentRuntime:
    def __init__(self, planner: Planner = None, memory: AgentMemory = None):
        self.planner = planner or LLMPlanner()
        self.memory = memory or AgentMemory()
        self._running = False
        self._tick = 0
    
    def observe_all(self):
        """Run all sensors and record observations."""
        observations = []
        for name in PluginRegistry.list_sensors():
            sensor = PluginRegistry.get_sensor(name)
            if sensor and self._tick % (sensor.interval // 10 or 1) == 0:
                try:
                    data = sensor.observe()
                    self.memory.record_observation(name, data)
                    observations.append({"sensor": name, "data": data})
                except Exception as e:
                    print(f"[agent] sensor {name} error: {e}")
        return observations
    
    def decide(self, observations):
        """Run planner to decide next action."""
        goals = self.memory.active_goals()
        history = self.memory.recent_actions(10)
        capabilities = root_capabilities()
        return self.planner.decide(observations, goals, history, capabilities)
    
    def act(self, decision):
        """Execute the planner's decision."""
        action_name = decision.get("action", "wait")
        if action_name == "wait":
            return
        
        actor_name = decision.get("actor", "")
        actor = PluginRegistry.get_actor(actor_name)
        if not actor:
            return
        
        params = decision.get("params", {})
        audit_root_action(
            "started",
            actor_name,
            action_name,
            {
                "params": params,
                "reasoning": decision.get("reasoning", ""),
                "risk": decision.get("risk", ""),
            },
        )
        try:
            result = actor.execute(action_name, params)
            self.memory.record_action(actor_name, action_name, params, result)
            audit_root_action("completed", actor_name, action_name, result)
            return result
        except Exception as e:
            error = {"success": False, "error": str(e)}
            self.memory.record_action(actor_name, action_name, params, error)
            audit_root_action("failed", actor_name, action_name, error)
            return error
    
    def run_forever(self, tick_interval: float = 10.0):
        """Main agent loop."""
        self._running = True
        while self._running:
            try:
                observations = self.observe_all()
                if observations:
                    decision = self.decide(observations)
                    self.act(decision)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[agent] cycle error: {e}")
            
            self._tick += 1
            time.sleep(tick_interval)
    
    def start_background(self, tick_interval: float = 10.0):
        import threading
        t = threading.Thread(target=self.run_forever, args=(tick_interval,), daemon=True)
        t.start()
        return t


def _load_tick_interval(default: float = 10.0) -> float:
    for path in ["/etc/aegisos/ai-agent.conf", os.path.expanduser("~/.config/aegisos/ai-agent.conf")]:
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
                    if "=" in line and section == "agent":
                        key, value = line.split("=", 1)
                        if key.strip() == "tick_interval":
                            return float(value.strip())
        except (FileNotFoundError, PermissionError, ValueError):
            continue
    return default


def main():
    sys.modules.setdefault("framework", sys.modules[__name__])
    import plugins  # noqa: F401 - imported for plugin self-registration

    runtime = AgentRuntime()
    runtime.run_forever(_load_tick_interval())


if __name__ == "__main__":
    main()
