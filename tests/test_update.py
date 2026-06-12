import hashlib
import importlib.util
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
import shutil


def load_updater():
    spec = importlib.util.spec_from_file_location(
        "aegis_update", "tools/aegis-update.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_updater()

    def test_rejects_unsafe_tar_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "bad.tar"
            payload = Path(directory) / "payload"
            payload.write_text("bad")
            with tarfile.open(archive_path, "w") as archive:
                archive.add(payload, arcname="../../etc/shadow")

            with tarfile.open(archive_path) as archive:
                with self.assertRaises(self.update.UpdateError):
                    list(self.update.safe_members(archive))

    def test_configuration_migration_enables_root_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "etc/aegisos/ai-agent.conf"
            config.parent.mkdir(parents=True)
            config.write_text("[agent]\ntick_interval = 10\n")

            self.update.migrate_configs(root, 2)

            content = config.read_text()
            self.assertIn("privilege_mode = root", content)
            self.assertEqual(
                (root / "etc/aegisos/config-schema").read_text(), "2\n"
            )

    def test_snapshot_restores_managed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            state = root / "var/lib/aegisos/update"
            library = root / "usr/local/lib/aegisos"
            library.mkdir(parents=True)
            (library / "framework.py").write_text("before")
            snapshot = self.update.create_snapshot(root, state, "test")
            (library / "framework.py").write_text("after")

            self.update.restore_snapshot(root, snapshot)

            self.assertEqual((library / "framework.py").read_text(), "before")

    def test_manifest_requires_exact_signed_fields(self):
        valid = {
            "format": 1,
            "version": "1.0",
            "bundle": "bundle.tar.gz",
            "sha256": "0" * 64,
            "config_schema": 2,
        }
        self.assertEqual(self.update.validate_manifest(valid), valid)
        with self.assertRaises(self.update.UpdateError):
            self.update.validate_manifest({**valid, "command": "id"})

    @unittest.skipUnless(shutil.which("gpg") and shutil.which("gpgv"), "GPG unavailable")
    def test_signed_apply_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            root = workspace / "root"
            library = root / "usr/local/lib/aegisos"
            config_dir = root / "etc/aegisos"
            library.mkdir(parents=True)
            config_dir.mkdir(parents=True)
            (library / "framework.py").write_text("before")
            (config_dir / "version").write_text("0.1\n")
            (config_dir / "config-schema").write_text("2\n")

            payload = workspace / "payload/usr/local/lib/aegisos"
            payload.mkdir(parents=True)
            (payload / "framework.py").write_text("after")
            bundle = workspace / "bundle.tar.gz"
            with tarfile.open(bundle, "w:gz") as archive:
                archive.add(
                    workspace / "payload/usr",
                    arcname="usr",
                )

            manifest = workspace / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "format": 1,
                        "version": "0.2",
                        "bundle": bundle.name,
                        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
                        "config_schema": 2,
                    },
                    sort_keys=True,
                )
            )

            gnupg = workspace / "gnupg"
            gnupg.mkdir(mode=0o700)
            subprocess.run(
                [
                    "gpg",
                    "--homedir",
                    str(gnupg),
                    "--batch",
                    "--passphrase",
                    "",
                    "--quick-gen-key",
                    "AegisOS Update Test <update-test@invalid>",
                    "ed25519",
                    "sign",
                    "0",
                ],
                check=True,
                capture_output=True,
            )
            fingerprint = subprocess.run(
                [
                    "gpg",
                    "--homedir",
                    str(gnupg),
                    "--batch",
                    "--with-colons",
                    "--list-secret-keys",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            fingerprint = next(
                line.split(":")[9]
                for line in fingerprint.stdout.splitlines()
                if line.startswith("fpr:")
            )
            keyring = workspace / "release.gpg"
            with keyring.open("wb") as handle:
                subprocess.run(
                    [
                        "gpg",
                        "--homedir",
                        str(gnupg),
                        "--batch",
                        "--export",
                        fingerprint,
                    ],
                    check=True,
                    stdout=handle,
                )
            signature = workspace / "manifest.json.sig"
            subprocess.run(
                [
                    "gpg",
                    "--homedir",
                    str(gnupg),
                    "--batch",
                    "--local-user",
                    fingerprint,
                    "--output",
                    str(signature),
                    "--detach-sign",
                    str(manifest),
                ],
                check=True,
                capture_output=True,
            )

            status = self.update.apply_update(
                root, str(manifest), str(signature), keyring
            )
            self.assertEqual(status["version"], "0.2")
            self.assertEqual((library / "framework.py").read_text(), "after")
            self.assertEqual((config_dir / "version").read_text(), "0.2\n")

            self.update.rollback(root, None)
            self.assertEqual((library / "framework.py").read_text(), "before")
            self.assertEqual((config_dir / "version").read_text(), "0.1\n")


if __name__ == "__main__":
    unittest.main()
