# Folloze Blog Cloudflare Snapshot

This directory contains the exact static artifact serving Vercel production deployment `dpl_5zui66KXXmjwS9PKYa5Hpj7XnqMW` on 2026-08-12.

- `folloze-blog-production.tar.gz`: immutable 298-file production snapshot.
- `archive.sha256`: checksum for the compressed snapshot.
- `manifest.sha256`: per-file checksum manifest for extracted assets.

The source content-engine worktree was dirty and its generated site was ignored by Git, so no existing commit can reproduce this production artifact. The snapshot is intentionally committed before any custom-domain change. Run `scripts/prepare-cloudflare-blog.sh` to verify and extract it into the ignored `site/cloudflare-production/` directory.

The Workers deployment remains on its `workers.dev` hostname during verification. `folloze-blog.com` and `www.folloze-blog.com` stay on Vercel until the owner approves custom-domain cutover after the preview, hash, SEO, TLS, and rollback gates pass.

## Verified deployment

- Worker: `folloze-blog`
- Worker URL: `https://folloze-blog.harnden-trey.workers.dev`
- first verified version: `f5f01b8d-1178-4bbe-afdb-6c5a46461e8c`
- first verified deployment: `6ca44043-68a1-4cc2-be6e-daf2c0c96ecf`
- Vercel rollback deployment: `dpl_5zui66KXXmjwS9PKYa5Hpj7XnqMW`

The Worker passed two independent three-consecutive-pass sweeps covering `/`, `robots.txt`, `sitemap.xml`, a representative article, a 404, and exact SHA-256 parity. Vercel custom domains and DNS remain unchanged during the observation window.
