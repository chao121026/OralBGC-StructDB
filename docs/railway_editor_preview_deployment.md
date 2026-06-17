# Railway Editor Preview Deployment

This guide prepares the OralBGC-StructDB editor preview as one Railway web
service running the original FastAPI/Jinja server-rendered ASGI application
directly under Uvicorn. Do not add Railway PostgreSQL, Redis, volumes, workers,
or scheduled jobs.

## Architecture

- Website: original FastAPI/Jinja server-rendered website.
- Source: GitHub repository branch selected for preview.
- Runtime: Uvicorn serving `app.main:app`.
- Database: bundled read-only `app/data/phrc_bgcstructdb.sqlite`.
- Resource manifest: packaged sanitized runtime manifest at
  `app/data/integrated-resource-manifest.json`.
- Large files: anonymous direct HTTPS links derived from manifest relative
  paths and the configured release root.
- Globus Web App: not exposed to visitors.
- Health check: `/health`.

## Railway Project

1. Create or open a Railway account.
2. Create one project.
3. Deploy from the GitHub repository.
4. Select the preview branch.
5. Keep exactly one service and one replica.
6. Do not add a database, volume, worker, or cron service.

## Build Configuration

Railway/Nixpacks should install Python dependencies from `requirements.txt`.
The repository includes `nixpacks.toml`, `railway.json`, `Procfile`, and
`.python-version`.

Verified start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers
```

Health-check path:

```text
/health
```

## Environment Variables

Required preview variables:

```text
DEPLOYMENT_MODE=editor_preview
RELEASE_PUBLICATION_STATE=staging_validation

GLOBUS_DIRECT_HTTPS_BASE_URL=https://g-f2d91c.6d8b.03c0.data.globus.org
GLOBUS_BROWSER_FETCH_BASE_URL=https://g-f2d91c.6d8b.03c0.data.globus.org
GLOBUS_RELEASE_RELATIVE_ROOT=staging/v1
GLOBUS_ALLOWED_HOSTS=g-f2d91c.6d8b.03c0.data.globus.org
```

Do not commit secrets or private environment files.

## Public Domain

1. Open the Railway service settings.
2. Generate a Railway public domain.
3. Visit the domain after deploy succeeds.
4. Confirm `/health` returns `status: ok` and `database: available`.

## Runtime Checks

Check build logs for dependency installation and the Uvicorn start command.
Check runtime logs for startup failures. Test:

- `/`
- `/about`
- `/contact`
- `/help`
- `/downloads`
- `/search?q=BGS-MAG-000283`
- `/networks?gcf=BGS-GCF-C03-0003`
- `/mags/BGS-MAG-000283`
- `/bgcs/BGS-BGC-000890`
- `/gcfs/BGS-GCF-C03-0003`
- `/proteins/BGS-PRT-000001`
- `/structures/BGS-STR-000001`

Confirm visitor pages contain no Globus browsing or transfer actions, no
collection UUID, no `origin_id=`, and no `app.globus.org` links.

## Deployment Control

Disable automatic deployments if the preview should remain fixed during review.
To roll back, redeploy a known-good commit or switch the service back to a
previous successful Railway deployment.

Pause or delete the preview service when editor review is complete. Monitor
Railway usage during review and keep the configuration to the Hobby preview
shape: one service, one replica, no PostgreSQL, no Redis, no persistent volume,
no background worker, and no scheduled job.

## Future Release Root Switch

After immutable promotion and validation, switch:

```text
GLOBUS_RELEASE_RELATIVE_ROOT=releases/v1
RELEASE_PUBLICATION_STATE=published
DEPLOYMENT_MODE=production
```

No template, JavaScript, database, or source-code change should be required for
that root switch.
