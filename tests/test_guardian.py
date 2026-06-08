import unittest
from unittest import mock

import guardian


class GuardianCommandPolicyTests(unittest.TestCase):
    def test_allows_read_only_command(self):
        self.assertEqual(
            guardian.safe_command_argv("systemctl status ssh"),
            ["systemctl", "status", "ssh"],
        )
        self.assertEqual(guardian.safe_command_argv("df -h /"), ["df", "-h", "/"])

    def test_rejects_shell_chaining_and_substitution(self):
        rejected = [
            "echo ok; touch /tmp/unsafe",
            "systemctl status ssh && rm -rf /tmp/example",
            "cat $(which passwd)",
            "cat /etc/passwd > /tmp/passwd",
            "/bin/cat /etc/passwd",
        ]
        for command in rejected:
            with self.subTest(command=command):
                self.assertIsNone(guardian.safe_command_argv(command))

    def test_rejects_mutating_systemctl_actions(self):
        for action in ("restart", "start", "stop", "enable", "disable"):
            with self.subTest(action=action):
                self.assertFalse(guardian.is_safe_command(f"systemctl {action} ssh"))

    @mock.patch.object(guardian, "log")
    @mock.patch.object(guardian.subprocess, "run")
    def test_unsafe_command_is_never_executed(self, run, _log):
        results = guardian.execute_commands(
            ["systemctl status ssh; rm -rf /tmp/example"],
            auto_execute_safe=True,
        )

        run.assert_not_called()
        self.assertEqual(results[0]["reason"], "unsafe")

    @mock.patch.object(guardian, "log")
    def test_safe_execution_can_be_disabled(self, _log):
        with mock.patch.object(guardian.subprocess, "run") as run:
            results = guardian.execute_commands(["df -h /"], False)
        run.assert_not_called()
        self.assertEqual(results[0]["reason"], "auto_disabled")


if __name__ == "__main__":
    unittest.main()
