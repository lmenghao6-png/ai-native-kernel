# AegisOS Product Requirements Document

## Document Status

- Product: AegisOS
- Version baseline: `0.3-dev`
- Stage: Developer Preview
- Last updated: 2026-06-12
- Product scope: Linux distribution, installer, root AI runtime, operations
  tooling, and signed application updates
- Kernel scope: Standard Debian Linux kernel; a custom kernel is not part of
  the product

## Product Summary

AegisOS turns a disposable x86_64 machine or virtual machine into an
AI-operated Linux node. A configured language model observes system state,
selects operational actions, and can execute those actions as root. The system
records root actions, provides an emergency stop, and supports signed updates
with rollback.

The Developer Preview is a research and evaluation product. It is intended to
test whether a persistent AI operator can diagnose and remediate Linux system
issues with enough visibility and operator control to be useful.

## Problem

Operating a Linux system requires users to inspect multiple sources of state,
translate findings into shell or service-management commands, and repeatedly
perform routine remediation. Existing AI assistants usually provide advice but
do not remain active as part of the operating environment.

AegisOS addresses this by packaging an AI operator into an installable Linux
system with:

- continuous system observation;
- persistent goals and operational memory;
- direct system execution;
- auditable action records;
- an operator-controlled emergency stop; and
- a controlled application update and rollback path.

## Target Users

### Primary Users

- AI agent and autonomous-systems researchers
- Linux platform and operating-system developers
- Security researchers evaluating root-capable AI behavior
- Lab operators running disposable VMs or test hardware

### Excluded Users

The Developer Preview is not intended for:

- consumer desktop users;
- production servers containing sensitive data or credentials;
- safety-critical, regulated, or high-availability workloads;
- multi-tenant systems;
- environments where model inputs or the model provider are not trusted.

## Core User Jobs

1. Install an AI-operated Linux node from a bootable image.
2. Configure a cloud or loopback OpenAI-compatible model endpoint.
3. Ask a model for system information through a local console.
4. Let the Agent observe system state and execute operational actions.
5. Let the Guardian periodically detect and remediate system issues.
6. Inspect what root actions the AI attempted and what each action returned.
7. Stop both AI services immediately without uninstalling the system.
8. Apply a verified application update and roll back after a failure.
9. Remove the AI layer while preserving configuration and state backups.

## Product Goals

### Developer Preview Goals

- Produce a bootable and installable Debian-based amd64 image.
- Start a persistent Agent and Guardian as explicit root services.
- Support an operator-supplied OpenAI-compatible model backend.
- Expose useful Linux observations and root execution capabilities.
- Record every root action before and after execution.
- Provide a reliable local emergency stop and restart flow.
- Harden the base host with unique credentials, key-only SSH, firewall rules,
  and audit watches.
- Deliver signed AI application updates with migration and rollback.
- Exercise boot and installation flows automatically in QEMU.

### Stable Product Goals

- Make AI execution evidence available outside the controlled host.
- Demonstrate predictable recovery from model, service, update, and storage
  failures.
- Define and meet measurable model-behavior and prompt-injection criteria.
- Validate supported hardware and firmware configurations.
- Demonstrate reproducible release artifacts.

## Non-Goals

- Developing or shipping a custom kernel
- Replacing Debian package management
- Providing a general-purpose graphical desktop
- Guaranteeing that model-generated actions are correct
- Running arbitrary untrusted model input safely as root
- Providing multi-user or multi-tenant policy isolation
- Shipping a production-ready local model in the Developer Preview
- Hiding root authority behind claims of least privilege

## Product Principles

1. **Authority must be explicit.** Agent and Guardian root authority must be
   visible in documentation, service definitions, and status output.
2. **No backend means no AI action.** An unconfigured model backend must not
   trigger calls to a public endpoint or cause autonomous execution.
3. **Root actions must leave evidence.** Each action must have a start record
   and a completion or failure record.
4. **The operator must retain a stop control.** AI services must remain stopped
   while the emergency-stop marker exists.
5. **Updates must be authenticated.** Application updates must be bound to a
   trusted signature and checksum before installation.
6. **Product claims must match executable behavior.** A chat interface must not
   be documented as an execution interface unless it can actually invoke and
   report system actions.

## Functional Requirements

| ID | Requirement | Preview Status |
| --- | --- | --- |
| FR-001 | Build a Debian bookworm amd64 Live ISO using the Debian Linux kernel. | Implemented |
| FR-002 | Boot the Live image through UEFI and expose Live and installation choices. | Implemented |
| FR-003 | Install to GPT storage with UEFI fallback and legacy BIOS boot support. | Implemented |
| FR-004 | Create a unique administrator, lock root login, remove Live credentials, and generate host identity. | Implemented |
| FR-005 | Disable SSH password authentication and enable a default-deny incoming firewall with SSH allowed. | Implemented |
| FR-006 | Configure cloud or loopback OpenAI-compatible model endpoints without requiring a key for loopback endpoints. | Implemented |
| FR-007 | Support optional GGUF inference when an operator separately installs `llama-cli` and a compatible model. | Partial |
| FR-008 | Gather disk, process, memory, log, and network observations. | Implemented |
| FR-009 | Execute Bash, systemd, and APT actions from Agent decisions as root. | Implemented |
| FR-010 | Periodically evaluate system state and execute Guardian remediation commands as root. | Implemented |
| FR-011 | Persist observations, actions, goals, and context in SQLite. | Implemented |
| FR-012 | Append pre-action and post-action records to a private JSONL root-action log. | Implemented |
| FR-013 | Watch AI code, configuration, service definitions, and action logs with `auditd`. | Implemented |
| FR-014 | Stop both AI services and prevent restart while an emergency marker exists. | Implemented |
| FR-015 | Show model-backend readiness and distinguish running services from a usable AI configuration. | Planned |
| FR-016 | Provide a local model console for direct prompts to the configured backend. | Implemented |
| FR-017 | Provide an interactive operator console that can invoke Agent capabilities and display execution results. | Planned |
| FR-018 | Verify update manifests with GPG, verify bundle SHA-256, migrate configuration, snapshot state, and roll back. | Implemented |
| FR-019 | Remove AI services and files while preserving a backup, with an optional purge mode. | Implemented |
| FR-020 | Forward journal, audit, and root-action evidence to an external append-only destination. | Planned |
| FR-021 | Provide trusted offline recovery instructions and media for disabling or repairing the AI layer. | Planned |

## Primary User Flows

### Evaluate in a VM

1. Download and verify the ISO.
2. Boot the Live image.
3. Log in with the published Live account.
4. Confirm service, firewall, and audit status.
5. Configure a test model backend or leave AI execution inactive.

### Install

1. Boot the installer entry.
2. Select a disposable target disk and confirm erasure.
3. Create a unique administrator password and optionally enroll an SSH key.
4. Reboot into the installed system.
5. Confirm that the Live account is absent and root login is locked.

### Configure and Operate

1. Configure `/etc/aegisos/ai-agent.conf`.
2. Confirm backend readiness.
3. Inspect `aegisctl status` and `aegisctl doctor`.
4. Monitor Agent and Guardian logs.
5. Review `/var/log/aegisos/root-actions.jsonl`.

### Emergency Stop and Recovery

1. Run `aegisctl ai-stop`.
2. Confirm that both AI services are inactive and the marker exists.
3. Inspect logs, audit events, and affected system state.
4. Restore or repair the system.
5. Run `aegisctl ai-start` only after the initiating input is understood.

## Security Requirements

- Root AI authority and prompt-injection risk must be disclosed before install.
- The default image must not silently call a public model endpoint without
  credentials.
- AI configuration and state directories must not be world-readable.
- Direct root login and SSH password authentication must remain disabled.
- Release private keys must never be included in the repository or image.
- Update installation must fail when signature, checksum, schema, or archive
  validation fails.
- Emergency stop must work without access to a model provider.
- Stable releases require external evidence collection because root processes
  can modify local evidence.

## Success Metrics

### Developer Preview Exit Metrics

- 100% pass rate for Python policy and update tests on the release commit.
- 100% pass rate for Live ISO boot and full install/reboot tests in QEMU.
- No failed systemd units at the end of automated boot and installation tests.
- Emergency stop and restart pass on a clean installed VM.
- Every tested root action produces paired start and completion or failure
  records.
- Signed update and rollback tests restore the previous version and managed
  files.
- An unconfigured image performs no public model API request.

### Stable Release Metrics

- Thirty-day Agent and Guardian soak test without an unrecovered service loop,
  database corruption, or storage leak.
- Prompt-injection review completed with published threat cases and residual
  risk.
- Recovery procedure validated from trusted offline media.
- Release artifacts reproduced on two clean workers and compared.
- Supported hardware matrix published with boot, networking, storage, and
  installation results.

## Release Boundaries

### Developer Preview

The current target. Suitable for disposable VMs and test hardware. Installation
and root execution work, but model behavior and local evidence cannot be
treated as trustworthy.

### Beta

Requires backend-readiness reporting, operator-facing execution visibility,
external audit forwarding, offline recovery documentation, and model red-team
results.

### Stable

Requires the Stable Release Metrics above, signed public releases, hardware
qualification, reproducibility evidence, and a documented support policy.

## Open Product Decisions

These decisions must be resolved before Beta:

1. Is unrestricted root autonomy the permanent product model, or should the
   product add approval and policy-controlled modes?
2. Should an official image bundle a local model, provide an installer for one,
   or require an external backend?
3. Should Agent and Guardian remain separate decision loops?
4. What is the supported recovery contract after an incorrect root action?
5. What external audit service or protocol is supported?
6. Is the long-term product an installable distribution, an AI layer for
   existing Debian systems, or both?
7. Which model and prompt combinations are qualified for each release?

## Acceptance Criteria for the Current PRD

The Developer Preview satisfies this PRD when all implemented requirements pass
from a clean checkout, the release image contains a release trust key, the
published limitations match `SECURITY.md`, and the artifact is explicitly
labeled as unsuitable for production or sensitive systems.
