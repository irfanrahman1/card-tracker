# Deploying Card Tracker (free)

The app runs as **one Docker container** (see `Dockerfile`): it builds the React
website and runs the Python API, which also serves the website. It needs a
**Postgres** database.

Free setup used here:

| Part | Service | Why |
|---|---|---|
| App | **Koyeb** (free instance) | No credit card; builds straight from GitHub; wakes in a few seconds after being idle |
| Database | **Neon** (free plan) | No credit card; data isn't deleted; no charges for going over (it stops at the limit) |

Pick nearby regions for both so pages load fast: **Neon: AWS US East (N. Virginia)**
and **Koyeb: Washington, D.C.**

> Plans and screens change over time. If a button below is named differently, look
> for the closest match.

## 1. Create the database (Neon)

1. Sign up at neon.com (GitHub login works).
2. Create a project: name `card-tracker`, Postgres version: latest, region **AWS US East (N. Virginia)**.
3. On the project dashboard, click **Connect** and copy the **connection string**. It
   looks like `postgresql://user:password@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require`.

**This string contains your database password. Never put it in the code, GitHub, or a chat.**
It only goes into Koyeb's settings (step 2).

## 2. Deploy the app (Koyeb)

1. Sign up at koyeb.com (GitHub login works) and allow Koyeb to access the
   `card-tracker` repository.
2. **Create Web Service → GitHub →** pick `card-tracker`, branch `main`.
3. **Builder:** Dockerfile (it finds `Dockerfile` at the root).
4. **Instance:** Free. **Region:** Washington, D.C.
5. **Environment variables** (add `DATABASE_URL` as a *Secret*):

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string (as a Secret) |
   | `COOKIE_SECURE` | `true` |
   | `TRUSTED_PROXY_HOPS` | `1` |
   | `ALLOWED_ORIGINS` | your app's address, e.g. `https://card-tracker-yourname.koyeb.app` (add it after the first deploy, once you know it) |

6. **Port:** `8000`, protocol HTTP. **Health check:** path `/api/health`.
7. Click **Deploy**. The first build takes a few minutes. When it says *Healthy*,
   open the public URL.

Every `git push` to `main` redeploys automatically.

## 3. Check it

- The login page loads over `https://` (padlock in the address bar).
- **Try the demo** works.
- Create your real account. (A fresh database starts empty; upload your CSVs again.)

## Moving to another host later

Any host that runs a Dockerfile works the same way: same image, same four
environment variables. For example, Google Cloud Run:

```bash
gcloud run deploy card-tracker --source . --region us-east4 --allow-unauthenticated \
  --max-instances 1 --set-env-vars COOKIE_SECURE=true,TRUSTED_PROXY_HOPS=1
```

(Set `DATABASE_URL` with Secret Manager, not on the command line.)

## Testing the container on your own computer (optional)

Needs Docker Desktop and a Postgres database (a free Neon branch works):

```bash
docker build -t card-tracker .
docker run -p 8000:8000 -e DATABASE_URL="postgresql://..." card-tracker
```

Then open http://localhost:8000.
