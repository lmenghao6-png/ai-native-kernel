# Changelog

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
