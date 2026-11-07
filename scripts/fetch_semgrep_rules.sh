#!/usr/bin/env bash
# Downloads Semgrep's official Python rules at a pinned commit, so the same code
# always gets the same findings. To update the rules, change SHA on purpose.
set -euo pipefail

SHA="16b9e6d45f10649f6a531ec4838ed9924372c3bc"
REPO="https://github.com/semgrep/semgrep-rules"
DEST="$(cd "$(dirname "$0")/.." && pwd)/config/semgrep-rules"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git -C "$tmp" init -q
git -C "$tmp" remote add origin "$REPO"
git -C "$tmp" fetch -q --depth 1 origin "$SHA"
git -C "$tmp" checkout -q FETCH_HEAD

rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$tmp/python" "$DEST/python"
cp "$tmp"/LICENSE* "$DEST/" 2>/dev/null || true
echo "$SHA" > "$DEST/VERSION"
echo "Semgrep rules $SHA saved to $DEST"
