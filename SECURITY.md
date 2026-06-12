# Security Model

## Root AI Trust Boundary

AegisOS intentionally runs both AI services as root. The Agent exposes arbitrary
shell execution and all actor capabilities. The Guardian executes model-provided
commands through `/bin/bash -lc` without an approval queue or command allowlist.

Anything that can influence model context may influence root execution,
including logs, filenames, command output, network content, API responses, and
the model provider itself. UFW, SSH hardening, auditd, and signed updates do not
remove this risk.

Do not deploy AegisOS on a machine containing irreplaceable data or credentials
unless this trust model is acceptable.

## Emergency Response

From a local administrator shell:

```bash
aegisctl ai-stop
sudo systemctl status aegisosd guardian
sudo journalctl -u aegisosd -u guardian
sudo ausearch -k aegisos_root_actions
```

If the running system cannot be trusted, boot trusted recovery media, mount the
root filesystem, create `/etc/aegisos/agent-disabled`, and inspect it offline.
Do not re-enable the services until the initiating input and resulting changes
are understood.

## Update Trust

Application updates are accepted only after `gpgv` verifies the signed manifest
against `/usr/share/keyrings/aegisos-release.gpg`. The signed manifest binds the
release version, bundle name, bundle SHA-256, and configuration schema.

Release private keys must never be stored in the repository or image. Rotate a
compromised key by shipping a new trust anchor through a separately trusted
full-image release.

## Reporting

Report security issues privately to the repository owner before publishing
details. Include the AegisOS version, affected component, reproduction steps,
and whether root execution occurred.
