#!/bin/bash

set -euo pipefail

ROOTFS="${1:-build/aegisos/linux-rootfs}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CACHE_DIR="${AEGISOS_DOWNLOAD_CACHE:-$REPO_DIR/build/aegisos/downloads}"

LLAMA_VERSION="b9603"
LLAMA_ARCHIVE="llama-${LLAMA_VERSION}-bin-ubuntu-x64.tar.gz"
LLAMA_URL="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_VERSION}/${LLAMA_ARCHIVE}"
LLAMA_SHA256="1917ea869670b60e69f80024d17213aabcf122e4e2c77783d5e309f1af0b5a1a"

MODEL_REPOSITORY="Qwen/Qwen2.5-0.5B-Instruct-GGUF"
MODEL_REVISION="df5bf01389a39c743ab467d734bf501681e041c5"
MODEL_SOURCE_FILE="qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_INSTALL_FILE="qwen2.5-0.5b-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/${MODEL_REPOSITORY}/resolve/${MODEL_REVISION}/${MODEL_SOURCE_FILE}"
MODEL_SHA256="74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"
MODEL_LICENSE_URL="https://huggingface.co/${MODEL_REPOSITORY}/raw/${MODEL_REVISION}/LICENSE"
MODEL_LICENSE_SHA256="832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e"

SUDO=()
if [[ $EUID -ne 0 ]]; then
    SUDO=(sudo)
fi

download_checked() {
    local url="$1"
    local destination="$2"
    local expected_sha256="$3"
    local temporary="${destination}.part"

    if [[ -f "$destination" ]] &&
       printf '%s  %s\n' "$expected_sha256" "$destination" | sha256sum --check --status; then
        echo "Using cached $(basename "$destination")"
        return
    fi

    rm -f "$destination" "$temporary"
    echo "Downloading $(basename "$destination")..."
    curl --fail --location --retry 3 --retry-delay 2 \
        --output "$temporary" "$url"
    printf '%s  %s\n' "$expected_sha256" "$temporary" |
        sha256sum --check --status || {
            rm -f "$temporary"
            echo "Checksum verification failed for $url" >&2
            exit 1
        }
    mv "$temporary" "$destination"
}

[[ -d "$ROOTFS" ]] || {
    echo "Rootfs not found: $ROOTFS" >&2
    exit 1
}
for command in curl sha256sum tar; do
    command -v "$command" >/dev/null 2>&1 || {
        echo "Missing required command: $command" >&2
        exit 1
    }
done

mkdir -p "$CACHE_DIR"
LLAMA_CACHE="$CACHE_DIR/$LLAMA_ARCHIVE"
MODEL_CACHE="$CACHE_DIR/$MODEL_SOURCE_FILE"
LICENSE_CACHE="$CACHE_DIR/qwen2.5-0.5b-LICENSE"

download_checked "$LLAMA_URL" "$LLAMA_CACHE" "$LLAMA_SHA256"
download_checked "$MODEL_URL" "$MODEL_CACHE" "$MODEL_SHA256"
download_checked "$MODEL_LICENSE_URL" "$LICENSE_CACHE" "$MODEL_LICENSE_SHA256"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT
tar -xzf "$LLAMA_CACHE" -C "$TEMP_DIR"
LLAMA_SOURCE="$TEMP_DIR/llama-$LLAMA_VERSION"
if [[ ! -x "$LLAMA_SOURCE/llama-server" ||
      ! -x "$LLAMA_SOURCE/llama-cli" ]]; then
    echo "Pinned llama.cpp archive has an unexpected layout" >&2
    exit 1
fi

LLAMA_DEST="$ROOTFS/usr/local/libexec/aegisos/llama-$LLAMA_VERSION"
MODEL_DEST="$ROOTFS/usr/local/share/aegisos/models/$MODEL_INSTALL_FILE"
DOC_DEST="$ROOTFS/usr/local/share/doc/aegisos"

"${SUDO[@]}" rm -rf "$LLAMA_DEST"
"${SUDO[@]}" install -d -m 755 "$LLAMA_DEST" "$(dirname "$MODEL_DEST")" "$DOC_DEST"
"${SUDO[@]}" install -m 755 \
    "$LLAMA_SOURCE/llama-server" \
    "$LLAMA_SOURCE/llama-cli" \
    "$LLAMA_DEST/"
"${SUDO[@]}" cp -a "$LLAMA_SOURCE"/lib*.so* "$LLAMA_DEST/"
"${SUDO[@]}" install -m 644 "$LLAMA_SOURCE/LICENSE" \
    "$DOC_DEST/llama.cpp-LICENSE"
"${SUDO[@]}" install -m 644 "$LICENSE_CACHE" \
    "$DOC_DEST/Qwen2.5-0.5B-Instruct-LICENSE"
"${SUDO[@]}" install -m 644 "$MODEL_CACHE" "$MODEL_DEST"

"${SUDO[@]}" tee "$ROOTFS/etc/ld.so.conf.d/aegisos-llama.conf" >/dev/null <<EOF
/usr/local/libexec/aegisos/llama-$LLAMA_VERSION
EOF
"${SUDO[@]}" chmod 644 "$ROOTFS/etc/ld.so.conf.d/aegisos-llama.conf"
"${SUDO[@]}" chroot "$ROOTFS" ldconfig

"${SUDO[@]}" tee "$ROOTFS/usr/local/libexec/aegisos/llama-cli" >/dev/null <<EOF
#!/bin/sh
export LD_LIBRARY_PATH="/usr/local/libexec/aegisos/llama-$LLAMA_VERSION\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
cd /usr/local/libexec/aegisos/llama-$LLAMA_VERSION || exit 1
exec ./llama-cli "\$@"
EOF
"${SUDO[@]}" chmod 755 "$ROOTFS/usr/local/libexec/aegisos/llama-cli"

"${SUDO[@]}" tee "$ROOTFS/usr/local/share/aegisos/models/README" >/dev/null <<EOF
AegisOS bundled local model

Model: Qwen2.5-0.5B-Instruct Q4_K_M
Repository: https://huggingface.co/$MODEL_REPOSITORY
Revision: $MODEL_REVISION
File: $MODEL_SOURCE_FILE
SHA-256: $MODEL_SHA256
Runtime: llama.cpp $LLAMA_VERSION
Runtime source: $LLAMA_URL
Runtime SHA-256: $LLAMA_SHA256
EOF
"${SUDO[@]}" chmod 644 "$ROOTFS/usr/local/share/aegisos/models/README"

echo "Installed Qwen2.5-0.5B-Instruct and llama.cpp $LLAMA_VERSION"
