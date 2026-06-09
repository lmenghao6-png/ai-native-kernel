# Changelog

## Unreleased

### Added
- Single-source `VERSION` metadata for images, CLI tools, MOTD, and OS identity
- Installer-time administrator account and password setup
- Physical page release/reuse with PMM and VMM boot-time self-tests
- Transactional VMM page mapping with data-page and page-table rollback
- QEMU integration test that executes a Ring 3 ELF program and verifies exit
- Python tests for Guardian command policy, Agent action policy, and service hardening
- Unprivileged `aegis` service account with systemd sandboxing
- Automated ISO installation and reboot test using a disposable QEMU disk

### Changed
- Live images use a removable `aegis-live` account; installed systems remove it
- ISO build output directories are created safely across root/non-root stages
- Bastion now consumes real Limine memory map and HHDM responses
- Initramfs now parses CPIO `newc` archives and constructs the VFS tree
- ELF loader now validates and maps x86-64 `PT_LOAD` segments
- Agent and Guardian unattended execution is restricted to read-only diagnostics
- Disk installer now writes UUID-based mounts, supports UEFI fallback and
  BIOS/GPT boot, creates unique SSH host keys, and cleans up failed installs

### Fixed
- Distribution CI can build the ISO after the privileged rootfs stage
- Installed systems no longer inherit a published root password
- Failed user-page allocations no longer leak pages or advance the virtual address cursor
- PMM free-page bitmap initialization and VMM CR3 allocation
- Limine request IDs and request markers
- GDT/TSS setup, IDT syscall vector mapping, and interrupt-frame register layout
- User-mode hello program pointer and length handling

## v0.3-beta (2026-06-05)

### Added
- **Agent Framework**: Plugin-based autonomous AI runtime with 8 plugins
  - 5 Sensors: disk, process, memory, logs, network
  - 3 Actors: bash (command execution), systemd (service management), apt (package management)
  - LLM Planner: any OpenAI-compatible model, auto-detected from ai-agent.conf
  - Agent Memory: SQLite-based persistent context storage
  - Goal system: user-defined long-term objectives
- **Guardian**: Proactive AI daemon with 4-level autonomous action (IGNORE/SUGGEST/SAFE_AUTO/NEEDS_CONFIRM)
- **Bastion v0.3**: Virtual filesystem, initramfs CPIO loader, ELF64 program loader
  - VFS: lookup, open, read, close, dump operations
  - Initramfs: CPIO newc format parser, automatic directory tree construction
  - ELF Loader: 64-bit ELF parsing, PT_LOAD mapping, BSS zeroing
- System hardening: UFW firewall with default-deny, SSH key-only authentication
- Development tools pre-installed: git, gcc, make, vim, htop, wget

### Changed
- Removed first-run API key configuration wizard (zero-friction boot)
- Agent loop: LLM sees execution results, decides next steps, loops until [DONE]
- Version bumped to 0.3-beta

### Fixed
- MOTD rendering (was shell script printed as raw text)
- Login banner (now clean static text)
- ai-console: no longer blocks startup when API key is unconfigured

## v0.2-alpha (2026-06-04)

### Added
- AegisOS Linux distribution based on Debian bookworm
- AI Console with natural language interface
- Local Qwen2.5-0.5B model for offline AI
- Guided disk installation program (GPT partitioning)
- aegisosd supervisor daemon with Unix socket RPC
- aegisctl CLI: status, monitor, doctor, logs, update, services
- ai-config: multi-provider API configuration (DeepSeek/OpenAI/Ollama/Claude)
- Bastion kernel: x86_64 + UEFI + Limine boot
- GDT, IDT, exception handling, PMM, VMM, kernel heap, TSS
- Ring3 task scheduler with cooperative + preemptive multitasking

## v0.1-alpha (2026-05-29)

- Initial commit
- Bastion kernel skeleton with serial debug shell
- Basic memory management
- Task subsystem with syscall ABI
