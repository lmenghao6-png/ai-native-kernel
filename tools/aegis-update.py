#!/usr/bin/env python3
"""Signed application update, migration, backup, and rollback for AegisOS."""

import argparse
import configparser
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath


CURRENT_CONFIG_SCHEMA = 2
MANAGED_PATHS = (
    "/usr/local/lib/aegisos",
    "/usr/local/bin/aegisctl",
    "/usr/local/bin/ai-console",
    "/usr/local/bin/aegis-update",
    "/usr/local/sbin/aegis-uninstall",
    "/etc/systemd/system/aegisosd.service",
    "/etc/systemd/system/guardian.service",
    "/usr/lib/tmpfiles.d/aegisos.conf",
    "/etc/aegisos",
)


class UpdateError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def root_path(root: Path, absolute: str) -> Path:
    return root / absolute.lstrip("/")


def require_root(root: Path):
    if root == Path("/") and os.geteuid() != 0:
        raise UpdateError("run this command through sudo")


def fetch(source: str, destination: Path):
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ("http", "https"):
        with urllib.request.urlopen(source, timeout=120) as response:
            destination.write_bytes(response.read())
        return
    if parsed.scheme == "file":
        shutil.copy2(urllib.request.url2pathname(parsed.path), destination)
        return
    shutil.copy2(source, destination)


def resolve_relative(base: str, value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme or os.path.isabs(value):
        return value
    base_parsed = urllib.parse.urlparse(base)
    if base_parsed.scheme in ("http", "https", "file"):
        return urllib.parse.urljoin(base, value)
    return str(Path(base).resolve().parent / value)


def verify_signature(manifest: Path, signature: Path, keyring: Path):
    if not keyring.is_file() or keyring.stat().st_size == 0:
        raise UpdateError(f"release trust key is unavailable: {keyring}")
    result = subprocess.run(
        ["gpgv", "--keyring", str(keyring), str(signature), str(manifest)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise UpdateError(f"release signature verification failed: {result.stderr.strip()}")


def validate_manifest(data: object) -> dict:
    if not isinstance(data, dict):
        raise UpdateError("release manifest must be a JSON object")
    required = {"format", "version", "bundle", "sha256", "config_schema"}
    if set(data) != required:
        raise UpdateError("release manifest fields are invalid")
    if data["format"] != 1:
        raise UpdateError("unsupported release manifest format")
    if not isinstance(data["version"], str) or not data["version"]:
        raise UpdateError("release version is invalid")
    if not isinstance(data["bundle"], str) or not data["bundle"]:
        raise UpdateError("release bundle path is invalid")
    checksum = data["sha256"]
    if not isinstance(checksum, str) or len(checksum) != 64:
        raise UpdateError("release checksum is invalid")
    try:
        int(checksum, 16)
    except ValueError as error:
        raise UpdateError("release checksum is invalid") from error
    if not isinstance(data["config_schema"], int):
        raise UpdateError("configuration schema is invalid")
    if data["config_schema"] > CURRENT_CONFIG_SCHEMA:
        raise UpdateError("this updater cannot migrate the requested configuration schema")
    return data


def safe_members(archive: tarfile.TarFile):
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise UpdateError(f"unsafe bundle path: {member.name}")
        if member.issym() or member.islnk():
            target = PurePosixPath(member.linkname)
            if target.is_absolute() or ".." in target.parts:
                raise UpdateError(f"unsafe bundle link: {member.name}")
        elif not (member.isfile() or member.isdir()):
            raise UpdateError(f"unsupported bundle entry: {member.name}")
        yield member


def create_snapshot(root: Path, state_dir: Path, version: str) -> Path:
    snapshots = state_dir / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    snapshot = snapshots / f"{int(time.time())}-{version}.tar.gz"
    metadata = {
        "created": time.time(),
        "version": version,
        "paths": list(MANAGED_PATHS),
    }
    with tarfile.open(snapshot, "w:gz") as archive:
        for absolute in MANAGED_PATHS:
            path = root_path(root, absolute)
            if path.exists() or path.is_symlink():
                archive.add(path, arcname=absolute.lstrip("/"), recursive=True)
        encoded = json.dumps(metadata, sort_keys=True).encode()
        info = tarfile.TarInfo(".aegisos-snapshot.json")
        info.size = len(encoded)
        info.mtime = int(metadata["created"])
        archive.addfile(info, fileobj=__import__("io").BytesIO(encoded))
    (state_dir / "latest-snapshot").write_text(str(snapshot) + "\n")
    return snapshot


def restore_snapshot(root: Path, snapshot: Path):
    if not snapshot.is_file():
        raise UpdateError(f"snapshot does not exist: {snapshot}")
    for absolute in MANAGED_PATHS:
        path = root_path(root, absolute)
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path)
    with tarfile.open(snapshot, "r:gz") as archive:
        members = [
            member
            for member in safe_members(archive)
            if member.name != ".aegisos-snapshot.json"
        ]
        archive.extractall(root, members=members)


def read_schema(root: Path) -> int:
    path = root_path(root, "/etc/aegisos/config-schema")
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 1


def migrate_configs(root: Path, target_schema: int):
    current = read_schema(root)
    if target_schema < current:
        raise UpdateError("configuration schema downgrade requires rollback")
    while current < target_schema:
        if current == 1:
            config_path = root_path(root, "/etc/aegisos/ai-agent.conf")
            config = configparser.ConfigParser()
            config.read(config_path)
            if not config.has_section("agent"):
                config.add_section("agent")
            config["agent"]["privilege_mode"] = "root"
            with config_path.open("w") as handle:
                config.write(handle)
            os.chmod(config_path, 0o600)
            current = 2
        else:
            raise UpdateError(f"no migration from configuration schema {current}")
    schema_path = root_path(root, "/etc/aegisos/config-schema")
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(f"{target_schema}\n")
    os.chmod(schema_path, 0o644)


def install_bundle(root: Path, bundle: Path):
    with tarfile.open(bundle, "r:*") as archive:
        members = list(safe_members(archive))
        archive.extractall(root, members=members)


def systemctl(root: Path, *args: str):
    if root != Path("/"):
        return
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", *args], check=True)


def apply_update(
    root: Path,
    manifest_source: str,
    signature_source: str | None,
    keyring: Path,
) -> dict:
    require_root(root)
    state_dir = root_path(root, "/var/lib/aegisos/update")
    state_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aegis-update-") as temporary:
        temp = Path(temporary)
        manifest_path = temp / "manifest.json"
        signature_path = temp / "manifest.json.sig"
        bundle_path = temp / "bundle.tar.gz"
        fetch(manifest_source, manifest_path)
        fetch(signature_source or manifest_source + ".sig", signature_path)
        verify_signature(manifest_path, signature_path, keyring)
        try:
            manifest = validate_manifest(json.loads(manifest_path.read_text()))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise UpdateError("release manifest is not valid JSON") from error
        fetch(resolve_relative(manifest_source, manifest["bundle"]), bundle_path)
        if sha256(bundle_path) != manifest["sha256"]:
            raise UpdateError("release bundle checksum mismatch")

        snapshot = create_snapshot(root, state_dir, manifest["version"])
        try:
            install_bundle(root, bundle_path)
            migrate_configs(root, manifest["config_schema"])
            root_path(root, "/etc/aegisos/version").write_text(
                manifest["version"] + "\n"
            )
            systemctl(root, "try-restart", "aegisosd.service", "guardian.service")
        except Exception:
            restore_snapshot(root, snapshot)
            systemctl(root, "try-restart", "aegisosd.service", "guardian.service")
            raise

        status = {
            "version": manifest["version"],
            "installed": time.time(),
            "snapshot": str(snapshot),
            "manifest_sha256": sha256(manifest_path),
        }
        (state_dir / "status.json").write_text(
            json.dumps(status, indent=2, sort_keys=True) + "\n"
        )
        return status


def rollback(root: Path, snapshot: Path | None):
    require_root(root)
    state_dir = root_path(root, "/var/lib/aegisos/update")
    if snapshot is None:
        try:
            snapshot = Path((state_dir / "latest-snapshot").read_text().strip())
        except FileNotFoundError as error:
            raise UpdateError("no rollback snapshot is available") from error
    restore_snapshot(root, snapshot)
    systemctl(root, "try-restart", "aegisosd.service", "guardian.service")


def main() -> int:
    parser = argparse.ArgumentParser(prog="aegis-update")
    parser.add_argument("--root", default="/", help=argparse.SUPPRESS)
    parser.add_argument(
        "--keyring",
        default="/usr/share/keyrings/aegisos-release.gpg",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("manifest")
    apply_parser.add_argument("--signature")
    rollback_parser = subparsers.add_parser("rollback")
    rollback_parser.add_argument("--snapshot")
    subparsers.add_parser("status")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    keyring = Path(args.keyring)

    try:
        if args.command == "apply":
            status = apply_update(root, args.manifest, args.signature, keyring)
            print(json.dumps(status, indent=2, sort_keys=True))
        elif args.command == "rollback":
            rollback(root, Path(args.snapshot) if args.snapshot else None)
            print("Rollback completed.")
        else:
            status_path = root_path(root, "/var/lib/aegisos/update/status.json")
            if status_path.is_file():
                print(status_path.read_text(), end="")
            else:
                print("No AegisOS application update has been applied.")
        return 0
    except (OSError, UpdateError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"aegis-update: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
