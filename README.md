# AegisOS

**AI-Native Operating System** — a Debian-based Linux distribution with a built-in autonomous AI agent framework.

AegisOS combines a standard Debian bookworm base with a self-hosted AI runtime that can observe system state, make decisions, and take autonomous actions to keep your system secure and stable.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                  AegisOS                     │
├─────────────────────────────────────────────┤
│  AI Console (natural language interface)     │
│  aegisctl (management CLI)                   │
├─────────────────────────────────────────────┤
│  Agent Framework (framework.py)              │
│  ├── Planner (LLM decision engine)           │
│  ├── Memory (SQLite persistent context)      │
│  └── Plugin Registry                         │
├──────────────────┬──────────────────────────┤
│  5 Sensors        │  3 Actors                │
│  ├── disk         │  ├── bash                │
│  ├── process      │  ├── systemd             │
│  ├── memory       │  └── apt                 │
│  ├── logs         │                          │
│  └── network      │                          │
├──────────────────┴──────────────────────────┤
│  Guardian Daemon (proactive AI monitor)      │
├─────────────────────────────────────────────┤
│  Bastion Kernel (custom x86_64, research)    │
│  ├── VFS + CPIO initramfs + ELF64 loader     │
│  ├── PMM/VMM + kheap + TSS                   │
│  ├── Ring 3 process bootstrap                │
│  └── Minimal syscall ABI                     │
├─────────────────────────────────────────────┤
│  Debian bookworm base + Linux kernel         │
└─────────────────────────────────────────────┘
```

## Features

### AI Agent Framework
- **8 self-registering plugins**: 5 sensors (disk, process, memory, logs, network) + 3 actors (bash, systemd, apt)
- **LLM Planner**: supports any OpenAI-compatible API (DeepSeek, OpenAI, Ollama, Claude) — configured in `/etc/aegisos/ai-agent.conf`
- **Local fallback**: supports offline GGUF inference when `llama-cli` and a compatible model are installed
- **Agent Memory**: SQLite-backed persistent context storage with observation/action/goal tracking
- **Goal system**: define long-term objectives the agent works toward autonomously

### Guardian Daemon
- Proactive system monitoring every 60 seconds
- 4-level decision output: IGNORE → SUGGEST → SAFE_AUTO → NEEDS_CONFIRM
- Automatic health checks: CPU, memory, disk, SSH attacks, service failures
- Parameterized, read-only unattended diagnostics; mutations require approval
- Structured decision output with reasoning

### System Management
- **ai-console**: natural language interface to the AI agent
- **aegisctl**: management CLI (status, doctor, monitor, logs, update)
- **Guided installer**: GPT partitioning, EFI + legacy BIOS dual boot
- **Security hardened**: UFW default-deny firewall, SSH key-only auth

### Bastion Kernel (Research)
- Custom x86_64 kernel with Limine boot protocol
- Virtual filesystem (VFS): lookup, open, read, close operations
- Initramfs CPIO newc format parser
- ELF64 program loader with BSS zeroing
- GDT, IDT, PMM, VMM, kernel heap, TSS
- Ring 3 ELF process bootstrap with serial write and exit syscalls
- Scheduler interfaces are present; multitasking and preemption remain in development

## Quick Start

### Download ISO
Get the latest ISO from [Releases](https://github.com/lmenghao6-png/ai-native-kernel/releases).

The current images are developer previews intended for virtual machines and
disposable test hardware. The Live environment uses `aegis-live` / `aegisos`;
SSH password authentication is disabled. Installation requires creating a new
administrator account, removes the Live account, and locks direct root login.

### Boot (VM)
```bash
qemu-system-x86_64 -machine q35 -m 1G -no-reboot \
  -nographic -serial mon:stdio \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/ovmf/OVMF.fd \
  -cdrom aegisos-0.3-dev.iso
```

### Boot (Physical)
```bash
sudo dd if=aegisos-0.3-dev.iso of=/dev/sdX bs=4M status=progress
```
Boot in UEFI mode. Select "AegisOS Live" to try, or "Install AegisOS to Disk" to install.

### Post-Install
```bash
# Configure AI backend
sudo nano /etc/aegisos/ai-agent.conf

# Check system health
aegisctl doctor

# Start AI console
ai-console

# Talk to the agent
ai-console "What is the current disk usage?"
```

## Building from Source

### Prerequisites
- Ubuntu 24.04 or Debian bookworm
- Root/sudo access

### Full ISO Build
```bash
# Install build dependencies
sudo apt-get install -y debian-archive-keyring mmdebstrap squashfs-tools grub-pc-bin \
    grub-efi-amd64-bin xorriso mtools parted dosfstools rsync \
    clang lld make git cpio

# Build rootfs + squashfs + bootable ISO
make aegisos-image

# Output
ls -lh build/aegisos/image/aegisos-0.3-dev.iso

# Optional local AI backend: add these to the rootfs, then rebuild the image
sudo install -Dm755 /path/to/llama-cli \
    build/aegisos/linux-rootfs/usr/local/libexec/aegisos/llama-cli
sudo install -Dm644 /path/to/model.gguf \
    build/aegisos/linux-rootfs/usr/local/share/aegisos/models/qwen2.5-0.5b-q4_k_m.gguf
bash tools/build-aegisos-image.sh
```

### Bastion Kernel Only
```bash
make all -j$(nproc)
# Output: build/aikernel.elf + build/initramfs.cpio

# Test with QEMU
make fat
qemu-system-x86_64 -bios /usr/share/ovmf/OVMF.fd -m 256M \
    -nographic -serial mon:stdio \
    -drive format=raw,file=fat:rw:build/fatroot
```

## Configuration

### AI Backend
Edit `/etc/aegisos/ai-agent.conf`:
```ini
[api]
endpoint = https://api.deepseek.com/v1
model = deepseek-chat
key = your-api-key-here
local_model_enabled = true
```

Supported providers: DeepSeek, OpenAI, Ollama, Claude, or any OpenAI-compatible endpoint.

### Guardian Goals
Edit `/etc/aegisos/guardian.conf`:
```ini
[guardian]
enabled = true
interval = 60
auto_execute_safe = true
goals = Keep the system secure and stable. Monitor disk space, memory, and service health.
```

## CI/CD

GitHub Actions automatically:
1. **Test** Python policy code and build the Bastion kernel
2. **Boot** Bastion in QEMU and verify a Ring 3 program runs and exits
3. **Build** the full AegisOS ISO distribution
4. **Log in** to the ISO in QEMU and verify hardened services
5. **Release** when a version tag (`v*`) is pushed

## Project Status

| Component | Version | Status |
|-----------|---------|--------|
| AegisOS Distribution | 0.3-dev | Bootable integration |
| Agent Framework | 0.3-dev | Policy-restricted prototype |
| Guardian Daemon | 0.3-dev | Read-only autonomous prototype |
| Bastion Kernel | 0.3-dev | Single-process research kernel |

## License

MIT License — see [LICENSE](LICENSE) file.

---

Built with ❤️ by the AegisOS team.
