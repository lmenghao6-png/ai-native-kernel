import os
import tempfile
import unittest
from unittest import mock

import framework
import plugins  # noqa: F401 - register core plugins


class StaticPlanner(framework.Planner):
    def __init__(self, decision):
        self.decision = decision

    def decide(self, observations, goals, history, capabilities):
        return self.decision


class AgentRuntimeTests(unittest.TestCase):
    def runtime(self, directory, decision):
        memory = framework.AgentMemory(os.path.join(directory, "memory.db"))
        return framework.AgentRuntime(
            planner=StaticPlanner(decision),
            memory=memory,
        )

    def test_registers_core_plugins(self):
        self.assertEqual(
            set(framework.PluginRegistry.list_sensors()),
            {"disk", "process", "memory", "logs", "network"},
        )
        self.assertEqual(
            set(framework.PluginRegistry.list_actors()),
            {"bash", "systemd", "apt"},
        )

    def test_allows_read_only_autonomous_action(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = self.runtime(directory, {
                "actor": "bash",
                "action": "check_command_exists",
                "params": {"command": "sh"},
            })
            result = runtime.act(runtime.decide([]))

        self.assertTrue(result["success"])
        self.assertTrue(result["exists"])

    def test_root_agent_executes_arbitrary_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = os.path.join(directory, "should-not-exist")
            runtime = self.runtime(directory, {
                "actor": "bash",
                "action": "run_command",
                "params": {"cmd": f"touch {marker}"},
            })
            result = runtime.act(runtime.decide([]))
            history = runtime.memory.recent_actions()
            marker_exists = os.path.exists(marker)

        self.assertTrue(result["success"])
        self.assertTrue(marker_exists)
        self.assertTrue(history[0]["result"]["success"])

    def test_planner_receives_every_root_capability(self):
        capabilities = framework.root_capabilities()
        execution = {
            (cap["actor"], cap["name"]): cap["execution"] for cap in capabilities
        }

        self.assertEqual(len(execution), 12)
        self.assertTrue(all(mode == "root" for mode in execution.values()))
        self.assertIn(("bash", "run_command"), execution)
        self.assertIn(("bash", "write_file"), execution)
        self.assertIn(("systemd", "restart_service"), execution)
        self.assertIn(("apt", "install_package"), execution)

    def test_root_actions_are_written_to_audit_log(self):
        with tempfile.TemporaryDirectory() as directory:
            audit_log = os.path.join(directory, "root-actions.jsonl")
            runtime = self.runtime(directory, {
                "actor": "bash",
                "action": "check_command_exists",
                "params": {"command": "sh"},
            })
            with mock.patch.object(framework, "ROOT_AUDIT_LOG", audit_log):
                runtime.act(runtime.decide([]))

            with open(audit_log) as handle:
                events = [line for line in handle if line.strip()]

        self.assertEqual(len(events), 2)
        self.assertIn('"event": "started"', events[0])
        self.assertIn('"event": "completed"', events[1])

    @mock.patch("urllib.request.urlopen")
    def test_unconfigured_planner_does_not_call_public_api(self, urlopen):
        with mock.patch.dict(os.environ, {}, clear=True):
            planner = framework.LLMPlanner(
                endpoint="https://api.deepseek.com/v1",
                model="deepseek-chat",
                key="",
            )
        planner.local_model_enabled = False

        decision = planner.decide([], [], [], [])

        urlopen.assert_not_called()
        self.assertEqual(decision["action"], "wait")
        self.assertEqual(decision["reasoning"], "no AI backend configured")

    def test_keyless_loopback_endpoint_is_available(self):
        planner = framework.LLMPlanner(
            endpoint="http://127.0.0.1:11434/v1",
            model="local",
            key="",
        )

        self.assertTrue(planner._cloud_available())


if __name__ == "__main__":
    unittest.main()
