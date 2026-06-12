#!/bin/bash

set -euo pipefail

purge=false
if [[ "${1:-}" == "--purge" ]]; then
    purge=true
elif [[ $# -ne 0 ]]; then
    echo "Usage: aegis-uninstall [--purge]" >&2
    exit 2
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run aegis-uninstall through sudo." >&2
    exit 1
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="/var/backups/aegisos-$timestamp.tar.gz"
mkdir -p /var/backups
paths=()
for path in /etc/aegisos /var/lib/aegisos; do
    [[ -e "$path" ]] && paths+=("${path#/}")
done
if (( ${#paths[@]} )); then
    tar -C / -czf "$backup" "${paths[@]}"
    chmod 600 "$backup"
    echo "Configuration and state backup: $backup"
fi

systemctl disable --now aegisosd.service guardian.service 2>/dev/null || true
rm -f \
    /etc/systemd/system/aegisosd.service \
    /etc/systemd/system/guardian.service \
    /usr/local/bin/aegisctl \
    /usr/local/bin/ai-console \
    /usr/local/bin/aegis-update \
    /usr/local/sbin/aegis-uninstall \
    /usr/lib/tmpfiles.d/aegisos.conf
rm -rf /usr/local/lib/aegisos
if $purge; then
    rm -rf /etc/aegisos /var/lib/aegisos /var/log/aegisos /run/aegisos
fi
systemctl daemon-reload
echo "AegisOS AI services removed."
