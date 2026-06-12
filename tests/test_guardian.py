import os
import tempfile
import unittest
from unittest import mock

import guardian


class GuardianCommandPolicyTests(unittest.TestCase):
    def test_config_parses_enabled_boolean_and_bounds_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            agent_config = os.path.join(directory, "ai-agent.conf")
            guardian_config = os.path.join(directory, "guardian.conf")
            with open(agent_config, "w") as handle:
                handle.write(
                    "[api]\n"
                    "endpoint = http://127.0.0.1:11434/v1\n"
                    "model = local-model\n"
                    "key =\n"
                    "local_model_enabled = false\n"
                )
            with open(guardian_config, "w") as handle:
                handle.write(
                    "[guardian]\n"
                    "enabled = false\n"
                    "interval = 1\n"
                    "auto_execute_root = false\n"
                )

            with mock.patch.object(guardian, "AGENT_CONFIG", agent_config), \
                 mock.patch.object(guardian, "CONFIG_PATH", guardian_config):
                config = guardian.load_config()

        self.assertIs(config["enabled"], False)
        self.assertIs(config["auto_execute_root"], False)
        self.assertEqual(config["interval"], 10)
        self.assertEqual(config["api"]["model"], "local-model")
        self.assertIs(config["api"]["local_model_enabled"], False)

    @mock.patch.object(guardian, "call_local_llm", return_value="local")
    @mock.patch.object(guardian, "call_cloud_llm", return_value=None)
    def test_cloud_failure_falls_back_to_local(self, cloud, local):
        config = {
            "api": {
                "endpoint": "http://localhost:11434/v1",
                "model": "local-model",
                "key": "",
                "local_model_enabled": True,
            }
        }

        self.assertEqual(guardian.call_llm(config, []), "local")
        cloud.assert_called_once_with(config, [])
        local.assert_called_once_with([])

    @mock.patch.object(guardian, "call_local_llm")
    def test_disabled_local_model_is_not_called(self, local):
        config = {
            "api": {
                "endpoint": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "key": "",
                "local_model_enabled": False,
            }
        }

        self.assertIsNone(guardian.call_llm(config, []))
        local.assert_not_called()

    @mock.patch.object(guardian, "log")
    @mock.patch.object(guardian.subprocess, "run")
    @mock.patch.object(guardian, "audit_root_command")
    def test_root_command_executes_without_filter(self, audit, run, _log):
        run.return_value = mock.Mock(returncode=0, stdout="done", stderr="")
        results = guardian.execute_commands(
            ["systemctl restart ssh && touch /root/guardian-ran"],
            auto_execute_root=True,
        )

        run.assert_called_once_with(
            [
                "/bin/bash",
                "-lc",
                "systemctl restart ssh && touch /root/guardian-ran",
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertTrue(results[0]["executed"])
        self.assertEqual(audit.call_count, 2)

    @mock.patch.object(guardian, "log")
    def test_root_execution_can_be_disabled(self, _log):
        with mock.patch.object(guardian.subprocess, "run") as run:
            results = guardian.execute_commands(["df -h /"], False)
        run.assert_not_called()
        self.assertEqual(results[0]["reason"], "auto_disabled")


if __name__ == "__main__":
    unittest.main()
