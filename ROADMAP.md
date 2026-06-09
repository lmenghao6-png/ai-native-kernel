# AegisOS Development Roadmap

The repository is currently `0.3-dev`. A version label is not considered a
release until its required tests pass from a clean checkout.

## Completed Baseline

- Debian Live ISO builds and reaches a serial login prompt
- Agent and Guardian services run as the unprivileged `aegis` user
- Unattended AI actions are restricted to read-only diagnostics
- Bastion consumes the Limine memory map and creates its own page tables
- Physical pages can be released and reused; failed VMM mappings roll back
- CPIO initramfs parsing, VFS construction, and ELF64 segment loading
- Ring 3 process entry, serial write syscall, and process exit syscall
- Python policy tests and QEMU kernel boot integration test

## 0.3 Alpha

- Per-process address spaces and page permission enforcement
- Kernel file descriptors with open/read/write syscalls
- Cooperative scheduler with two isolated user tasks
- Structured Agent approval queue for mutating operations
- Reproducible ISO build
- Automated UEFI installer disk test

## 0.4 Beta

- Timer-driven preemptive scheduling and blocking/wakeup
- User process fault isolation and lifecycle cleanup
- Signed update metadata and rollback
- Network configuration and first-boot credential workflow
- Automated legacy BIOS installation test
- Threat model and external security review checklist

## Release Criteria

- Clean builds produce no compiler warnings
- All Python and QEMU tests pass in CI
- No daemon runs as root without a documented requirement
- Mutating AI actions require an authenticated approval path
- Installation, reboot, upgrade, and rollback are tested in disposable VMs
