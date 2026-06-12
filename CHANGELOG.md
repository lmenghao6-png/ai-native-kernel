# Changelog

## Unreleased

### Added
- Bundled Qwen2.5-0.5B-Instruct Q4_K_M model and pinned llama.cpp runtime
- Loopback-only local model service with offline health and inference tests
- Root Agent and Guardian execution model with all actor and shell capabilities
- Pre/post root action JSONL records and auditd watches
- Emergency stop and restart commands through `aegisctl`
- Optional installer-time administrator SSH public key enrollment
- GPG-verified application updates with strict manifests and SHA-256 binding
- Configuration schema migration, snapshots, automatic recovery, rollback,
  uninstall backup, and purge mode
- ISO release manifest, checksums, deterministic squashfs timestamps, and
  external signing-key integration
- Automated Live ISO and full installation/reboot tests using QEMU
- End-to-end signed update and rollback test with an ephemeral GPG key
- Security model and release operator documentation

### Changed
- Default model configuration now uses the bundled offline endpoint
- Emergency stop now stops the model service together with Agent and Guardian
- The project now ships only a Debian-based Linux distribution; the Bastion
  custom kernel, user sample, build targets, CI job, and boot test were removed
- Agent and Guardian systemd services now run as root by product design
- Guardian `ROOT_AUTO` commands run directly through a root shell
- Live images use a removable `aegis-live` account; installed systems remove it
- AI Console and daemons share configured endpoint/model settings and support
  keyless loopback OpenAI-compatible APIs
- UFW is enabled by default with incoming traffic denied except for SSH
- Disk installer now writes UUID-based mounts, supports UEFI fallback and
  BIOS/GPT boot, creates unique SSH host keys, and cleans up failed installs

### Fixed
- Distribution CI can build the ISO after the privileged rootfs stage
- Installed systems no longer inherit a published root password
- Guardian boolean configuration, disabled-service restart behavior, and local
  model fallback after a loopback API failure
- Unconfigured agents no longer repeatedly call the public default API

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
