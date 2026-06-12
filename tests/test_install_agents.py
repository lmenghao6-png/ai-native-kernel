import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest


class InstallAgentsTests(unittest.TestCase):
    def install_tools(self, rootfs):
        subprocess.run(
            [sys.executable, "tools/install-agents.py", rootfs],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_services_run_as_root_with_emergency_stop(self):
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
                self.assertNotIn("User=", content)
                self.assertNotIn("CapabilityBoundingSet=", content)
                self.assertIn("Restart=on-failure\n", content)
                self.assertIn(
                    "ConditionPathExists=!/etc/aegisos/agent-disabled\n",
                    content,
                )
                self.assertIn("UMask=0077\n", content)

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
                "d /run/aegisos 0700 root root -\n"
                "d /var/lib/aegisos 0700 root root -\n"
                "d /var/log/aegisos 0700 root root -\n"
                "f /var/log/aegisos/root-actions.jsonl 0600 root root -\n",
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

    def test_installer_validates_ssh_public_keys(self):
        valid = (
            "ssh-ed25519 "
            "AAAAC3NzaC1lZDI1NTE5AAAAIHycMH0+K6FQoCemw1/ocvIV4ppfapJ1H61UrIykyiBP "
            "test"
        )
        accepted = subprocess.run(
            ["bash", "tools/aegisos-install.sh", "--validate-ssh-key", valid],
            capture_output=True,
            text=True,
        )
        self.assertEqual(accepted.returncode, 0)
        for key in ("", "command=id ssh-ed25519 AAAA", "ssh-ed25519 bad key\nnext"):
            with self.subTest(key=key):
                rejected = subprocess.run(
                    ["bash", "tools/aegisos-install.sh", "--validate-ssh-key", key],
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
            self.assertTrue(
                os.access(os.path.join(rootfs, "usr/local/bin/aegis-update"), os.X_OK)
            )
            self.assertTrue(
                os.access(
                    os.path.join(rootfs, "usr/local/sbin/aegis-uninstall"),
                    os.X_OK,
                )
            )

    def test_ai_console_uses_configured_keyless_local_endpoint(self):
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers["Content-Length"])
                body = json.loads(self.rfile.read(length))
                requests.append((self.path, body, self.headers.get("Authorization")))
                response = json.dumps({
                    "choices": [{"message": {"content": "configured backend"}}]
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, _format, *_args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as rootfs:
                self.install_tools(rootfs)
                config = os.path.join(rootfs, "ai-agent.conf")
                with open(config, "w") as handle:
                    handle.write(
                        "[api]\n"
                        f"endpoint = http://127.0.0.1:{server.server_port}/v1\n"
                        "model = configured-model\n"
                        "key =\n"
                        "local_model_enabled = false\n"
                    )
                result = subprocess.run(
                    [
                        os.path.join(rootfs, "usr/local/bin/ai-console"),
                        "system status",
                    ],
                    env={**os.environ, "AEGISOS_AI_CONFIG": config},
                    check=True,
                    capture_output=True,
                    text=True,
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.assertEqual(result.stdout.strip(), "configured backend")
        self.assertEqual(requests[0][0], "/v1/chat/completions")
        self.assertEqual(requests[0][1]["model"], "configured-model")
        self.assertIsNone(requests[0][2])

    def test_installer_removes_live_credentials(self):
        with open("tools/aegisos-install.sh") as handle:
            installer = handle.read()
        self.assertIn("userdel --remove aegis-live", installer)
        self.assertIn("sed -i '/^[[:space:]]*Live login:/d'", installer)
        self.assertIn("passwd --lock root", installer)
        self.assertIn("Administrator password must be at least 12", installer)
        self.assertIn("authorized_keys", installer)
        self.assertIn("firstboot-complete", installer)

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

    def test_rootfs_writes_guardian_config_and_enables_firewall(self):
        with open("tools/build-aegisos-rootfs.sh") as handle:
            builder = handle.read()

        self.assertIn(
            '"$ROOTFS/etc/aegisos/guardian.conf"',
            builder,
        )
        self.assertIn(
            'chroot "$ROOTFS" ufw default deny incoming',
            builder,
        )
        self.assertIn(
            'chroot "$ROOTFS" ufw allow 22/tcp',
            builder,
        )
        self.assertIn(
            "sed -i 's/^ENABLED=.*/ENABLED=yes/'",
            builder,
        )
        self.assertIn("auditd,apparmor,apparmor-utils,gpgv", builder)
        self.assertIn('"$ROOTFS/etc/audit/rules.d/aegisos.rules"', builder)

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

    def test_image_builder_makes_build_outputs_writable(self):
        with open("tools/build-aegisos-image.sh") as handle:
            builder = handle.read()
        self.assertIn(
            '${SUDO[@]} chown "$(id -u):$(id -g)" "$BUILD_DIR"',
            builder,
        )
        self.assertIn(
            '${SUDO[@]} chown -R "$(id -u):$(id -g)" '
            '"$ISO_DIR" "$IMAGE_DIR"',
            builder,
        )

    def test_image_builder_emits_reproducible_release_metadata(self):
        with open("tools/build-aegisos-image.sh") as handle:
            builder = handle.read()
        self.assertIn("SOURCE_DATE_EPOCH", builder)
        self.assertIn('-mkfs-time "$SOURCE_DATE_EPOCH"', builder)
        self.assertIn('-all-time "$SOURCE_DATE_EPOCH"', builder)
        self.assertIn("release-manifest.json", builder)
        self.assertIn("sha256sum", builder)

    def test_release_workflow_requires_external_signing_keys(self):
        with open(".github/workflows/build.yml") as handle:
            workflow = handle.read()
        self.assertIn("AEGISOS_RELEASE_PUBLIC_KEY_B64", workflow)
        self.assertIn("AEGISOS_RELEASE_PRIVATE_KEY", workflow)
        self.assertIn("build-release-bundle.sh", workflow)
        self.assertIn("SHA256SUMS.sig", workflow)


if __name__ == "__main__":
    unittest.main()
