# AegisOS Roadmap

The product is a Debian Linux distribution. Custom-kernel development is no
longer part of the repository or release process.

Product scope, users, requirements, and release boundaries are defined in
[PRD.md](PRD.md).

## Completed Release Engineering

- Debian Live ISO with standard Debian Linux kernel
- Guided GPT installer with UEFI and legacy BIOS support
- Unique administrator credentials and optional SSH public key enrollment
- Root login locked and SSH password authentication disabled
- Root Agent and Guardian with unrestricted system execution
- Pre/post root action JSONL records and auditd watches
- Local emergency stop marker and `aegisctl ai-stop`
- Active UFW default-deny incoming policy with SSH exception
- GPG-verified application update bundle and strict signed manifest
- Configuration schema migration, pre-update snapshot, automatic recovery,
  explicit rollback, and uninstall backup
- Deterministic squashfs timestamps, ISO SHA-256, and release manifest
- Python tests, QEMU Live boot test, and QEMU install/reboot test
- Tag-based GitHub release workflow using externally managed signing keys

## Before Stable

- Forward audit and journal records to an external append-only service
- Recovery image and documented offline disable procedure
- TPM-backed release-key and configuration integrity measurements
- Automated legacy BIOS installation test on physical-equivalent firmware
- Hardware compatibility matrix
- Model/prompt red-team review focused on root-level prompt injection
- Reproducibility comparison across two clean build workers

## Release Criteria

- Version tag exactly matches `VERSION`
- All Python, ISO boot, installation, reboot, update, and rollback tests pass
- Tagged builds contain an injected release trust key
- ISO checksums, release manifest, and application update manifest are signed
- A clean installed VM can engage the emergency stop without either AI unit
  restarting
- Known security limitations are published in `SECURITY.md`
