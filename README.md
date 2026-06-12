# AegisOS

AegisOS is a Debian-based AI Linux distribution. It uses the standard Debian
Linux kernel and gives its built-in Agent and Guardian unrestricted root
authority over the operating system.

The custom Bastion kernel has been removed. The product is now a Linux
distribution, installer, root AI runtime, and signed release/update toolchain.

## Download

The current build is an unsigned Developer Preview for disposable VMs and test
hardware:

- [AegisOS 0.3 Developer Preview release](https://github.com/lmenghao6-png/ai-native-kernel/releases/tag/preview-0.3-dev)
- [Download the amd64 ISO](https://github.com/lmenghao6-png/ai-native-kernel/releases/download/preview-0.3-dev/aegisos-0.3-dev.iso)
- [Download SHA256SUMS](https://github.com/lmenghao6-png/ai-native-kernel/releases/download/preview-0.3-dev/SHA256SUMS)

Verify the ISO before booting:

```bash
sha256sum --check SHA256SUMS
```

This preview does not bundle a local model or contain a release trust key.
Configure a model backend after installation. Do not use it for sensitive or
irreplaceable data.

## Product Documentation

- [Product requirements](PRD.md)
- [Development roadmap](ROADMAP.md)
- [Security model](SECURITY.md)
- [Release procedure](RELEASE.md)
- [Changelog](CHANGELOG.md)

## Root AI Model

The Agent can execute every registered actor capability, including arbitrary
shell commands, file writes, package installation, and systemd control. The
Guardian can issue unrestricted `ROOT_AUTO` shell commands.

This is intentionally not a least-privilege design. Prompt injection through
logs, files, network responses, or model output can become root code execution.
Use disposable machines until the model, prompts, and operational controls have
been independently reviewed.

Every root action is written before and after execution to:

```text
/var/log/aegisos/root-actions.jsonl
```

`auditd` also watches the AI code, configuration, units, and root action log.
A root process can still alter local evidence, so production deployments should
forward the journal and audit stream to an external append-only collector.

Emergency stop:

```bash
aegisctl ai-stop
aegisctl status

# Re-enable after inspection
aegisctl ai-start
```

The stop command creates `/etc/aegisos/agent-disabled`; both AI units have a
systemd condition that prevents restart while this marker exists.

## Components

- Debian bookworm and the Debian Linux kernel
- Root Agent with five sensors and Bash, systemd, and APT actors
- Root Guardian for periodic monitoring and direct remediation
- OpenAI-compatible cloud or loopback model endpoints
- Optional local GGUF inference through `llama-cli`
- SQLite observation, action, goal, and context memory
- Guided GPT disk installer with UEFI and legacy BIOS boot
- SSH key-only remote authentication and active UFW default-deny policy
- GPG-verified application updates with configuration migration and rollback
- ISO checksums, release manifests, QEMU boot tests, and QEMU install tests

## Install

Boot the ISO in UEFI mode and select `Install AegisOS to Disk`. The installer:

1. Erases and partitions the selected disk.
2. Creates a unique sudo administrator and locks direct root login.
3. Accepts an optional SSH public key.
4. Removes the published Live account.
5. Generates unique SSH host keys.
6. Enables the root AI, SSH, UFW, and audit services.

The Live credentials are `aegis-live` / `aegisos`. SSH password authentication
is disabled in both Live and installed systems.

## Operations

```bash
aegisctl status
aegisctl doctor
aegisctl logs
aegisctl root-audit 100
ai-console "Summarize likely causes of the failed services"
```

`ai-console` sends prompts to the configured model backend. It does not execute
Agent capabilities; autonomous system execution is performed by the Agent and
Guardian services.

Configure the model in `/etc/aegisos/ai-agent.conf`:

```ini
[api]
endpoint = http://127.0.0.1:11434/v1
model = local-model
key =
local_model_enabled = false

[agent]
tick_interval = 10
privilege_mode = root
```

Guardian configuration is stored in `/etc/aegisos/guardian.conf`:

```ini
[guardian]
enabled = true
interval = 60
auto_execute_root = true
goals = Keep the system secure and stable.
```

## Signed Updates

Installed systems trust `/usr/share/keyrings/aegisos-release.gpg`. A release
image must be built with the public key supplied through
`AEGISOS_RELEASE_PUBLIC_KEY` or `AEGISOS_RELEASE_PUBLIC_KEY_B64`.

Apply and roll back an application update:

```bash
aegisctl update https://example.invalid/aegisos/manifest.json
aegisctl rollback
```

The updater verifies the detached GPG signature and bundle SHA-256 before
creating a snapshot. Failed installation or migration restores that snapshot
automatically.

Remove the AI layer while retaining a backup:

```bash
sudo aegis-uninstall
sudo aegis-uninstall --purge
```

## Build

Prerequisites on Ubuntu 24.04 or Debian:

```bash
sudo apt-get install -y debian-archive-keyring mmdebstrap squashfs-tools \
  grub-pc-bin grub-efi-amd64-bin xorriso mtools parted dosfstools rsync \
  expect qemu-system-x86 qemu-utils ovmf
```

Build and test:

```bash
make test
make image
make test-iso
make test-install
```

Artifacts:

```text
build/aegisos/image/aegisos-<version>.iso
build/aegisos/image/SHA256SUMS
build/aegisos/image/release-manifest.json
```

`SOURCE_DATE_EPOCH` controls squashfs timestamps and release metadata. See
[RELEASE.md](RELEASE.md) for signing-key and tag procedures.

## Status

The current image is a developer preview. Boot, installation, root AI identity,
SSH credentials, firewall, audit service, signed update, migration, and rollback
are automated. The unrestricted root AI model is inherently unsuitable for
systems where model input is not fully trusted.

## License

MIT License. See [LICENSE](LICENSE).
