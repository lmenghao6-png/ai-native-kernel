import os
import subprocess
import sys
import tempfile
import unittest


class InstallAgentsTests(unittest.TestCase):
    def install_tools(self, rootfs):
        subprocess.run(
            [sys.executable, "tools/install-agents.py", rootfs],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_services_run_unprivileged_with_hardening(self):
        with tempfile.TemporaryDirectory() as rootfs:
            self.install_tools(rootfs)
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
            self.install_tools(rootfs)
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
            self.install_tools(rootfs)
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

    def test_installer_validates_administrator_names(self):
        accepted = subprocess.run(
            [
                "bash",
                "tools/aegisos-install.sh",
                "--validate-admin-username",
                "aegisadmin",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(accepted.returncode, 0)

        for username in ("root", "aegis", "aegis-live", "UpperCase", "bad.name"):
            with self.subTest(username=username):
                rejected = subprocess.run(
                    [
                        "bash",
                        "tools/aegisos-install.sh",
                        "--validate-admin-username",
                        username,
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(rejected.returncode, 0)

    def test_generated_tools_use_repository_version(self):
        with tempfile.TemporaryDirectory() as rootfs:
            self.install_tools(rootfs)
            with open("VERSION") as handle:
                version = handle.read().strip()
            for path in (
                "usr/local/bin/aegisctl",
                "usr/local/bin/ai-console",
            ):
                with open(os.path.join(rootfs, path)) as handle:
                    content = handle.read()
                self.assertIn(version, content)
                self.assertNotIn("0.3-beta", content)

    def test_installer_removes_live_credentials(self):
        with open("tools/aegisos-install.sh") as handle:
            installer = handle.read()
        self.assertIn("userdel --remove aegis-live", installer)
        self.assertIn("sed -i '/^[[:space:]]*Live login:/d'", installer)
        self.assertIn("passwd --lock root", installer)
        self.assertIn("Administrator password must be at least 12", installer)

    def test_rootfs_branding_uses_repository_version(self):
        with open("tools/build-aegisos-rootfs.sh") as handle:
            builder = handle.read()
        self.assertIn("@AEGISOS_VERSION@", builder)
        self.assertIn('"$ROOTFS/etc/issue"', builder)
        self.assertIn('"$ROOTFS/etc/issue.net"', builder)
        self.assertNotIn(
            "AI-Native Operating System $AEGISOS_VERSION",
            builder,
        )

    def test_image_builder_accepts_release_version_formats(self):
        for version in ("1.0", "1.0.0", "1.0-rc.1"):
            with self.subTest(version=version):
                with tempfile.TemporaryDirectory() as directory:
                    version_file = os.path.join(directory, "VERSION")
                    with open(version_file, "w") as handle:
                        handle.write(version)
                    result = subprocess.run(
                        ["bash", "tools/build-aegisos-image.sh"],
                        env={
                            **os.environ,
                            "VERSION_FILE": version_file,
                            "ROOTFS": os.path.join(directory, "missing-rootfs"),
                        },
                        capture_output=True,
                        text=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Rootfs not found:", result.stderr)
                    self.assertNotIn("Invalid AegisOS version:", result.stderr)


if __name__ == "__main__":
    unittest.main()
