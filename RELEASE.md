# Release Procedure

## Signing Keys

Create a dedicated offline GPG signing key. Export the binary public key and an
ASCII-armored private-key backup:

```bash
gpg --quick-gen-key "AegisOS Release <release@example.invalid>" ed25519 sign 2y
gpg --output aegisos-release.gpg --export <fingerprint>
gpg --armor --export-secret-keys <fingerprint> > aegisos-release-private.asc
```

Configure these GitHub Actions secrets:

- `AEGISOS_RELEASE_PUBLIC_KEY_B64`: `base64 -w0 aegisos-release.gpg`
- `AEGISOS_RELEASE_PRIVATE_KEY`: contents of the armored private key

Keep the private key outside the repository. For a passphrase-protected key,
use a dedicated signing environment that can supply the passphrase
non-interactively; the provided workflow assumes its imported CI key can sign
without prompting.

## Local Candidate

```bash
export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
export AEGISOS_RELEASE_PUBLIC_KEY="$PWD/aegisos-release.gpg"
make test
make image
(cd build/aegisos/image && sha256sum --check SHA256SUMS)
make test-iso
make test-install
```

Build a signed application update from the same rootfs:

```bash
export AEGISOS_SIGNING_KEY=<fingerprint>
bash tools/build-release-bundle.sh
gpgv --keyring aegisos-release.gpg \
  build/aegisos/update/manifest.json.sig \
  build/aegisos/update/manifest.json
```

## Tag

Set `VERSION`, commit it, and create an exact matching tag:

```bash
version="$(tr -d '[:space:]' < VERSION)"
git tag -s "v$version" -m "AegisOS $version"
git push origin main "v$version"
```

The tag workflow builds the ISO, boots it, installs it to a disposable disk,
verifies checksums, builds the signed update bundle, signs ISO metadata, and
publishes all artifacts.

## Verification

Release consumers should verify both signature and checksum:

```bash
gpgv --keyring aegisos-release.gpg SHA256SUMS.sig SHA256SUMS
sha256sum --check SHA256SUMS
gpgv --keyring aegisos-release.gpg \
  release-manifest.json.sig release-manifest.json
```
