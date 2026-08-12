#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-https://folloze-blog.harnden-trey.workers.dev}"
base_url="${base_url%/}"

verify_tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/folloze-blog-verify.XXXXXX")"
cleanup() {
  find "$verify_tmp_dir" -type f -delete 2>/dev/null || true
  rmdir "$verify_tmp_dir" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

fetch_status() {
  local path="$1"
  local output="$2"
  curl --silent --show-error --location \
    --output "$output" \
    --write-out '%{http_code}' \
    "$base_url$path" || return 1
}

sha256_file() {
  local file="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file" | awk '{print $1}'
  else
    sha256sum "$file" | awk '{print $1}'
  fi
}

verify_once() {
  root_status="$(fetch_status / "$verify_tmp_dir/root.html")" || return 1
  robots_status="$(fetch_status /robots.txt "$verify_tmp_dir/robots.txt")" || return 1
  sitemap_status="$(fetch_status /sitemap.xml "$verify_tmp_dir/sitemap.xml")" || return 1
  article_status="$(fetch_status /insights/first-party-buyer-intent-activation-from-signal-to-experience "$verify_tmp_dir/article.html")" || return 1
  not_found_status="$(fetch_status /cloudflare-migration-negative-probe "$verify_tmp_dir/not-found.html")" || return 1

  [[ "$root_status" == "200" ]] || return 1
  [[ "$robots_status" == "200" ]] || return 1
  [[ "$sitemap_status" == "200" ]] || return 1
  [[ "$article_status" == "200" ]] || return 1
  [[ "$not_found_status" == "404" ]] || return 1

  [[ "$(sha256_file "$verify_tmp_dir/root.html")" == "725c9389ada9f7e5dd65ab507aea3609d4167e9c2ab52f137a253fa9e09d30d0" ]] || return 1
  [[ "$(sha256_file "$verify_tmp_dir/robots.txt")" == "0b0fa27f76e4fbf91619b107c38369921e365053ebb49c69c577037de17f9aee" ]] || return 1
  [[ "$(sha256_file "$verify_tmp_dir/sitemap.xml")" == "3e66e91b283c955c4f4e658c78f02ea23122994e4446dc301136d77951cbb129" ]] || return 1
  [[ "$(sha256_file "$verify_tmp_dir/article.html")" == "f6b84deca5a2c3f9d9bd18eb4fab7e7516f0f5957718a62db96383539a07b3b7" ]] || return 1
}

consecutive_passes=0
for attempt in $(seq 1 12); do
  if verify_once; then
    consecutive_passes=$((consecutive_passes + 1))
    printf 'Verification pass %s/3 for %s\n' "$consecutive_passes" "$base_url"
    if [[ "$consecutive_passes" -eq 3 ]]; then
      printf 'Verified exact Folloze Blog production snapshot on %s\n' "$base_url"
      exit 0
    fi
  else
    consecutive_passes=0
    printf 'Verification attempt %s/12 has not converged for %s\n' "$attempt" "$base_url" >&2
  fi
  sleep 2
done

printf 'Folloze Blog verification failed to converge for %s\n' "$base_url" >&2
exit 1
