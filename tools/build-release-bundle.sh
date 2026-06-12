#!/bin/bash
# Build and sign an AegisOS application update bundle.

set -euo pipefail

ROOTFS="${ROOTFS:-build/aegisos/linux-rootfs}"
OUTPUT_DIR="${OUTPUT_DIR:-build/aegisos/update}"
VERSION_FILE="${VERSION_FILE:-VERSION}"
CONFIG_SCHEMA="${CONFIG_SCHEMA:-2}"
SIGNING_KEY="${AEGISOS_SIGNING_KEY:-}"

if [[ -z "$SIGNING_KEY" ]]; then
    echo "AEGISOS_SIGNING_KEY must identify a private GPG signing key." >&2
    exit 1
fi
if [[ ! -d "$ROOTFS/usr/local/lib/aegisos" ]]; then
    echo "AegisOS rootfs is unavailable: $ROOTFS" >&2
    exit 1
fi

version="$(tr -d '[:space:]' < "$VERSION_FILE")"
bundle="aegisos-app-$version.tar.gz"
mkdir -p "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/$bundle" "$OUTPUT_DIR/manifest.json" \
    "$OUTPUT_DIR/manifest.json.sig"

tar --numeric-owner --owner=0 --group=0 --sort=name \
    --mtime="@${SOURCE_DATE_EPOCH:-0}" \
    -C "$ROOTFS" -czf "$OUTPUT_DIR/$bundle" \
    usr/local/lib/aegisos \
    usr/local/bin/aegisctl \
    usr/local/bin/ai-console \
    usr/local/bin/aegis-update \
    usr/local/sbin/aegis-uninstall \
    etc/systemd/system/aegisosd.service \
    etc/systemd/system/guardian.service \
    usr/lib/tmpfiles.d/aegisos.conf

checksum="$(sha256sum "$OUTPUT_DIR/$bundle" | awk '{print $1}')"
python3 - "$OUTPUT_DIR/manifest.json" "$version" "$bundle" "$checksum" "$CONFIG_SCHEMA" <<'PY'
import json
import sys

path, version, bundle, checksum, schema = sys.argv[1:]
with open(path, "w") as handle:
    json.dump(
        {
            "format": 1,
            "version": version,
            "bundle": bundle,
            "sha256": checksum,
            "config_schema": int(schema),
        },
        handle,
        indent=2,
        sort_keys=True,
    )
    handle.write("\n")
PY

gpg --batch --yes --local-user "$SIGNING_KEY" \
    --output "$OUTPUT_DIR/manifest.json.sig" \
    --detach-sign "$OUTPUT_DIR/manifest.json"
sha256sum "$OUTPUT_DIR/$bundle" "$OUTPUT_DIR/manifest.json" \
    > "$OUTPUT_DIR/SHA256SUMS"
echo "Signed update bundle: $OUTPUT_DIR/$bundle"
