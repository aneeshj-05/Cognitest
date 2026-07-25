# Cognitest Frontend

## Production Gates

- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run check` (runs all of the above)
- `npm run audit:prod`

## Test Suites

- Unit + integration: `npm run test`
- E2E smoke: `npm run test:e2e`

## Environment

- `VITE_API_URL` should point to the backend API base URL.
- Dev fallback is in `.env`.

## Cleanup + Hygiene Checklist

- Keep only one project detail page implementation (`ProjectDetailPageNew.tsx`).
- Remove unreachable UI/components/services as soon as they become dead.
- Keep frontend dependencies minimal; remove unused direct deps before release.
- Resolve critical audit vulnerabilities before production deploy.
- Frontend currently has its own nested `.git` repository. Decide whether to keep nested git or move to a single-repo layout before release automation.
