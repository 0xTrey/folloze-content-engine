#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
archive="$repo_root/deploy/cloudflare/folloze-blog-production.tar.gz"
manifest="$repo_root/deploy/cloudflare/manifest.sha256"
archive_checksum="$repo_root/deploy/cloudflare/archive.sha256"
output_dir="$repo_root/site/cloudflare-production"

for required_file in "$archive" "$manifest" "$archive_checksum"; do
  [[ -f "$required_file" ]] || {
    printf 'Missing production snapshot file: %s\n' "$required_file" >&2
    exit 1
  }
done

(
  cd "$(dirname "$archive")"
  shasum -a 256 -c "$(basename "$archive_checksum")"
)

if [[ -d "$output_dir" ]]; then
  find "$output_dir" -type f -delete
  find "$output_dir" -mindepth 1 -depth -type d -empty -delete
fi
mkdir -p "$output_dir"

tar -xzf "$archive" -C "$output_dir"

(
  cd "$output_dir"
  shasum -a 256 -c "$manifest" >/dev/null
)

printf 'Prepared %s files in %s\n' "$(wc -l < "$manifest" | tr -d ' ')" "$output_dir"
