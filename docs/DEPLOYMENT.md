# Deployment

## Local release flow

1. Generate a release artifact with `python pipeline.py`.
2. Promote the artifact into `site/published` with `python scripts/promote-artifact.py --artifact ...`.
3. Build the static bundle with `python scripts/build-site.py`.
4. Review `site/dist/` and `site/dist/deployment-manifest.json`.
5. Export the Vercel prebuilt bundle with `python scripts/export-vercel.py`.
6. Deploy with `vercel deploy --prebuilt`.
7. Verify the deployed page with `python scripts/verify-deploy.py --artifact ... --target preview`.
8. After preview approval, alias the production domain in Vercel and rerun `python scripts/verify-deploy.py --artifact ... --target production`.

## Vercel validation

Use `.vercel/output/` as the deployable prebuilt bundle. Validate:

- `/insights/{slug}` returns 200
- `<title>` and meta description match the artifact
- canonical URL is correct
- JSON-LD is present in `<head>`
- `logs/deployments.jsonl` records both export and verification

## DNS and domain

- Preview URL is configured in `config.yaml`
- Production URL is configured in `config.yaml`
- Connect the owned domain in Vercel before production rollout
- Keep the final Vercel project name, DNS records, and alias steps in `docs/HANDOFF.md`
