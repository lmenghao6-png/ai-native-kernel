import os
import subprocess
import sys
import tempfile
import unittest


class InstallAgentsTests(unittest.TestCase):
    def test_services_run_unprivileged_with_hardening(self):
        with tempfile.TemporaryDirectory() as rootfs:
            subprocess.run(
                [sys.executable, "tools/install-agents.py", rootfs],
                check=True,
                capture_output=True,
                text=True,
            )
            for service in ("aegisosd.service", "guardian.service"):
                path = os.path.join(
                    rootfs,
                    "etc/systemd/system",
                    service,
                )
                with open(path) as handle:
                    content = handle.read()
                self.assertIn("User=aegis\n", content)
                self.assertIn("NoNewPrivileges=true\n", content)
                self.assertIn("ProtectSystem=strict\n", content)
                self.assertIn("CapabilityBoundingSet=\n", content)
                self.assertIn(
                    "ReadWritePaths=/var/lib/aegisos "
                    "/var/log/aegisos /run/aegisos\n",
                    content,
                )

    def test_tmpfiles_creates_private_runtime_directories(self):
        with tempfile.TemporaryDirectory() as rootfs:
            subprocess.run(
                [sys.executable, "tools/install-agents.py", rootfs],
                check=True,
                capture_output=True,
                text=True,
            )
            path = os.path.join(
                rootfs,
                "usr/lib/tmpfiles.d/aegisos.conf",
            )
            with open(path) as handle:
                content = handle.read()
            self.assertEqual(
                content,
                "d /run/aegisos 0750 aegis aegis -\n"
                "d /var/lib/aegisos 0750 aegis aegis -\n"
                "d /var/log/aegisos 0750 aegis aegis -\n",
            )

    def test_installer_is_installed_with_console_service(self):
        with tempfile.TemporaryDirectory() as rootfs:
            subprocess.run(
                [sys.executable, "tools/install-agents.py", rootfs],
                check=True,
                capture_output=True,
                text=True,
            )
            installer = os.path.join(rootfs, "usr/local/bin/aegisos-install")
            service = os.path.join(
                rootfs,
                "etc/systemd/system/aegisos-installer.service",
            )
            with open("tools/aegisos-install.sh") as handle:
                expected_installer = handle.read()
            with open(installer) as handle:
                installed_installer = handle.read()
            with open(service) as handle:
                service_content = handle.read()

            self.assertEqual(installed_installer, expected_installer)
            self.assertEqual(os.stat(installer).st_mode & 0o777, 0o755)
            self.assertIn("TTYPath=/dev/console\n", service_content)
            self.assertIn("StandardInput=tty-force\n", service_content)

    def test_installer_partition_paths(self):
        cases = (
            ("/dev/vda", "3", "/dev/vda3"),
            ("/dev/sda", "1", "/dev/sda1"),
            ("/dev/nvme0n1", "3", "/dev/nvme0n1p3"),
            ("/dev/mmcblk0", "2", "/dev/mmcblk0p2"),
        )
        for disk, number, expected in cases:
            with self.subTest(disk=disk):
                result = subprocess.run(
                    [
                        "bash",
                        "tools/aegisos-install.sh",
                        "--partition-path",
                        disk,
                        number,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()
