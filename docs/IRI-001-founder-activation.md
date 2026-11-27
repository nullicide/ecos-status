# IRI-001 production activation — remaining checks

Status: not activated. No credentials included. Do not use actual project data or normal employee accounts. No paid features required.

## Independent Pages publication
1. Repository ecos-status → Settings → Pages. Confirm Build and deployment source is GitHub Actions, and inspect the domain / actual deployed URL. If not correct, capture configuration before changing it.
2. Artifact verification is already complete: run 45905404612, artifact 15157897057 contains both v2 JSON files and feed.xml; the two JSON files are 31,372 bytes each and checked_at is 2026-11-26T22:32:14Z. No additional upload or versioned path is needed. Deploy job 140200878810 reports the primary custom domain as its environment URL, and the earlier mirror verification job follows a 302 before failing with 404.
3. Inspect the github-pages environment deployment URL and any custom domain redirects. Check final URL, HTTP status, response content type and cache headers for both data paths and RSS; compare with the actual artifact. If paths are present but not served, escalate to Pages provider with deployment ID and sanitized request evidence.
4. Acceptance: canonical and mirror shells, fresh v2 reports, historical archive and both RSS URLs (including raw canonical RSS) pass independently; a browser with canonical source blocked loads the current mirror without a false green. No new versioned path is authorized without evidence.
The available connector has no Pages settings API; the existing mirror returned 404 after a redirect. The custom-domain association must be inspected, not blindly removed. If the status custom domain is genuinely served by GitHub Pages, moving it would affect production. If a separate Cloudflare Pages project is the intended primary host, confirm the DNS target and hosting ownership before separating the Pages mirror. Raw GitHub currently supplies the data independently of ECOS DNS, but not an independent HTML shell or scheduler. The new release smoke check records each target independently, including RSS even when the mirror fails.

## Platform synthetic fixture (manual only)
1. In a dedicated isolated evaluation/test tenant, create an ordinary non-admin identity with verified email and standard MFA. Assign it only one synthetic workspace as viewer; no actual project, customer data or privileged grants. Never use a founder session. If tenant isolation cannot be guaranteed, do not enable.
2. Authenticate through the ordinary UI; obtain a short-lived session cookie securely using authorized local browser developer tools. Do not paste it in chat or commit it. This manual check verifies a session-backed bootstrap read, not sign-in/MFA itself; sessions expire and may be refreshed by native auth.
3. GitHub ecos-status → Settings → Environments → create ecos-synthetic. Restrict to main, require reviewer approval where supported, and limit repository write/workflow permissions. Set these environment secrets (not repository files):
   - ECOS_SYNTHETIC_APP_COOKIE: Cookie header for the isolated app identity only.
   - ECOS_SYNTHETIC_ORG_ID: synthetic tenant ID.
   - ECOS_SYNTHETIC_PROJECT_ID: synthetic project ID.
   - ECOS_SYNTHETIC_EMAIL: synthetic identity email.
4. Settings → Secrets and variables → Actions → Variables: set ECOS_SYNTHETIC_ENABLED to true only after isolation and protection are verified. Default absent/false disables the job. Actions → ECOS isolated synthetic workspace (manual) → Run workflow on main. Review and authorize the environment deployment.
5. Acceptance: fixture read returns passed, wrong/expired session fails, no production operational records modified, no raw response or secret logged. Revoke the session and remove the cookie secret after testing; disable variable. No public status is automatically promoted by this workflow.
6. Academy and Investor synthetic identities, automated MFA/sign-in, email and document retrieval remain separate future integration work. Do not substitute this bootstrap check for those checks.

## Production bindings and recovery
Cloudflare dashboard → Workers & Pages → ecos-app production settings: confirm ECOS_DB, ECOS_NATIVE_AUTH_ENABLED, ECOS_AUTH_ORIGIN and existing auth/mail secret presence (never disclose values). Readiness should return only {"ready":true} or 503 {"ready":false}. No authenticated coverage claimed. Inspect existing Academy broker and Investor D1/R2 bindings separately. Confirm existing backup and alert destination configuration and use isolated restore tests. These are not verified by repository inspection.
