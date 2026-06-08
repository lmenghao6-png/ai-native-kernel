import os
import tempfile
import unittest

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

    def test_denies_arbitrary_autonomous_shell(self):
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

        self.assertTrue(result["denied"])
        self.assertFalse(marker_exists)
        self.assertTrue(history[0]["result"]["denied"])

    def test_denies_mutating_service_action(self):
        self.assertFalse(
            framework.autonomous_action_allowed("systemd", "restart_service")
        )
        self.assertFalse(
            framework.autonomous_action_allowed("apt", "install_package")
        )


if __name__ == "__main__":
    unittest.main()
